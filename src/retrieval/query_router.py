import re
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.config_loader import load_config


class QueryRouter:
    def __init__(self, ollama_api=None):
        self.config = load_config()
        
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
                    'curriculum', 'program', 'cpsc', 'computer science', 'engineering',
                    'courses needed', 'what courses', 'graduate', 'upper division',
                    'lower division', 'electives', 'core courses', 'capstone', 'eeng',
                    'electrical engineering', 'computational sciences', 'ceng', 'game',
                    'game development', 'math', 'mathematics'
                ],
                'patterns': [
                    r'\b(cpsc|eeng|ceng|game|math)\b',
                    r'\bcs\b(?=.*computational)',
                    r'computer\s+science',
                    r'software\s+engineering', 
                    r'electrical\s+engineering',
                    r'computational\s+sciences?',
                    r'game\s+development',
                    r'graduation\s+requirements',
                    r'upper\s+division',
                    r'core\s+courses'
                ]
            },
            '4_year_plans': {
                'keywords': [
                    'freshman', 'sophomore', 'junior', 'senior', 'semester',
                    'sequence', 'schedule', 'plan', 'first year', 'second year',
                    'when should', 'what order', 'course sequence', 'timeline',
                    'roadmap', 'pathway', 'progression', 'recommended order',
                    'create a plan', 'chemistry track', 'track'
                ],
                'patterns': [
                    r'\b(freshman|sophomore|junior|senior)\s+year',
                    r'\b\d+\s*year',
                    r'first\s+year',
                    r'course\s+sequence',
                    r'when\s+(should|to)\s+take',
                    r'recommended\s+(order|sequence)',
                    r'create\s+a?\s*(4\s*year\s*)?plan',
                    r'\b4\s*year\s*plan\b',
                    r'chemistry\s+track',
                    r'what\s+(order|sequence)',
                    r'academic\s+(plan|roadmap|pathway)'
                ]
            },
            'minor_catalogs': {
                'keywords': [
                    'minor', 'analytics', 'data science minor', 'business minor',
                    'minors available', 'double major', 'concentration'
                ],
                'patterns': [
                    r'\bminor\b',
                    r'analytics\s+minor',
                    r'double\s+major'
                ]
            },
            'general_knowledge': {
                'keywords': [
                    'registration', 'enroll', 'deadline', 'policy', 'gpa', 'grade',
                    'transfer', 'credit', 'academic', 'advisor', 'permission',
                    'waitlist', 'drop', 'add', 'calendar', 'dates', 'withdraw',
                    'repeat', 'retake', 'hold', 'probation', 'forms', 'petition'
                ],
                'patterns': [
                    r'registration\s+process',
                    r'academic\s+policy',
                    r'transfer\s+credit',
                    r'permission\s+number',
                    r'academic\s+calendar'
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
    
    def route_query(self, query: str, conversation_history: List[Dict] = None,
                   student_program: str = None, student_year: str = None, 
                   student_minor: str = None, method: str = 'hybrid') -> List[str]:
        enhanced_query = self._enhance_query_with_context(query, conversation_history)
        
        if method == 'keyword':
            return self._keyword_routing(enhanced_query, student_program, student_year, student_minor)
        elif method == 'semantic' and self.semantic_enabled:
            return self._semantic_routing(enhanced_query, student_program, student_year, student_minor)
        elif method == 'llm' and self.ollama_api:
            return self._llm_routing(enhanced_query, student_program, student_year, student_minor)
        else:
            return self._hybrid_routing(enhanced_query, student_program, student_year, student_minor)
    
    def _enhance_query_with_context(self, query: str, conversation_history: List[Dict] = None) -> str:
        if not conversation_history or len(conversation_history) < 2:
            return query
        
        last_n_messages = self.config.get('query_router', {}).get('last_n_messages', 4)
        
        ambiguous_words = ['them', 'those', 'it', 'that', 'these', 'they']
        query_lower = query.lower()
        
        has_ambiguous = any(word in query_lower for word in ambiguous_words)
        is_short = len(query.split()) <= 4
        
        if has_ambiguous or is_short:
            recent_messages = conversation_history[-last_n_messages:] if len(conversation_history) >= last_n_messages else conversation_history
            
            context_text = ""
            for msg in recent_messages:
                if msg.get('role') == 'user':
                    context_text += f" {msg.get('content', '')}"
            
            if context_text.strip():
                academic_terms = self._extract_academic_terms(context_text)
                if academic_terms:
                    enhanced = f"{query} (related to: {', '.join(academic_terms)})"
                    return enhanced
        
        return query
    
    def _extract_academic_terms(self, text: str) -> List[str]:
        text_lower = text.lower()
        terms = []
        
        course_patterns = [
            r'\b(cpsc|eeng|ceng|game|math)\s*\d+',
            r'\bcs\s*\d+(?=.*computational)',
            r'\b(computer science|software engineering|electrical engineering)',
            r'\b(computational sciences?|game development)',
            r'\b(calculus|physics|chemistry|mathematics)',
            r'\b(major|degree|program|graduation|requirements)',
            r'\b(prerequisite|corequisite)',
            r'\b(freshman|sophomore|junior|senior)',
            r'\b(courses?|classes?)',
        ]
        
        for pattern in course_patterns:
            matches = re.findall(pattern, text_lower)
            terms.extend(matches)
        
        unique_terms = list(set(terms))[:3]
        return unique_terms
    
    def _keyword_routing(self, query: str, student_program: str = None, 
                        student_year: str = None, student_minor: str = None) -> List[str]:
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
            collections, query_lower, student_program, student_year, student_minor
        )
        
        if not collections or (len(query.split()) <= 3 and len(collections) < 2):
            collections.extend(['major_catalogs', '4_year_plans', 'general_knowledge'])
            collections = list(dict.fromkeys(collections))
        
        return collections[:3]
    
    def _semantic_routing(self, query: str, student_program: str = None,
                         student_year: str = None, student_minor: str = None, threshold: float = 0.35) -> List[str]:
        if not self.semantic_enabled:
            return self._keyword_routing(query, student_program, student_year, student_minor)
        
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
            collections, query.lower(), student_program, student_year, student_minor
        )
        
        return collections[:3]
    
    def _llm_routing(self, query: str, student_program: str = None,
                    student_year: str = None, student_minor: str = None) -> List[str]:
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
            model_name = self.config.get('llm', {}).get('model', 'llama3.2:1b')
            response = self.ollama_api.chat(
                model=model_name,
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
                       student_year: str = None, student_minor: str = None) -> List[str]:
        
        if self.semantic_enabled:
            semantic_collections = self._semantic_routing(query, student_program, student_year, student_minor, threshold=0.4)
            
            if len(semantic_collections) >= 1:
                return semantic_collections
        
        return self._keyword_routing(query, student_program, student_year, student_minor)
    
    def _add_contextual_collections(self, collections: List[str], query_lower: str,
                                   student_program: str = None, student_year: str = None, 
                                   student_minor: str = None) -> List[str]:
        
        if (student_program and 'major_catalogs' not in collections and
            any(word in query_lower for word in ['major', 'degree', 'graduation', 'requirements', 
                                               'prerequisite', 'curriculum', 'program', 'courses needed',
                                               'what courses', 'graduate', 'upper division', 'lower division'])):
            collections.append('major_catalogs')
        
        if (student_program and student_year and 
            '4_year_plans' not in collections and
            any(word in query_lower for word in ['sequence', 'plan', 'schedule', 'roadmap', 'timeline'])):
            collections.append('4_year_plans')
        
        if ('4_year_plans' not in collections and
            any(phrase in query_lower for phrase in ['4 year plan', 'four year plan', 'course sequence', 
                                                   'freshman year', 'sophomore year', 'junior year', 'senior year',
                                                   'first year', 'second year', 'when should i take',
                                                   'recommended order', 'course timeline', 'roadmap',
                                                   'create a plan', 'academic plan'])):
            collections.append('4_year_plans')
        
        if (student_minor and 'minor_catalogs' not in collections and
            any(word in query_lower for word in ['minor', 'themed inquiry', 'analytics', 'game development', 
                                               'information security', 'additional requirements'])):
            collections.append('minor_catalogs')
        
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
