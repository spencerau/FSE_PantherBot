import os
import math
from typing import List, Dict, Any
from utils.config_loader import load_config


class BGEReranker:
    def __init__(self):
        self.config = load_config()
        self.model_name = self.config.get('reranker', {}).get('model', 'BAAI/bge-reranker-v2-m3')
        self.top_k = self.config.get('reranker', {}).get('top_k_rerank', 12)
        self.batch_size = self.config.get('reranker', {}).get('batch_size', 32)
        self.max_candidates = self.config.get('reranker', {}).get('max_candidates_for_rerank', 200)
        self.activation = self.config.get('reranker', {}).get('activation', 'sigmoid')
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name, trust_remote_code=True)
        except ImportError:
            print("sentence-transformers not available, using fallback reranker")
            self.model = None
    
    def rerank(self, query: str, documents: List[Dict], top_k: int = None) -> List[Dict]:
        if not documents:
            return []
        
        if top_k is None:
            top_k = self.top_k
        
        candidates = documents[:self.max_candidates]
        
        if self.model is not None:
            scores = self._rerank_with_model(query, candidates)
        else:
            scores = self._fallback_rerank(query, candidates)
        
        reranked_docs = []
        for i, doc in enumerate(candidates):
            new_doc = doc.copy()
            new_doc['rerank_score'] = scores[i] if i < len(scores) else 0.0
            reranked_docs.append(new_doc)
        
        reranked_docs.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        return reranked_docs[:top_k]
    
    def _rerank_with_model(self, query: str, documents: List[Dict]) -> List[float]:
        pairs = [[query, doc.get('text', '')] for doc in documents]
        
        all_scores = []
        for i in range(0, len(pairs), self.batch_size):
            batch_pairs = pairs[i:i + self.batch_size]
            batch_scores = self.model.predict(batch_pairs)
            
            if self.activation == 'sigmoid':
                batch_scores = [1 / (1 + math.exp(-score)) for score in batch_scores]
            
            all_scores.extend(batch_scores)
        
        return all_scores
    
    def _fallback_rerank(self, query: str, documents: List[Dict]) -> List[float]:
        scores = []
        for doc in documents:
            score = self._calculate_simple_relevance(query, doc.get('text', ''))
            scores.append(score)
        return scores
    
    def _calculate_simple_relevance(self, query: str, text: str) -> float:
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = len(query_words.intersection(text_words))
        union = len(query_words.union(text_words))
        
        if union == 0:
            return 0.0
        
        jaccard_score = intersection / union
        
        query_lower = query.lower()
        text_lower = text.lower()
        
        phrase_boost = 0.0
        if query_lower in text_lower:
            phrase_boost = 0.3
        
        academic_terms = [
            'requirement', 'prerequisite', 'course', 'credit', 'gpa', 
            'degree', 'major', 'minor', 'graduation', 'semester'
        ]
        
        academic_boost = 0.0
        for term in academic_terms:
            if term in query_lower and term in text_lower:
                academic_boost += 0.1
        
        academic_boost = min(academic_boost, 0.2)
        
        return min(jaccard_score + phrase_boost + academic_boost, 1.0)
    
    def rerank_with_weights(self, query: str, documents: List[Dict], 
                           pdf_weight: float = 1.0, course_weight: float = 1.0) -> List[Dict]:
        reranked = self.rerank(query, documents)
        
        for doc in reranked:
            metadata = doc.get('metadata', {})
            collection = doc.get('collection', '')
            
            if 'major' in collection or 'minor' in collection:
                doc['rerank_score'] *= pdf_weight
            elif 'course' in collection:
                doc['rerank_score'] *= course_weight
        
        reranked.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        return reranked