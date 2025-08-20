"""
Query routing system to determine which collections to search based on query semantics.
"""

import re
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


class QueryRouter:
    def __init__(self, ollama_api=None):
        try:
            self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.semantic_enabled = True
        except Exception as e:
            print(f"Warning: Could not load sentence transformer: {e}")
            self.semantic_enabled = False
            
        self.ollama_api = ollama_api
        
        self.collection_patterns = {
            'major_catalogs': {
                'keywords': [
                    'major', 'degree', 'graduation', 'requirements', 'prerequisite', 
                    'curriculum', 'program', 'cs', 'computer science', 'engineering',
                    'courses needed', 'what courses', 'graduate'
                ],
                'patterns': [
                    r'\b(cs|ce|se|ee|ds)\b',
                    r'computer\s+science',
                    r'software\s+engineering', 
                    r'electrical\s+engineering',
                    r'graduation\s+requirements'
                ]
            },
            '4_year_plans': {
                'keywords': [
                    'freshman', 'sophomore', 'junior', 'senior', 'year', 'semester',
                    'sequence', 'schedule', 'plan', 'first year', 'second year',
                    'when should', 'what order', 'course sequence'
                ],
                'patterns': [
                    r'\b(freshman|sophomore|junior|senior)\s+year',
                    r'\b\d+\s*year',
                    r'first\s+year',
                    r'course\s+sequence'
                ]
            },
            'minor_catalogs': {
                'keywords': [
                    'minor', 'analytics', 'data science minor', 'business minor',
                    'minors available'
                ],
                'patterns': [
                    r'\bminor\b',
                    r'analytics\s+minor'
                ]
            },
            'general_knowledge': {
                'keywords': [
                    'registration', 'enroll', 'deadline', 'policy', 'gpa', 'grade',
                    'transfer', 'credit', 'academic', 'advisor', 'permission',
                    'waitlist', 'drop', 'add'
                ],
                'patterns': [
                    r'registration\s+process',
                    r'academic\s+policy',
                    r'transfer\s+credit'
                ]
            }
        }
        
        if self.semantic_enabled:
            self._compute_collection_embeddings()
    
    def _compute_collection_embeddings(self):
        collection_examples = {
            'major_catalogs': [
                "What are the Computer Science major requirements?",
                "What courses do I need to graduate with a CS degree?",
                "What are the prerequisites for upper division courses?",
                "Graduation requirements for engineering majors"
            ],
            '4_year_plans': [
                "What courses should I take freshman year?",
                "What is the recommended course sequence?",
                "When should I take calculus and physics?",
                "Course schedule for first year students"
            ],
            'minor_catalogs': [
                "What minors are available?",
                "Requirements for analytics minor",
                "How do I declare a business minor?",
                "What courses are needed for the data science minor?"
            ],
            'general_knowledge': [
                "When is registration?",
                "How do I get permission numbers?",
                "What is the academic calendar?",
                "Transfer credit policies and procedures"
            ]
        }
        
        self.collection_embeddings = {}
        for collection, examples in collection_examples.items():
            embeddings = self.semantic_model.encode(examples)
            self.collection_embeddings[collection] = np.mean(embeddings, axis=0)
    
    def route_query(self, query: str, student_program: str = None, 
                   student_year: str = None, method: str = 'hybrid') -> List[str]:
        """
        Route query to appropriate collections.
        
        Args:
            query: User query
            student_program: Student's program (cs, ce, se, etc.)
            student_year: Student's academic year
            method: 'keyword', 'semantic', 'llm', or 'hybrid'
        
        Returns:
            List of collection names to search
        """
        if method == 'keyword':
            return self._keyword_routing(query, student_program, student_year)
        elif method == 'semantic' and self.semantic_enabled:
            return self._semantic_routing(query, student_program, student_year)
        elif method == 'llm' and self.ollama_api:
            return self._llm_routing(query, student_program, student_year)
        else:
            return self._hybrid_routing(query, student_program, student_year)
    
    def _keyword_routing(self, query: str, student_program: str = None, 
                        student_year: str = None) -> List[str]:
        """Current rule-based approach with improvements."""
        query_lower = query.lower()
        collections = []
        scores = {}
        
        for collection, config in self.collection_patterns.items():
            score = 0
            
            for keyword in config['keywords']:
                if keyword.lower() in query_lower:
                    score += 2
            
            for pattern in config['patterns']:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    score += 3
            
            if score > 0:
                scores[collection] = score
        
        sorted_collections = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        collections = [col for col, score in sorted_collections if score >= 2]
        
        collections = self._add_contextual_collections(
            collections, query_lower, student_program, student_year
        )
        
        return collections[:2]
    
    def _semantic_routing(self, query: str, student_program: str = None,
                         student_year: str = None, threshold: float = 0.35) -> List[str]:
        if not self.semantic_enabled:
            return self._keyword_routing(query, student_program, student_year)
        
        query_embedding = self.semantic_model.encode([query])
        scores = {}
        
        for collection, collection_embedding in self.collection_embeddings.items():
            similarity = cosine_similarity(query_embedding, [collection_embedding])[0][0]
            scores[collection] = similarity
        
        collections = [
            collection for collection, score in scores.items() 
            if score > threshold
        ]
        
        collections = sorted(collections, key=lambda x: scores[x], reverse=True)
        
        collections = self._add_contextual_collections(
            collections, query.lower(), student_program, student_year
        )
        
        return collections[:3]
    
    def _llm_routing(self, query: str, student_program: str = None,
                    student_year: str = None) -> List[str]:
        """LLM-based intelligent routing."""
        prompt = f"""You are a university academic routing system. Given a student query, determine which knowledge collections to search.

            Available collections:
            - major_catalogs: Degree requirements, course prerequisites, graduation requirements
            - 4_year_plans: Semester course sequences, recommended schedules by year
            - minor_catalogs: Minor program requirements and course lists
            - general_knowledge: Registration, policies, deadlines, academic procedures

            Student context:
            - Program: {student_program or "Not specified"}
            - Year: {student_year or "Not specified"}

            Query: "{query}"

            Return only a comma-separated list of the most relevant 1-3 collections.

            Examples:
            "CS major requirements" → major_catalogs
            "freshman year courses" → 4_year_plans,major_catalogs  
            "analytics minor" → minor_catalogs
            "registration deadline" → general_knowledge

            Collections:"""

        try:
            response = self.ollama_api.chat(
                model='llama3.2:1b',
                messages=[{'role': 'user', 'content': prompt}],
                stream=False,
                options={'temperature': 0.1, 'num_predict': 30}
            )
            
            collections = []
            for item in response.split(','):
                item = item.strip()
                if item in self.collection_patterns:
                    collections.append(item)
            
            return collections[:3]
            
        except Exception as e:
            print(f"LLM routing failed: {e}")
            return self._keyword_routing(query, student_program, student_year)
    
    def _hybrid_routing(self, query: str, student_program: str = None,
                       student_year: str = None) -> List[str]:
        """Hybrid approach: semantic first, LLM for complex cases."""
        
        if self.semantic_enabled:
            semantic_collections = self._semantic_routing(query, student_program, student_year, threshold=0.4)
            
            if len(semantic_collections) >= 1:
                return semantic_collections
        
        return self._keyword_routing(query, student_program, student_year)
    
    def _add_contextual_collections(self, collections: List[str], query_lower: str,
                                   student_program: str = None, student_year: str = None) -> List[str]:
        
        if (student_program and 'major_catalogs' not in collections and
            any(word in query_lower for word in ['major', 'degree', 'graduation', 'requirements', 
                                               'prerequisite', 'curriculum', 'program', 'courses needed',
                                               'what courses', 'graduate', 'upper division', 'lower division'])):
            collections.append('major_catalogs')
        
        if (student_program and student_year and 
            '4_year_plans' not in collections and
            any(word in query_lower for word in ['year', 'semester', 'sequence', 'plan', 'schedule'])):
            collections.append('4_year_plans')
        
        if not collections:
            collections.append('general_knowledge')
        
        return list(dict.fromkeys(collections))


def create_router(ollama_api=None):
    try:
        return QueryRouter(ollama_api)
    except Exception as e:
        print(f"Error creating query router: {e}")
        return None

def route_query_simple(query: str, student_program: str = None, student_year: str = None) -> List[str]:
    router = QueryRouter()
    return router.route_query(query, student_program, student_year, method='keyword')
