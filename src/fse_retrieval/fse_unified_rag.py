import os
import sys
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_rag.retrieval import UnifiedRAG as BaseUnifiedRAG
from core_rag.retrieval.llm_handler import LLMHandler, format_system_prompt
from core_rag.retrieval.search import SearchEngine
from core_rag.retrieval.answer import AnswerGenerator
from core_rag.utils.docstore import get_docstore
from fse_utils.config_loader import load_config
from core_rag.utils.llm_api import get_ollama_api, get_intermediate_ollama_api

_CATALOG_COLLECTIONS = frozenset({'major_catalogs', 'minor_catalogs', '4_year_plans'})


class FSEUnifiedRAG(BaseUnifiedRAG):

    def __init__(self):
        # Do NOT call super().__init__() — core_rag's config loader resolves to the wrong
        # configs directory. Build components manually with PantherBot's load_config().
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=self.config['qdrant']['timeout'],
        )
        self.embedding_model = self.config['embedding']['model']
        self.collections = self.config['qdrant']['collections']
        self.ollama_api = get_ollama_api(timeout=self.config.get('llm', {}).get('timeout', 300))
        self.docstore = get_docstore()
        self.hybrid_disabled = os.getenv('HYBRID_DISABLED', 'false').lower() == 'true'
        self.rerank_disabled = os.getenv('RERANK_DISABLED', 'false').lower() == 'true'
        self.reranker = None
        self.bm25_retriever = None
        self.summary_retriever = None

        self._init_query_router()
        self._init_summary_retriever()

        coll_cfg = self.config.get('collection_config', {})
        enable_summary_gating = any(v.get('summary_enabled', False) for v in coll_cfg.values())
        summary_top_n = self.config.get('summary', {}).get('summary_top_n', 5)

        self.search_engine = SearchEngine(
            self.client, self.config, self.collections, self.ollama_api,
            self.embedding_model, self.bm25_retriever, self.hybrid_disabled,
        )
        self.system_prompt = format_system_prompt(self.config)
        self.llm_handler = LLMHandler(self.config, self.ollama_api, self.system_prompt)
        self.answer_gen = AnswerGenerator(
            self.config, self.search_engine, self.llm_handler, self._get_reranker,
            query_router=self.query_router,
            summary_retriever=self.summary_retriever,
            docstore=self.docstore,
            enable_summary_gating=enable_summary_gating,
            summary_top_n=summary_top_n,
            rerank_disabled=self.rerank_disabled,
            search_fn=self.search_collection,
        )

    def _init_query_router(self):
        self.query_router = None
        try:
            from core_rag.retrieval.query_router import QueryRouter
            int_llm = self.config.get('intermediate_llm', {})
            ollama_api = get_intermediate_ollama_api(timeout=int_llm.get('timeout', 30))
            self.query_router = QueryRouter(ollama_api)
            self.query_router.config = self.config
            self.query_router._prompt_template = int_llm.get('prompt_template', '').strip()
            print("Query router initialized")
        except Exception as e:
            print(f"Warning: Query router disabled: {e}")

    def _init_summary_retriever(self):
        self.summary_retriever = None
        coll_cfg = self.config.get('collection_config', {})
        if not any(v.get('summary_enabled', False) for v in coll_cfg.values()):
            return
        try:
            from core_rag.summary import SummaryRetriever
            if SummaryRetriever is None:
                return
            sr = SummaryRetriever.__new__(SummaryRetriever)
            sr.config = self.config
            sr.client = self.client
            sr.embedding_model = self.embedding_model
            sr.ollama_api = self.ollama_api
            sr.docstore = self.docstore
            sr.collections = self.collections
            sr.summary_top_n = self.config.get('summary', {}).get('summary_top_n', 5)
            self.summary_retriever = sr
            print("Summary retriever initialized")
        except Exception as e:
            print(f"Warning: Summary retriever disabled: {e}")

    def _get_reranker(self):
        if self.reranker is None and not self.rerank_disabled:
            try:
                from core_rag.retrieval.reranker import BGEReranker
                print("Initializing reranker...")
                self.reranker = BGEReranker()
            except Exception as e:
                print(f"Reranker initialization failed: {e}")
                self.reranker = False
        return self.reranker if self.reranker is not False else None

    def search_collection(self, query: str, collection_name: str,
                          user_context: Dict = None, top_k: int = 10,
                          **kwargs) -> List[Dict]:
        return self._dense_search(
            query=query,
            collection_name=collection_name,
            user_context=user_context,
            top_k=top_k,
            document_type=kwargs.get('document_type'),
        )

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
                    with_vectors=True,
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
                        score = (
                            sum(a * b for a, b in zip(query_vector, point.vector))
                            if query_vector and point.vector else 0.0
                        )
                        text = point.payload.get('chunk_text', point.payload.get('text', ''))
                        results.append({
                            'text': text,
                            'score': score,
                            'metadata': {k: v for k, v in point.payload.items() if k != 'chunk_text'},
                            'collection': collection_name,
                        })
                    results.sort(key=lambda x: x['score'], reverse=True)

                    coll_cfg = self.config.get('collection_config', {}).get(collection_name, {})
                    if coll_cfg.get('hybrid_enabled') and not self.hybrid_disabled and results:
                        results = self._fuse_with_bm25(query, results)

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
            query_filter=filter_obj,
        )
        return [{
            'text': hit.payload.get('chunk_text', hit.payload.get('text', '')),
            'score': hit.score,
            'metadata': {k: v for k, v in hit.payload.items() if k != 'chunk_text'},
            'collection': collection_name,
        } for hit in results.points]

    def _fuse_with_bm25(self, query: str, chunks: List[Dict]) -> List[Dict]:
        from core_rag.retrieval.bm25 import BM25
        from core_rag.retrieval.fusion import reciprocal_rank_fusion
        try:
            bm25 = BM25()
            bm25.fit([c['text'] for c in chunks])
            bm25_raw = bm25.search(query, top_k=len(chunks))
            dense = [dict(c, doc_id=i) for i, c in enumerate(chunks)]
            sparse = [dict(chunks[r['doc_id']], doc_id=r['doc_id'], score=r['score'])
                      for r in bm25_raw if r['doc_id'] < len(chunks)]
            return reciprocal_rank_fusion(dense, sparse, k=60)
        except Exception as e:
            print(f"BM25 fusion failed, using dense only: {e}")
            return chunks

    def _build_filter(self, user_context: Dict = None,
                      document_type: str = None) -> Optional[Filter]:
        if not user_context:
            return None

        collection_name = user_context.get('_collection_name')
        student_program = user_context.get('program')
        student_year = user_context.get('year')
        student_minor = user_context.get('minor')

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

    def answer_question(self, query: str, student_program: str = None,
                        student_year: str = None, student_minor: str = None,
                        conversation_history: List[Dict] = None, **kwargs) -> Any:
        if 'use_streaming' in kwargs:
            kwargs['stream'] = kwargs.pop('use_streaming')
        user_context = {k: v for k, v in {
            'program': student_program,
            'year': student_year,
            'minor': student_minor,
        }.items() if v is not None}
        return self.answer_gen.answer_question(
            query, conversation_history=conversation_history,
            user_context=user_context or None, **kwargs
        )


UnifiedRAG = FSEUnifiedRAG
