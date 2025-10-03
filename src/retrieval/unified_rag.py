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
from retrieval.query_router import QueryRouter


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
        llm_timeout = self.config.get('llm', {}).get('timeout', 300)
        self.ollama_api = get_ollama_api(timeout=llm_timeout)
        
        self.hybrid_disabled = os.getenv('HYBRID_DISABLED', 'false').lower() == 'true'
        self.rerank_disabled = os.getenv('RERANK_DISABLED', 'false').lower() == 'true'
        
        try:
            self.query_router = QueryRouter(self.ollama_api)
        except Exception as e:
            print(f"Warning: Query router initialization failed: {e}")
            self.query_router = None
        
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
                chat_params = {
                    'model': self.config['llm']['model'],
                    'messages': [
                        {
                            'role': 'system',
                            'content': self.config['llm']['system_prompt']
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    'stream': False,
                    'hide_thinking': not show_thinking,
                    'options': {
                        'temperature': self.config['llm']['temperature'],
                        'top_p': self.config['llm']['top_p'],
                        'num_predict': self.config['llm']['max_tokens'],
                        'num_ctx': self.config['llm'].get('context_length', 4096),
                        **self.config['llm'].get('ollama_options', {})
                    }
                }
                
                if 'deepseek' in self.config['llm']['model'].lower():
                    chat_params['think'] = enable_thinking
                
                response = self.ollama_api.chat(**chat_params)
                return response
        except Exception as e:
            print(f"Error getting LLM response: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again later."
    
    def _get_llm_response_stream(self, prompt: str, enable_thinking: bool = True, 
                                show_thinking: bool = False):
        try:
            stream_params = {
                'model': self.config['llm']['model'],
                'messages': [
                    {
                        'role': 'system',
                        'content': self.config['llm']['system_prompt']
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'hide_thinking': not show_thinking,
                'options': {
                    'temperature': self.config['llm']['temperature'],
                    'top_p': self.config['llm']['top_p'],
                    'num_predict': self.config['llm']['max_tokens'],
                    'num_ctx': self.config['llm'].get('context_length', 4096),
                    **self.config['llm'].get('ollama_options', {})
                }
            }
            
            if 'deepseek' in self.config['llm']['model'].lower():
                stream_params['think'] = enable_thinking
            
            for chunk in self.ollama_api.chat_stream(**stream_params):
                yield chunk
        except Exception as e:
            print(f"Error getting streaming LLM response: {e}")
            yield "I apologize, but I'm experiencing technical difficulties. Please try again later."
    
    def _build_filter(self, student_program: str = None, student_year: str = None, 
                     document_type: str = None, student_minor: str = None, collection_name: str = None) -> Optional[Filter]:
        conditions = []
        
        subject_code_to_filter = None
        
        if collection_name == 'minor_catalogs' and student_minor:
            minor_code_mappings = {
                "analytics": "anal", "anal": "anal",
                "cs": "cs", "computer science": "cs",
                "ce": "ce", "computer engineering": "ce",
                "ee": "ee", "electrical engineering": "ee",
                "gamedev": "gamedev", "game development": "gamedev",
                "isp": "isp", "information security policy": "isp"
            }
            subject_code_to_filter = minor_code_mappings.get(student_minor.lower(), student_minor.lower())
            if hasattr(self, 'debug_info'):
                self.debug_info.append(f"Minor mapping ({collection_name}): {student_minor} -> {subject_code_to_filter}")
                
        elif student_program and collection_name in ['major_catalogs', '4_year_plans']:
            program_mappings = {
                'Computer Science': 'cs', 'CompSci': 'cs', 'cs': 'cs',
                'Computer Engineering': 'ce', 'CompEng': 'ce', 'ce': 'ce',
                'Electrical Engineering': 'ee', 'ElecEng': 'ee', 'ee': 'ee',
                'Software Engineering': 'se', 'SoftEng': 'se', 'se': 'se',
                'Data Science': 'ds', 'DataSci': 'ds', 'ds': 'ds',
                'Analytics': 'anal', 'anal': 'anal',
                'Game Development': 'gamedev', 'GameDev': 'gamedev', 'gamedev': 'gamedev',
                'Information Security Policy': 'isp', 'ISP': 'isp', 'isp': 'isp'
            }
            subject_code_to_filter = program_mappings.get(student_program, student_program.lower())
            if hasattr(self, 'debug_info'):
                self.debug_info.append(f"Program mapping ({collection_name}): {student_program} -> {subject_code_to_filter}")
        
        if subject_code_to_filter:
            conditions.append(
                FieldCondition(key="SubjectCode", match=MatchValue(value=subject_code_to_filter))
            )
        
        if student_year:
            if hasattr(self, 'debug_info'):
                self.debug_info.append(f"Year filter: {student_year} (type: {type(student_year)})")
            
            conditions.append(
                FieldCondition(
                    key="Year",
                    match=MatchValue(value=str(student_year))
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
            filter_obj = Filter(must=conditions)
            return filter_obj
        return None
    
    def search_collection(self, query: str, collection_name: str, 
                         student_program: str = None, student_year: str = None,
                         student_minor: str = None, top_k: int = 5) -> List[Dict]:
        try:
            if self.bm25_retriever and not self.hybrid_disabled:
                return self._hybrid_search(query, collection_name, student_program, student_year, student_minor, top_k)
            else:
                return self._dense_search(query, collection_name, student_program, student_year, student_minor, top_k)
        except Exception as e:
            print(f"Error searching collection {collection_name}: {e}")
            return []
    
    def _dense_search(self, query: str, collection_name: str, 
                     student_program: str = None, student_year: str = None,
                     student_minor: str = None, top_k: int = 5) -> List[Dict]:
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []
        
        filter_condition = self._build_filter(student_program, student_year, None, student_minor, collection_name)
        
        if hasattr(self, 'debug_info'):
            self.debug_info.append(f"Dense search filter: program={student_program}, year={student_year}, collection={collection_name}, filter={filter_condition}")
        
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
                      student_minor: str = None, top_k: int = 5) -> List[Dict]:
        k_dense = self.config.get('retrieval', {}).get('k_dense', 40)
        k_sparse = self.config.get('retrieval', {}).get('k_sparse', 40)
        
        dense_results = self._dense_search(query, collection_name, student_program, student_year, student_minor, k_dense)
        
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
        if not student_year or not student_program:
            return None
        
        student_year_str = str(student_year)
            
        available_years = ['2025', '2024', '2023']
        
        if student_year_str in available_years:
            return student_year_str
            
        student_year_int = int(student_year_str) if student_year_str.isdigit() else 0
        
        best_year = None
        for year in sorted(available_years):
            year_int = int(year)
            if year_int >= student_year_int:
                best_year = year
                break
        
        return best_year or available_years[0]
    
    def search_multiple_collections(self, query: str, collection_names: List[str],
                                  student_program: str = None, student_year: str = None,
                                  student_minor: str = None, top_k_per_collection: int = 8) -> List[Dict]:
        all_results = []
        
        chunk_allocation = self._calculate_dynamic_chunk_allocation(collection_names, query)
        
        for collection_name in collection_names:
            collection_id = collection_name if collection_name in ['major_catalogs', 'minor_catalogs', 'general_knowledge', '4_year_plans'] else collection_name
            chunks_for_this_collection = chunk_allocation.get(collection_name, self.config['retrieval']['min_chunks_per_collection'])
            
            if collection_name == 'major_catalogs':
                if hasattr(self, 'debug_info'):
                    self.debug_info.append(f"Major catalog search: program={student_program}, year={student_year}")
                
                results = self.search_collection(
                    query, collection_id, student_program, student_year, student_minor,
                    top_k=chunks_for_this_collection
                )
                
                if hasattr(self, 'debug_info'):
                    self.debug_info.append(f"Major catalog search results: {len(results)} chunks")
                    if results:
                        major_programs = set()
                        for r in results[:5]:
                            meta = r.get('metadata', {})
                            subject_code = meta.get('SubjectCode')
                            if subject_code:
                                major_programs.add(subject_code)
                        self.debug_info.append(f"Major catalog program codes found: {list(major_programs)}")
                
                all_results.extend(results)
            
            elif collection_name == 'minor_catalogs':
                if hasattr(self, 'debug_info'):
                    self.debug_info.append(f"Minor catalog search: program={student_program}, year={student_year}")
                
                results = self.search_collection(
                    query, collection_id, student_program, student_year, student_minor,
                    top_k=chunks_for_this_collection
                )
                
                if hasattr(self, 'debug_info'):
                    self.debug_info.append(f"Minor catalog search results: {len(results)} chunks")
                    if results:
                        minor_programs = set()
                        for r in results[:5]:
                            meta = r.get('metadata', {})
                            subject_code = meta.get('SubjectCode')
                            if subject_code:
                                minor_programs.add(subject_code)
                        self.debug_info.append(f"Minor catalog program codes found: {list(minor_programs)}")
                
                all_results.extend(results)
                
            elif collection_name == '4_year_plans':
                if student_program:
                    best_year = self._find_best_4_year_plan_year(student_year, student_program)
                    self.debug_info.append(f"4-year plan search: program={student_program}, year={student_year}, best_year={best_year}")
                    
                    test_filter = self._build_filter(student_program, best_year, None, None, '4_year_plans')
                    self.debug_info.append(f"Filter being applied: {test_filter}")
                    
                    results = self.search_collection(
                        query, collection_id, student_program, best_year, student_minor,
                        top_k=chunks_for_this_collection
                    )
                    self.debug_info.append(f"4-year plan search with filters: {len(results)} results")
                    
                    if not results and best_year:
                        self.debug_info.append(f"No results with program filter, trying year-only filter")
                        results = self.search_collection(
                            query, collection_id, student_program=None, student_year=best_year, student_minor=None,
                            top_k=chunks_for_this_collection
                        )
                        self.debug_info.append(f"4-year plan search with year-only: {len(results)} results")
                        
                        if results:
                            sample_metadata = results[0].get('metadata', {})
                            self.debug_info.append(f"Sample metadata from year-only results: {sample_metadata}")
                            
                            program_values = set()
                            file_names = []
                            for r in results[:5]:
                                meta = r.get('metadata', {})
                                subject_code = meta.get('SubjectCode')
                                if subject_code:
                                    program_values.add(subject_code)
                                if 'file_name' in meta:
                                    file_names.append(meta['file_name'])
                                    
                            self.debug_info.append(f"Files found: {file_names}")
                            self.debug_info.append(f"Program values found in metadata: {list(program_values)}")
                            
                            cs_documents = [r for r in results if r.get('metadata', {}).get('SubjectCode') == 'cs']
                            self.debug_info.append(f"CS documents found: {len(cs_documents)}")
                            if cs_documents:
                                cs_file = cs_documents[0].get('metadata', {}).get('file_name', 'unknown')
                                self.debug_info.append(f"CS file: {cs_file}")
                        
                        if results and student_program:
                            search_terms = {
                                'cs': ['cs', 'computer science', 'compsci'], 
                                'ce': ['ce', 'computer engineering', 'compeng'],
                                'ee': ['ee', 'electrical engineering', 'eleceng'],
                                'se': ['se', 'software engineering', 'softeng'],
                                'ds': ['ds', 'data science', 'datasci']
                            }.get(student_program.lower(), [student_program.lower()])
                            
                            filtered_results = []
                            for result in results:
                                meta = result.get('metadata', {})
                                subject_code = meta.get('SubjectCode', '')
                                text_fields = f"{subject_code} {meta.get('Subject', meta.get('subject', ''))} {meta.get('file_name', '')}".lower()
                                
                                if any(term in text_fields for term in search_terms):
                                    filtered_results.append(result)
                            
                            self.debug_info.append(f"Manual filtering found {len(filtered_results)} matching results")
                            if filtered_results:
                                results = filtered_results
                    
                    if not results:
                        self.debug_info.append(f"No results with filters, trying no filters")
                        results = self.search_collection(
                            query, collection_id, student_program=None, student_year=None, student_minor=None,
                            top_k=chunks_for_this_collection
                        )
                        self.debug_info.append(f"4-year plan search with no filters: {len(results)} results")
                else:
                    results = self.search_collection(
                        query, collection_id, student_program=None, student_year=student_year, student_minor=None,
                        top_k=chunks_for_this_collection
                    )
                    self.debug_info.append(f"4-year plan search (no program): {len(results)} results")
                all_results.extend(results)
                
            elif collection_name == 'general_knowledge':
                results = self.search_collection(
                    query, collection_id, student_program=None, student_year=None, student_minor=None,
                    top_k=chunks_for_this_collection
                )
                all_results.extend(results)
        
        return all_results
    
    def _calculate_dynamic_chunk_allocation(self, collection_names: List[str], query: str) -> Dict[str, int]:
        total_budget = self.config['retrieval']['total_retrieval_budget']
        min_chunks = self.config['retrieval']['min_chunks_per_collection'] 
        default_max_chunks = self.config['retrieval']['max_chunks_per_collection']
        weights = self.config['retrieval']['collection_weights']
        collection_max_chunks = self.config['retrieval'].get('collection_max_chunks', {})
        
        allocation = {}
        total_weight = sum(weights.get(col, 0.25) for col in collection_names)
        
        remaining_budget = total_budget
        
        for collection in collection_names:
            weight = weights.get(collection, 0.25)
            base_chunks = int((weight / total_weight) * total_budget)
            max_chunks = collection_max_chunks.get(collection, default_max_chunks)
            
            chunks = max(min_chunks, min(max_chunks, base_chunks))
            allocation[collection] = chunks
            remaining_budget -= chunks
        
        if remaining_budget > 0:
            priority_collections = self._get_priority_collections(collection_names, query)
            
            for collection in priority_collections:
                if remaining_budget <= 0:
                    break
                    
                current_allocation = allocation.get(collection, 0)
                max_chunks = collection_max_chunks.get(collection, default_max_chunks)
                if current_allocation < max_chunks:
                    additional = min(remaining_budget, max_chunks - current_allocation)
                    allocation[collection] += additional
                    remaining_budget -= additional
        
        return allocation
    
    def _get_priority_collections(self, collection_names: List[str], query: str) -> List[str]:
        query_lower = query.lower()
        priority_order = []
        
        if any(word in query_lower for word in ['major', 'degree', 'graduation', 'requirement', 'prerequisite']):
            if 'major_catalogs' in collection_names:
                priority_order.append('major_catalogs')
        
        if any(word in query_lower for word in ['year', 'semester', 'sequence', 'freshman', 'sophomore', 'plan']):
            if '4_year_plans' in collection_names:
                priority_order.append('4_year_plans')
        
        if any(word in query_lower for word in ['minor']):
            if 'minor_catalogs' in collection_names:
                priority_order.append('minor_catalogs')
        
        if any(word in query_lower for word in ['policy', 'registration', 'deadline', 'gpa']):
            if 'general_knowledge' in collection_names:
                priority_order.append('general_knowledge')
        
        for col in collection_names:
            if col not in priority_order:
                priority_order.append(col)
        
        return priority_order
        
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        return all_results
    
    def answer_question(self, query: str, conversation_history: List[Dict] = None,
                       student_program: str = None, student_year: str = None, 
                       student_minor: str = None, top_k: int = 10, enable_thinking: bool = True, 
                       show_thinking: bool = False, use_streaming: bool = True, 
                       test_mode: bool = False, enable_reranking: bool = None, 
                       routing_method: str = None, return_debug_info: bool = False) -> tuple:
        
        try:
            self.debug_info = []
            if routing_method is None:
                routing_method = self.config.get('query_router', {}).get('routing_method', 'hybrid')
            
            if self.query_router:
                collection_names = self.query_router.route_query(
                    query, conversation_history, student_program, student_year, student_minor, method=routing_method
                )
                self.debug_info.append(f"Query router found collections: {collection_names}")
                
                if '4_year_plans' in collection_names and 'major_catalogs' not in collection_names:
                    collection_names.append('major_catalogs')
                    self.debug_info.append(f"Added major_catalogs since 4-year plans were requested")
                
                if student_minor and 'minor_catalogs' not in collection_names:
                    collection_names.append('minor_catalogs')
                    self.debug_info.append(f"Added minor_catalogs for student minor: {student_minor}")
                
                collections_to_search = []
                for name in collection_names:
                    if name in self.collections:
                        collections_to_search.append(self.collections[name])
                    else:
                        self.debug_info.append(f"Collection '{name}' not found in available collections: {list(self.collections.keys())}")
                self.debug_info.append(f"Collections to search: {len(collections_to_search)} collections")
            else:
                collections_to_search = []

                if student_program and student_year:
                    collections_to_search.append(self.collections['major_catalogs'])
                else:
                    collections_to_search = [
                        self.collections['general_knowledge'],
                        self.collections['major_catalogs']
                    ]

                if student_program:
                    collections_to_search.append(self.collections['4_year_plans'])

                if student_minor:
                    collections_to_search.append(self.collections['minor_catalogs'])

                specific_plan_keywords = [
                    'sequence', 'schedule', 'plan', 'course sequence', 'timeline',
                    'roadmap', 'pathway', 'progression', 'recommended order',
                    'create a plan', 'chemistry track', 'track',
                    '4 year plan', 'freshman year', 'sophomore year', 'junior year', 'senior year',
                    'first year', 'second year', 'when should i take'
                ]
                if any(keyword in query.lower() for keyword in specific_plan_keywords):
                    if self.collections['4_year_plans'] not in collections_to_search:
                        collections_to_search.append(self.collections['4_year_plans'])

                minor_keywords = ['minor']
                if any(keyword in query.lower() for keyword in minor_keywords):
                    collections_to_search.append(self.collections['minor_catalogs'])

            collections_to_search = list(dict.fromkeys(collections_to_search))

            retrieved_chunks = self.search_multiple_collections(
                query, collections_to_search, student_program, student_year, student_minor,
                top_k_per_collection=top_k
            )
            self.debug_info.append(f"Initial retrieval found {len(retrieved_chunks)} chunks")

            total_budget = self.config['retrieval']['total_retrieval_budget']
            initial_top_k = self.config.get('retrieval', {}).get('initial_top_k', 20)
            max_chunks = max(total_budget, initial_top_k)
            retrieved_chunks = retrieved_chunks[:max_chunks]
            self.debug_info.append(f"After budget limit: {len(retrieved_chunks)} chunks")
            
            should_rerank = enable_reranking if enable_reranking is not None else not self.rerank_disabled
            
            if should_rerank and not self.rerank_disabled and retrieved_chunks:
                reranker = self._get_reranker()
                if reranker:
                    try:
                        final_top_k = self.config.get('retrieval', {}).get('final_top_k', 15)
                        retrieved_chunks = reranker.rerank(query, retrieved_chunks, top_k=final_top_k)
                        self.debug_info.append(f"After reranking: {len(retrieved_chunks)} chunks")
                    except Exception as e:
                        self.debug_info.append(f"Reranking failed: {e}")
            
            self.debug_info.append(f"Final retrieved chunks: {len(retrieved_chunks)}")
            if not retrieved_chunks:
                error_msg = ("I don't have enough information to answer your question. "
                           "Please contact academic advising for assistance.")
                if return_debug_info:
                    return error_msg, [], self.debug_info
                else:
                    return error_msg, []
            
            if test_mode:
                if return_debug_info:
                    return "Test mode: retrieval successful", retrieved_chunks, self.debug_info
                else:
                    return "Test mode: retrieval successful", retrieved_chunks
            
            context_parts = []
            for chunk in retrieved_chunks:
                try:
                    text = chunk.get('text', chunk.get('chunk_text', ''))
                    text = text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                    metadata = chunk.get('metadata', {})
                    
                    source_info = ""
                    if isinstance(metadata, dict) and metadata.get('file_name'):
                        source_info = f"[Source: {metadata['file_name']}]"
                    
                    context_parts.append(f"{source_info} {text}")
                except Exception as e:
                    self.debug_info.append(f"Error processing chunk: {e}")
                    self.debug_info.append(f"Chunk type: {type(chunk)}")
                    self.debug_info.append(f"Chunk content: {chunk}")
                    continue
            
            context = "\n\n".join(context_parts)
            
            prompt = f"""Context from Chapman University's academic catalogs:

            {context}

            Student Question: {query}"""
            
            answer = self._get_llm_response(prompt, enable_thinking=enable_thinking, 
                                           show_thinking=show_thinking, use_streaming=use_streaming)
            
            if return_debug_info:
                return answer, retrieved_chunks, self.debug_info
            else:
                return answer, retrieved_chunks
            
        except Exception as e:
            self.debug_info.append(f"Error in answer_question: {e}")
            import traceback
            self.debug_info.append(f"Traceback: {traceback.format_exc()}")
            if return_debug_info:
                return f"I'm sorry, I encountered an error while processing your question: {str(e)}", [], self.debug_info
            else:
                return f"I'm sorry, I encountered an error while processing your question: {str(e)}", []
    
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
