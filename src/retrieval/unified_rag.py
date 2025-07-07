import os
import sys
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api


class UnifiedRAG:
    def __init__(self):
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=self.config['qdrant']['timeout']
        )
        self.embedding_model = self.config['embedding']['model']
        self.collections = self.config['qdrant']['collections']
        self.ollama_api = get_ollama_api()
        
    def _get_embedding(self, text: str) -> List[float]:
        try:
            embedding = self.ollama_api.get_embeddings(
                model=self.embedding_model,
                prompt=text
            )
            return embedding
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return None
    
    def _get_llm_response(self, prompt: str, enable_thinking: bool = True, 
                         show_thinking: bool = False, use_streaming: bool = True):
        try:
            if use_streaming:
                return self._get_llm_response_stream(prompt, enable_thinking, show_thinking)
            else:
                response = self.ollama_api.chat(
                    model=self.config['llm']['model'],
                    messages=[
                        {
                            'role': 'system',
                            'content': self.config['llm']['system_prompt']
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    stream=False,
                    think=enable_thinking,
                    hide_thinking=not show_thinking,
                    options={
                        'temperature': self.config['llm']['temperature'],
                        'top_p': self.config['llm']['top_p'],
                        'num_predict': self.config['llm']['max_tokens']
                    }
                )
                return response
        except Exception as e:
            print(f"Error getting LLM response: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again later."
    
    def _get_llm_response_stream(self, prompt: str, enable_thinking: bool = True, 
                                show_thinking: bool = False):
        """Generate streaming response"""
        try:
            for chunk in self.ollama_api.chat_stream(
                model=self.config['llm']['model'],
                messages=[
                    {
                        'role': 'system',
                        'content': self.config['llm']['system_prompt']
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                think=enable_thinking,
                hide_thinking=not show_thinking,
                options={
                    'temperature': self.config['llm']['temperature'],
                    'top_p': self.config['llm']['top_p'],
                    'num_predict': self.config['llm']['max_tokens']
                }
            ):
                yield chunk
        except Exception as e:
            print(f"Error getting streaming LLM response: {e}")
            yield "I apologize, but I'm experiencing technical difficulties. Please try again later."
    
    def _build_filter(self, student_program: str = None, student_year: str = None, 
                     document_type: str = None) -> Optional[Filter]:
        conditions = []
        
        if student_program:
            conditions.append(
                FieldCondition(
                    key="program",
                    match=MatchValue(value=student_program.lower())
                )
            )
        
        if student_year:
            conditions.append(
                FieldCondition(
                    key="year",
                    match=MatchValue(value=student_year)
                )
            )
        
        if document_type:
            conditions.append(
                FieldCondition(
                    key="document_type",
                    match=MatchValue(value=document_type)
                )
            )
        
        if conditions:
            return Filter(must=conditions)
        return None
    
    def search_collection(self, query: str, collection_name: str, 
                         student_program: str = None, student_year: str = None,
                         top_k: int = 5) -> List[Dict]:
        try:
            query_embedding = self._get_embedding(query)
            if query_embedding is None:
                return []
            
            filter_condition = self._build_filter(student_program, student_year)
            
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                query_filter=filter_condition,
                limit=top_k,
                with_payload=True,
                with_vectors=False
            )
            
            results = []
            for result in search_results:
                results.append({
                    'text': result.payload.get('chunk_text', ''),
                    'metadata': result.payload,
                    'score': result.score,
                    'collection': collection_name
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching collection {collection_name}: {e}")
            return []
    
    def search_multiple_collections(self, query: str, collection_names: List[str],
                                  student_program: str = None, student_year: str = None,
                                  top_k_per_collection: int = 3) -> List[Dict]:
        """
        Search multiple collections with guaranteed retrieval:
        - ALWAYS get 1 result from major_catalogs (with program/year filter)
        - ALWAYS get 1 result from course_listings (with year filter only)
        - 1 result max from minor_catalogs (if requested, with program/year filter)
        - Remaining slots filled with general_knowledge
        """
        all_results = []
        
        # Priority collections that we MUST retrieve from
        guaranteed_collections = ['major_catalogs', 'course_listings']
        
        for collection_name in guaranteed_collections:
            if collection_name in collection_names:
                if collection_name == 'major_catalogs':
                    collection_results = self.search_collection(
                        query, collection_name, student_program, student_year, top_k=1
                    )
                elif collection_name == 'course_listings':
                    collection_results = self.search_collection(
                        query, collection_name, None, student_year, top_k=1
                    )
                
                if collection_results:
                    all_results.extend(collection_results)
                else:
                    print(f"No filtered results from {collection_name}, trying without filters...")
                    fallback_results = self.search_collection(
                        query, collection_name, None, None, top_k=1
                    )
                    all_results.extend(fallback_results)
        
        if 'minor_catalogs' in collection_names:
            minor_results = self.search_collection(
                query, 'minor_catalogs', student_program, student_year, top_k=1
            )
            all_results.extend(minor_results)
        
        if 'general_knowledge' in collection_names:
            remaining_slots = max(0, top_k_per_collection - len(all_results))
            if remaining_slots > 0:
                general_results = self.search_collection(
                    query, 'general_knowledge', None, None, top_k=remaining_slots
                )
                all_results.extend(general_results)
        
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        return all_results
    
    def answer_question(self, query: str, student_program: str = None, 
                       student_year: str = None, top_k: int = 10, 
                       enable_thinking: bool = True, show_thinking: bool = False,
                       use_streaming: bool = True) -> tuple:
        
        collections_to_search = [
            self.collections['general_knowledge'],
            self.collections['major_catalogs'], 
            self.collections['course_listings']
        ]
        
        minor_keywords = ['minor']
        if any(keyword in query.lower() for keyword in minor_keywords):
            collections_to_search.append(self.collections['minor_catalogs'])
        
        collections_to_search = list(dict.fromkeys(collections_to_search))
        
        retrieved_chunks = self.search_multiple_collections(
            query, collections_to_search, student_program, student_year, 
            top_k_per_collection=top_k
        )
        
        retrieved_chunks = retrieved_chunks[:top_k]
        
        if not retrieved_chunks:
            return ("I don't have enough information to answer your question. "
                   "Please contact academic advising for assistance."), []
        
        context_parts = []
        for chunk in retrieved_chunks:
            text = chunk['text']
            metadata = chunk['metadata']
            
            source_info = ""
            if metadata.get('file_name'):
                source_info = f"[Source: {metadata['file_name']}]"
            
            context_parts.append(f"{source_info} {text}")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Based on the following context from Chapman University's academic catalogs, please answer the student's question.

Context:
{context}

Student Question: {query}

Please provide a helpful, accurate answer based only on the information provided in the context. If the context doesn't contain enough information, say so and recommend the student contact academic advising."""
        
        answer = self._get_llm_response(prompt, enable_thinking=enable_thinking, 
                                       show_thinking=show_thinking, use_streaming=use_streaming)
        
        return answer, retrieved_chunks
    
    def get_collection_stats(self, collection_name: str) -> Dict:
        try:
            info = self.client.get_collection(collection_name)
            return {
                'points_count': info.points_count,
                'vectors_count': info.vectors_count if hasattr(info, 'vectors_count') else 'N/A',
                'status': info.status
            }
        except Exception as e:
            return {'error': str(e)}
    
    def list_collections(self) -> List[str]:
        try:
            collections = self.client.get_collections()
            return [collection.name for collection in collections.collections]
        except Exception as e:
            print(f"Error listing collections: {e}")
            return []
