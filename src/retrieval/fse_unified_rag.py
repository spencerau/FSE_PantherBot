import os
import sys
from typing import List, Dict, Any, Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core_rag.retrieval import UnifiedRAG as BaseUnifiedRAG
from utils.config_loader import load_config


class FSEUnifiedRAG(BaseUnifiedRAG):
    
    def _init_query_router(self):
        try:
            from core_rag.retrieval.query_router import QueryRouter
        except ImportError as e:
            print(f"Warning: Query router disabled: {e}")
            self.query_router = None
            return
        
        try:
            from utils.ollama_api import get_intermediate_ollama_api
            intermediate_api = get_intermediate_ollama_api(timeout=30)
            self.query_router = QueryRouter(intermediate_api)
            print("Query router initialized with FSE config")
        except Exception as e:
            print(f"Warning: Query router initialization failed: {e}")
            self.query_router = None
    
    def _calculate_chunk_allocation(self, collection_names: List[str], query: str) -> Dict[str, int]:
        collection_max_chunks = self.config.get('retrieval', {}).get('collection_max_chunks', {})
        
        return {
            name: collection_max_chunks.get(name, 10)
            for name in collection_names
        }
    
    def search_collection(self, query: str, collection_name: str,
                         user_context: Dict = None, top_k: int = 5,
                         student_program: str = None, student_year: str = None,
                         student_minor: str = None, **kwargs) -> List[Dict]:
        if user_context:
            student_program = user_context.get('program', student_program)
            student_year = user_context.get('year', student_year)
            student_minor = user_context.get('minor', student_minor)
        
        final_context = {
            'program': student_program,
            'year': student_year,
            'minor': student_minor
        }
        final_context = {k: v for k, v in final_context.items() if v is not None}
        
        return super().search_collection(
            query=query,
            collection_name=collection_name,
            user_context=final_context if final_context else None,
            top_k=top_k,
            **kwargs
        )
    
    def answer_query(self, query: str, student_program: str = None, 
                    student_year: str = None, student_minor: str = None,
                    conversation_history: List[Dict] = None, **kwargs) -> Dict:
        return self.answer_question(
            query=query,
            student_program=student_program,
            student_year=student_year,
            student_minor=student_minor,
            conversation_history=conversation_history,
            **kwargs
        )
    
    def answer_question(self, query: str, student_program: str = None,
                       student_year: str = None, student_minor: str = None,
                       conversation_history: List[Dict] = None, **kwargs) -> Dict:
        user_context = {
            'program': student_program,
            'year': student_year,
            'minor': student_minor
        }
        user_context = {k: v for k, v in user_context.items() if v is not None}
        
        if 'use_streaming' in kwargs:
            kwargs['stream'] = kwargs.pop('use_streaming')
        
        return super().answer_question(
            query=query,
            user_context=user_context if user_context else None,
            conversation_history=conversation_history,
            **kwargs
        )
    
    def _dense_search(self, query: str, collection_name: str, 
                     user_context: Dict = None, top_k: int = 10,
                     document_type: str = None) -> List[Dict]:
        if user_context is None:
            user_context = {}
        user_context['_collection_name'] = collection_name
        
        metadata_only_collections = ['major_catalogs', 'minor_catalogs', '4_year_plans']
        
        if collection_name in metadata_only_collections and (user_context.get('program') or user_context.get('minor')):
            filter_obj = self._build_filter(user_context, document_type)
            collection = self.collections.get(collection_name, collection_name)
            
            if filter_obj:
                query_vector = self._get_embedding(query)
                
                scroll_results = self.client.scroll(
                    collection_name=collection,
                    scroll_filter=filter_obj,
                    limit=200,
                    with_payload=True,
                    with_vectors=True
                )
                
                if scroll_results and scroll_results[0]:
                    seen_texts = set()
                    unique_points = []
                    for point in scroll_results[0]:
                        text = point.payload.get('chunk_text', point.payload.get('text', ''))
                        if text and text not in seen_texts:
                            seen_texts.add(text)
                            unique_points.append(point)
                    
                    results = []
                    for point in unique_points:
                        if query_vector and point.vector:
                            score = sum(a * b for a, b in zip(query_vector, point.vector))
                        else:
                            score = 0.0
                        
                        text = point.payload.get('chunk_text', point.payload.get('text', ''))
                        results.append({
                            'text': text,
                            'score': score,
                            'metadata': {k: v for k, v in point.payload.items() if k != 'chunk_text'},
                            'collection': collection_name
                        })
                    
                    results.sort(key=lambda x: x['score'], reverse=True)
                    return results
        
        query_vector = self._get_embedding(query)
        if not query_vector:
            return []
        
        filter_obj = self._build_filter(user_context, document_type)
        collection = self.collections.get(collection_name, collection_name)
        
        results = self.client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=top_k,
            query_filter=filter_obj
        )
        
        return [{
            'text': hit.payload.get('chunk_text', hit.payload.get('text', '')),
            'score': hit.score,
            'metadata': {k: v for k, v in hit.payload.items() if k != 'chunk_text'},
            'collection': collection_name
        } for hit in results.points]
    
    def _hybrid_search(self, query: str, collection_name: str,
                      user_context: Dict = None, top_k: int = 10,
                      document_type: str = None, alpha: float = 0.5) -> List[Dict]:
        if user_context is None:
            user_context = {}
        user_context['_collection_name'] = collection_name
        
        dense_results = self._dense_search(query, collection_name, user_context, top_k, document_type)
        
        try:
            if self.bm25_retriever:
                sparse_results = self.bm25_retriever.search(
                    query=query,
                    collection_name=self.collections.get(collection_name, collection_name),
                    top_k=top_k
                )
                
                from core_rag.retrieval.fusion import HybridRetriever
                hybrid_retriever = HybridRetriever()
                fused_results = hybrid_retriever.reciprocal_rank_fusion(
                    dense_results, sparse_results, k=60
                )
                return fused_results[:top_k]
        except Exception as e:
            print(f"Hybrid search fallback to dense: {e}")
        
        return dense_results[:top_k]
    
    def _build_filter(self, user_context: Dict = None, 
                     document_type: str = None) -> Optional[Filter]:
        if not user_context:
            return super()._build_filter(user_context, document_type)
        
        collection_name = user_context.get('_collection_name')
        student_program = user_context.get('program')
        student_year = user_context.get('year')
        student_minor = user_context.get('minor')
        
        conditions = []
        subject_code_to_filter = None
        
        if collection_name == 'minor_catalogs' and student_minor:
            subject_code_to_filter = student_minor
            if hasattr(self, 'debug_info'):
                self.debug_info.append(f"Minor filter ({collection_name}): {subject_code_to_filter}")
                
        elif student_program and collection_name in ['major_catalogs', '4_year_plans']:
            subject_code_to_filter = student_program
            if hasattr(self, 'debug_info'):
                self.debug_info.append(f"Program filter ({collection_name}): {subject_code_to_filter}")
        
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
    
    def _find_best_4_year_plan_year(self, student_year: str, student_program: str) -> str:
        if not student_year or not student_program:
            return "2025"
        
        subject_code = self._normalize_program(student_program)
        
        try:
            year_int = int(student_year)
            
            scroll_result = self.client.scroll(
                collection_name="4_year_plans",
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="SubjectCode", match=MatchValue(value=subject_code))
                    ]
                ),
                limit=100
            )
            
            if not scroll_result or not scroll_result[0]:
                return "2025"
            
            available_years = set()
            for point in scroll_result[0]:
                if hasattr(point, 'payload') and point.payload:
                    year_value = point.payload.get('Year')
                    if year_value:
                        try:
                            available_years.add(int(year_value))
                        except (ValueError, TypeError):
                            continue
            
            if not available_years:
                return "2025"
            
            sorted_years = sorted(available_years, reverse=True)
            
            if year_int >= sorted_years[0]:
                return str(sorted_years[0])
            
            if year_int <= sorted_years[-1]:
                return str(sorted_years[-1])
            
            for plan_year in sorted_years:
                if year_int >= plan_year:
                    return str(plan_year)
            
            return str(sorted_years[0])
            
        except Exception as e:
            print(f"Error finding best 4-year plan year: {e}")
            return "2025"


UnifiedRAG = FSEUnifiedRAG
