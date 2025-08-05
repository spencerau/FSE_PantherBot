import os
import sys
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api
from utils.text_preprocessing import preprocess_for_embedding
from retrieval.bm25 import BM25Retriever
from retrieval.fusion import HybridRetriever
from retrieval.reranker import BGEReranker


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
        
        self.hybrid_disabled = os.getenv('HYBRID_DISABLED', 'false').lower() == 'true'
        self.rerank_disabled = os.getenv('RERANK_DISABLED', 'false').lower() == 'true'
        
        self.bm25_retriever = None
        if not self.hybrid_disabled and os.getenv('OPENSEARCH_URL'):
            try:
                self.bm25_retriever = BM25Retriever()
            except Exception as e:
                print(f"BM25 initialization failed: {e}")
        
        self.reranker = None
        self.rerank_disabled = os.getenv('RERANK_DISABLED', 'false').lower() == 'true'
        
    def _get_reranker(self):
        if self.reranker is None and not self.rerank_disabled:
            try:
                print("Initializing reranker (first use)...")
                self.reranker = BGEReranker()
            except Exception as e:
                print(f"Reranker initialization failed: {e}")
                self.reranker = False
        return self.reranker if self.reranker is not False else None
        
    def _get_embedding(self, text: str) -> List[float]:
        try:
            processed_text = preprocess_for_embedding([text], 'query', self.config.get('embedding', {}))[0]
            embedding = self.ollama_api.get_embeddings(
                model=self.embedding_model,
                prompt=processed_text
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
            program_mappings = {
                'Computer Science': 'cs',
                'Computer Engineering': 'ce', 
                'Software Engineering': 'se',
                'Electrical Engineering': 'ee',
                'Data Science': 'ds',
                'cs': 'cs',
                'ce': 'ce',
                'se': 'se', 
                'ee': 'ee',
                'ds': 'ds'
            }
            
            program_code = program_mappings.get(student_program, student_program.lower())
            
            conditions.append(
                FieldCondition(
                    key="program",
                    match=MatchValue(value=program_code)
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
                    key="doc_type",
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
            if self.bm25_retriever and not self.hybrid_disabled:
                return self._hybrid_search(query, collection_name, student_program, student_year, top_k)
            else:
                return self._dense_search(query, collection_name, student_program, student_year, top_k)
        except Exception as e:
            print(f"Error searching collection {collection_name}: {e}")
            return []
    
    def _dense_search(self, query: str, collection_name: str, 
                     student_program: str = None, student_year: str = None,
                     top_k: int = 5) -> List[Dict]:
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []
        
        filter_condition = self._build_filter(student_program, student_year)
        
        search_results = self.client.query_points(
            collection_name=collection_name,
            query=query_embedding,
            query_filter=filter_condition,
            limit=top_k,
            with_payload=True,
            with_vectors=False
        ).points
        
        results = []
        for result in search_results:
            results.append({
                'text': result.payload.get('chunk_text', ''),
                'metadata': result.payload,
                'score': result.score,
                'score_dense': result.score,
                'collection': collection_name
            })
        
        return results
    
    def _hybrid_search(self, query: str, collection_name: str,
                      student_program: str = None, student_year: str = None,
                      top_k: int = 5) -> List[Dict]:
        k_dense = self.config.get('retrieval', {}).get('k_dense', 40)
        k_sparse = self.config.get('retrieval', {}).get('k_sparse', 40)
        
        dense_results = self._dense_search(query, collection_name, student_program, student_year, k_dense)
        
        sparse_results = []
        if self.bm25_retriever:
            sparse_results = self.bm25_retriever.search(query, top_k=k_sparse)
        
        if dense_results and sparse_results:
            from retrieval.fusion import reciprocal_rank_fusion
            fused_results = reciprocal_rank_fusion(
                dense_results, sparse_results,
                k=self.config.get('retrieval', {}).get('rrf_k', 60),
                weights=self.config.get('retrieval', {}).get('fuse_weights', {'dense': 0.6, 'sparse': 0.4})
            )
            return fused_results[:top_k]
        
        return dense_results[:top_k]
    
    def _find_best_4_year_plan_year(self, student_year: str, student_program: str) -> str:
        """
        Find the best available 4-year plan year for a student.
        Since 2022 doesn't have 4-year plans, students should use the next available year.
        """
        if not student_year or not student_program:
            return None
            
        available_years = ['2025', '2024', '2023']
        
        if student_year in available_years:
            return student_year
            
        student_year_int = int(student_year) if student_year.isdigit() else 0
        
        best_year = None
        for year in sorted(available_years):
            year_int = int(year)
            if year_int >= student_year_int:
                best_year = year
                break
        
        return best_year or available_years[0]
    
    def search_multiple_collections(self, query: str, collection_names: List[str],
                                  student_program: str = None, student_year: str = None,
                                  top_k_per_collection: int = 8) -> List[Dict]:
        all_results = []
        
        major_chunks = int(self.config['retrieval']['major_catalogs_chunks'])
        minor_chunks = self.config['retrieval']['minor_catalogs_chunks']
        
        if 'major_catalogs' in collection_names:
            major_results = self.search_collection(
                query, 'major_catalogs', student_program, student_year, 
                top_k=major_chunks
            )
            all_results.extend(major_results)
        
        if 'minor_catalogs' in collection_names:
            minor_results = self.search_collection(
                query, 'minor_catalogs', student_program, student_year, top_k=minor_chunks
            )
            all_results.extend(minor_results)
        
        if '4_year_plans' in collection_names and student_program:
            best_year = self._find_best_4_year_plan_year(student_year, student_program)
            
            plan_results = self.search_collection(
                query, '4_year_plans', student_program, best_year, top_k=2 
            )
            all_results.extend(plan_results)
        
        if 'general_knowledge' in collection_names:
            used_chunks = len(all_results)
            remaining_slots = max(0, top_k_per_collection - used_chunks)
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
                       use_streaming: bool = True, test_mode: bool = False,
                       enable_reranking: bool = None) -> tuple:
        
        collections_to_search = []

        if student_program and student_year:
            collections_to_search.append(self.collections['major_catalogs'])
        else:
            collections_to_search = [
                self.collections['general_knowledge'],
                self.collections['major_catalogs']
            ]

        if student_program and self.config.get('retrieval', {}).get('4_year_plans_chunks', 0) > 0:
            collections_to_search.append(self.collections['4_year_plans'])

        minor_keywords = ['minor']
        if any(keyword in query.lower() for keyword in minor_keywords):
            collections_to_search.append(self.collections['minor_catalogs'])

        collections_to_search = list(dict.fromkeys(collections_to_search))

        retrieved_chunks = self.search_multiple_collections(
            query, collections_to_search, student_program, student_year, 
            top_k_per_collection=top_k
        )

        config_total = (
            int(self.config['retrieval']['major_catalogs_chunks']) + 
            int(self.config['retrieval']['minor_catalogs_chunks'])
        )
        max_chunks = max(config_total, top_k)
        retrieved_chunks = retrieved_chunks[:max_chunks]
        
        should_rerank = enable_reranking if enable_reranking is not None else not self.rerank_disabled
        
        if should_rerank and not self.rerank_disabled and retrieved_chunks:
            reranker = self._get_reranker()
            if reranker:
                try:
                    rerank_top_k = self.config.get('reranker', {}).get('top_k_rerank', 12)
                    retrieved_chunks = reranker.rerank(query, retrieved_chunks, top_k=rerank_top_k)
                except Exception as e:
                    print(f"Reranking failed: {e}")
        
        if not retrieved_chunks:
            return ("I don't have enough information to answer your question. "
                   "Please contact academic advising for assistance."), []
        
        if test_mode:
            return "Test mode: retrieval successful", retrieved_chunks
        
        context_parts = []
        for chunk in retrieved_chunks:
            text = chunk.get('text', chunk.get('chunk_text', ''))
            metadata = chunk['metadata']
            
            source_info = ""
            if metadata.get('file_name'):
                source_info = f"[Source: {metadata['file_name']}]"
            
            context_parts.append(f"{source_info} {text}")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Context from Chapman University's academic catalogs:

        {context}

        Student Question: {query}"""
        
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
