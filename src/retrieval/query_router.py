import re
import json
from typing import List, Dict
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.config_loader import load_config


class QueryRouter:
    def __init__(self, ollama_api=None):
        self.config = load_config()
        self.ollama_api = ollama_api
    
    def route_query(self, query: str, conversation_history: List[Dict] = None,
                   student_program: str = None, student_year: str = None, 
                   student_minor: str = None, method: str = 'llm') -> Dict:
        if not self.ollama_api or method == 'simple':
            return self.route_simple(query)
        
        return self.route_with_llm_analysis(query, conversation_history, student_program, student_year)
    
    def route_simple(self, query: str) -> Dict:
        query_lower = query.lower()
        collections = []
        
        if any(word in query_lower for word in ['4-year', '4 year', 'plan', 'schedule', 'sequence', 'timeline']):
            collections.append('4_year_plans')
        
        if any(word in query_lower for word in ['minor', 'minors']):
            collections.append('minor_catalogs')
        
        if any(word in query_lower for word in ['prerequisite', 'prereq', 'course', 'credit', 'requirement', 'major', 'degree', 'graduation']):
            collections.append('major_catalogs')
        
        if any(word in query_lower for word in ['policy', 'register', 'gpa', 'abroad', 'transfer', 'availability']):
            collections.append('general_knowledge')
        
        if not collections:
            collections = ['major_catalogs', 'general_knowledge']
        
        token_allocation = 600
        if len(collections) > 2:
            token_allocation = 800
        elif 'plan' in query_lower:
            token_allocation = 1000
        
        return {
            'collections': list(set(collections)),
            'token_allocation': token_allocation,
            'reasoning': f'Simple keyword-based routing: {", ".join(collections)}'
        }

    def route_with_llm_analysis(self, query: str, conversation_history: List[Dict] = None,
                               student_program: str = None, student_year: str = None) -> Dict:
        if not self.ollama_api:
            return {
                'collections': ['major_catalogs', 'general_knowledge'],
                'token_allocation': 600,
                'reasoning': 'No LLM available for routing'
            }
        
        router_config = self.config.get('query_router', {})
        llm_config = self.config.get('llm', {})
        
        collection_descriptions = router_config.get('collection_descriptions', {})
        min_tokens = router_config.get('min_tokens', 150)
        max_tokens = router_config.get('max_tokens', 1250)
        
        collections_desc = "\n".join([
            f"- {name}: {desc}"
            for name, desc in collection_descriptions.items()
        ])
        
        context = f"Student Program: {student_program or 'Unknown'}\nCatalog Year: {student_year or 'Unknown'}"
        
        conversation_context = ""
        if conversation_history:
            last_n = router_config.get('last_n_messages', 3)
            recent = conversation_history[-last_n:] if len(conversation_history) > last_n else conversation_history
            for msg in recent:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                conversation_context += f"{role.capitalize()}: {content}\n"
        
        prompt = f"""You are a routing system for an academic advising chatbot. Analyze the student's query and determine:
1. Which knowledge collections are needed to answer it (select one or more)
2. How many tokens the response should use (between {min_tokens} and {max_tokens})

Available Collections:
{collections_desc}

Collection Selection Rules:
- Use major_catalogs for: course requirements, prerequisites, degree requirements, major-specific questions
- Use minor_catalogs for: minor requirements, minor course details (only if query mentions minor)
- Use 4_year_plans for: graduation timelines, course sequencing, semester planning, "4-year plan" requests
- Use general_knowledge for: university policies, registration procedures, waitlist info, GPA requirements, study abroad (ONLY if query is about policies/procedures, NOT course content)
- For queries about specific courses or degree planning: do NOT include general_knowledge unless explicitly about policies

Student Context:
{context}

Recent Conversation:
{conversation_context if conversation_context else "No previous conversation"}

Current Query: "{query}"

Examples:
- "What are the prereqs for CPSC 380?" -> {{"collections": ["major_catalogs"], "token_allocation": 400}}
- "Generate a 4-year plan with my major and minor" -> {{"collections": ["4_year_plans", "major_catalogs", "minor_catalogs"], "token_allocation": 1000}}
- "How do I register for classes?" -> {{"collections": ["general_knowledge"], "token_allocation": 400}}
- "What's the GPA requirement for graduation?" -> {{"collections": ["general_knowledge"], "token_allocation": 300}}
- "What electives can I take?" -> {{"collections": ["major_catalogs"], "token_allocation": 500}}

Token Allocation Guidelines:
- Simple lookups: {min_tokens}-300 tokens
- Course details: 300-500 tokens
- Multiple topics: 500-800 tokens
- 4-year plans: 800-{max_tokens} tokens

Respond ONLY with valid JSON in this exact format:
{{"collections": ["collection1", "collection2"], "token_allocation": 500, "reasoning": "brief explanation"}}"""

        try:
            response = self.ollama_api.chat(
                model=llm_config.get('router_model', 'gpt-oss:20b'),
                messages=[{'role': 'user', 'content': prompt}],
                stream=False,
                format='json',
                options={
                    'temperature': llm_config.get('router_temperature', 0.1),
                    'num_predict': llm_config.get('router_max_tokens', 500)
                }
            )
            
            if not response or not response.strip():
                return {
                    'collections': ['major_catalogs', 'general_knowledge'],
                    'token_allocation': 600,
                    'reasoning': 'Empty response from router LLM'
                }
            
            cleaned_response = ' '.join(response.split())
            
            try:
                result = json.loads(cleaned_response)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        return {
                            'collections': ['major_catalogs', 'general_knowledge'],
                            'token_allocation': 600,
                            'reasoning': 'Failed to parse router response'
                        }
                else:
                    return {
                        'collections': ['major_catalogs', 'general_knowledge'],
                        'token_allocation': 600,
                        'reasoning': 'No valid JSON found in response'
                    }
            collections = result.get('collections', ['major_catalogs', 'general_knowledge'])
            token_allocation = result.get('token_allocation', 600)
            reasoning = result.get('reasoning', 'LLM analysis')
            
            token_allocation = max(min_tokens, min(token_allocation, max_tokens))
            
            valid_collections = [c for c in collections if c in collection_descriptions]
            if not valid_collections:
                valid_collections = ['major_catalogs', 'general_knowledge']
            
            return {
                'collections': valid_collections,
                'token_allocation': token_allocation,
                'reasoning': reasoning
            }
                
        except json.JSONDecodeError as je:
            print(f"JSON decode error: {je}")
            print(f"Response was: {response[:500] if 'response' in locals() else 'No response'}")
            return {
                'collections': ['major_catalogs', 'general_knowledge'],
                'token_allocation': 600,
                'reasoning': f'JSON decode failed: {str(je)}'
            }
        except Exception as e:
            print(f"LLM routing error: {e}")
            return {
                'collections': ['major_catalogs', 'general_knowledge'],
                'token_allocation': 600,
                'reasoning': f'Error: {str(e)}'
            }


def create_router(ollama_api=None):
    try:
        return QueryRouter(ollama_api)
    except Exception as e:
        print(f"Error creating query router: {e}")
        return None
