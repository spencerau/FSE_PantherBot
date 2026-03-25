import os
import sys
from textwrap import dedent
from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_rag.retrieval import UnifiedRAG as BaseUnifiedRAG
from core_rag.retrieval.llm_handler import LLMHandler, format_system_prompt
from core_rag.retrieval.search import SearchEngine
from core_rag.retrieval.answer import AnswerGenerator
from core_rag.retrieval.context_formatter import format_context
from core_rag.utils.docstore import get_docstore
from fse_utils.config_loader import load_config
from fse_utils.ollama_api import get_ollama_api

_CATALOG_COLLECTIONS = frozenset({'major_catalogs', 'minor_catalogs', '4_year_plans'})


class FSEUnifiedRAG(BaseUnifiedRAG):

    def __init__(self):
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=self.config['qdrant']['timeout']
        )
        self.embedding_model = self.config['embedding']['model']
        self.collections = self.config['qdrant']['collections']
        self.ollama_api = get_ollama_api(timeout=self.config.get('llm', {}).get('timeout', 300))
        self.docstore = get_docstore()
        self.hybrid_disabled = os.getenv('HYBRID_DISABLED', 'false').lower() == 'true'
        self.rerank_disabled = os.getenv('RERANK_DISABLED', 'false').lower() == 'true'

        summary_cfg = self.config.get('summary', {})
        self.enable_summary_gating = summary_cfg.get('enable_summary_gating', False)
        self.summary_top_n = summary_cfg.get('summary_top_n', 5)
        self.return_parent_docs = summary_cfg.get('return_parent_docs', False)

        self._init_bm25()
        self._init_query_router()
        self._init_summary_retriever()
        self.reranker = None

        self.search_engine = SearchEngine(
            self.client, self.config, self.collections, self.ollama_api,
            self.embedding_model, self.bm25_retriever, self.hybrid_disabled
        )
        self.system_prompt = format_system_prompt(self.config)
        self.llm_handler = LLMHandler(self.config, self.ollama_api, self.system_prompt)
        self.answer_gen = AnswerGenerator(
            self.config, self.search_engine, self.llm_handler,
            self._get_reranker, self.query_router, self.summary_retriever,
            self.docstore, self.enable_summary_gating, self.summary_top_n,
            self.return_parent_docs, self.rerank_disabled
        )

    def _calculate_chunk_allocation(self, collection_names: List[str], query: str) -> Dict[str, int]:
        collection_max_chunks = self.config.get('retrieval', {}).get('collection_max_chunks', {})
        return {name: collection_max_chunks.get(name, 10) for name in collection_names}

    def search_collection(self, query: str, collection_name: str,
                         user_context: Dict = None, top_k: int = 5,
                         student_program: str = None, student_year: str = None,
                         student_minor: str = None, **kwargs) -> List[Dict]:
        if user_context:
            student_program = user_context.get('program', student_program)
            student_year = user_context.get('year', student_year)
            student_minor = user_context.get('minor', student_minor)
        final_context = {k: v for k, v in {
            'program': student_program,
            'year': student_year,
            'minor': student_minor,
        }.items() if v is not None}
        return self._dense_search(
            query=query,
            collection_name=collection_name,
            user_context=final_context if final_context else None,
            top_k=top_k,
            document_type=kwargs.get('document_type'),
        )

    def answer_question(self, query: str, student_program: str = None,
                       student_year: str = None, student_minor: str = None,
                       conversation_history: List[Dict] = None, **kwargs) -> Any:
        user_context = {k: v for k, v in {
            'program': student_program,
            'year': student_year,
            'minor': student_minor,
        }.items() if v is not None}

        if 'use_streaming' in kwargs:
            kwargs['stream'] = kwargs.pop('use_streaming')

        stream               = kwargs.get('stream', False)
        enable_thinking      = kwargs.get('enable_thinking', True)
        show_thinking        = kwargs.get('show_thinking', False)
        enable_reranking     = kwargs.get('enable_reranking', None)
        return_debug_info    = kwargs.get('return_debug_info', False)
        selected_collections = kwargs.get('selected_collections', None)

        ctx = user_context or None

        if self.query_router and not selected_collections:
            route_result = self.query_router.route_query(
                query, conversation_history=conversation_history, user_context=ctx
            )
            collection_names = route_result['collections']
            token_allocation = route_result['token_allocation']
        else:
            collection_names = selected_collections or list(self.collections.keys())
            token_allocation = self.config.get('llm', {}).get('default_tokens', 600)

        chunk_allocation = self._calculate_chunk_allocation(collection_names, query)
        catalog_results: List[Dict] = []
        other_results:   List[Dict] = []

        for coll_name in collection_names:
            results = self.search_collection(query, coll_name, ctx, chunk_allocation.get(coll_name, 10))
            if coll_name in _CATALOG_COLLECTIONS:
                catalog_results.extend(results)
            else:
                other_results.extend(results)

        if enable_reranking is None:
            enable_reranking = not self.rerank_disabled

        non_catalog_cap = (
            self.config.get('retrieval', {})
                        .get('collection_max_chunks', {})
                        .get('general_knowledge', 25)
        )
        if enable_reranking and other_results:
            reranker = self._get_reranker()
            other_results = reranker.rerank(query, other_results, top_k=non_catalog_cap) if reranker else other_results[:non_catalog_cap]
        else:
            other_results = other_results[:non_catalog_cap]

        all_chunks = catalog_results + other_results

        if not all_chunks:
            msg = "I couldn't find relevant information to answer your question."
            if stream:
                def _err():
                    yield msg
                return (_err(), [], {}) if return_debug_info else _err()
            return (msg, [], {}) if return_debug_info else msg

        context = format_context(all_chunks, self.config)

        if enable_thinking and show_thinking:
            prompt = dedent(f"""
                Context:
                {context}

                Question: {query}

                Please think through your answer step by step, then provide your final response.

                Thinking: [Show your reasoning process here]

                Answer: [Provide your final answer here]
            """).strip()
        elif enable_thinking:
            prompt = dedent(f"""
                Context:
                {context}

                Question: {query}

                Think through your answer carefully using the provided context, then provide a clear and concise response.

                Answer:
            """).strip()
        else:
            prompt = dedent(f"""
                Context:
                {context}

                Question: {query}

                Answer:
            """).strip()

        if stream:
            gen = self.llm_handler.get_response_stream(prompt, conversation_history, token_allocation)
            return (gen, all_chunks, {}) if return_debug_info else gen

        answer = self.llm_handler.get_response(prompt, conversation_history, token_allocation)
        return (answer, all_chunks, {}) if return_debug_info else answer

    def _dense_search(self, query: str, collection_name: str,
                     user_context: Dict = None, top_k: int = 10,
                     document_type: str = None) -> List[Dict]:
        if user_context is None:
            user_context = {}
        user_context['_collection_name'] = collection_name

        if collection_name in _CATALOG_COLLECTIONS and (user_context.get('program') or user_context.get('minor')):
            filter_obj = self._build_filter(user_context, document_type)
            collection = self.collections.get(collection_name, collection_name)

            if filter_obj:
                query_vector = self.search_engine.get_embedding(query)
                scroll_results = self.client.scroll(
                    collection_name=collection,
                    scroll_filter=filter_obj,
                    limit=500,
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
                        score = sum(a * b for a, b in zip(query_vector, point.vector)) if query_vector and point.vector else 0.0
                        text = point.payload.get('chunk_text', point.payload.get('text', ''))
                        results.append({
                            'text': text,
                            'score': score,
                            'metadata': {k: v for k, v in point.payload.items() if k != 'chunk_text'},
                            'collection': collection_name
                        })
                    results.sort(key=lambda x: x['score'], reverse=True)
                    return results

        query_vector = self.search_engine.get_embedding(query)
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

    def _build_filter(self, user_context: Dict = None,
                     document_type: str = None) -> Optional[Filter]:
        if not user_context:
            return self.search_engine.build_filter(user_context, document_type)

        collection_name = user_context.get('_collection_name')
        student_program = user_context.get('program')
        student_year    = user_context.get('year')
        student_minor   = user_context.get('minor')

        conditions = []

        if collection_name == 'minor_catalogs' and student_minor:
            subject_code = student_minor
        elif student_program and collection_name in ('major_catalogs', '4_year_plans'):
            subject_code = student_program
        else:
            subject_code = None

        if subject_code:
            conditions.append(FieldCondition(key="SubjectCode", match=MatchValue(value=subject_code)))

        if student_year and collection_name in ('major_catalogs', '4_year_plans'):
            conditions.append(FieldCondition(key="Year", match=MatchValue(value=str(student_year))))

        if document_type:
            conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=document_type)))

        return Filter(must=conditions) if conditions else None


UnifiedRAG = FSEUnifiedRAG
