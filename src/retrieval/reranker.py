import requests
import os
from typing import List, Dict, Tuple
from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api


class BGEReranker:
    
    def __init__(self):
        self.config = load_config()
        self.model = self.config.get('reranker', {}).get('model', 'BAAI/bge-reranker-v2-m3')
        self.top_k = self.config.get('reranker', {}).get('top_k', 5)
        self.batch_size = self.config.get('reranker', {}).get('batch_size', 32)
        self.ollama_api = get_ollama_api()
    
    def rerank(self, query: str, documents: List[Dict], top_k: int = None) -> List[Dict]:
        if not documents:
            return []
        
        if top_k is None:
            top_k = self.top_k
        
        pairs = []
        for doc in documents:
            pairs.append([query, doc.get('text', '')])
        
        try:
            scores = self._call_reranker_api(pairs)
            
            reranked_docs = []
            for i, doc in enumerate(documents):
                new_doc = doc.copy()
                if i < len(scores):
                    new_doc['rerank_score'] = scores[i]
                else:
                    new_doc['rerank_score'] = 0.0
                reranked_docs.append(new_doc)
            
            reranked_docs.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            return reranked_docs[:top_k]
            
        except Exception as e:
            print(f"Reranking failed, returning original order: {e}")
            return sorted(documents, key=lambda x: x.get('score', 0), reverse=True)[:top_k]
    
    def _call_reranker_api(self, pairs: List[List[str]]) -> List[float]:
        scores = []
        for query, text in pairs:
            score = self._calculate_simple_relevance(query, text)
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
            elif 'course' in collection or 'listing' in collection:
                doc['rerank_score'] *= course_weight
        
        reranked.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        return reranked


class SimpleReranker:
    
    def __init__(self):
        self.config = load_config()
        self.top_k = self.config.get('reranker', {}).get('top_k', 5)
    
    def rerank(self, query: str, documents: List[Dict], top_k: int = None) -> List[Dict]:
        if not documents:
            return []
        
        if top_k is None:
            top_k = self.top_k
        
        query_terms = query.lower().split()
        
        scored_docs = []
        for doc in documents:
            text = doc.get('text', '').lower()
            metadata = doc.get('metadata', {})
            
            base_score = doc.get('score', 0.0)
            
            tf_score = sum(text.count(term) for term in query_terms)
            tf_score = min(tf_score / 10.0, 1.0)
            
            type_boost = 0.0
            if any(keyword in query.lower() for keyword in ['requirement', 'degree', 'major']):
                if metadata.get('ProgramType') == 'major':
                    type_boost = 0.2
            elif any(keyword in query.lower() for keyword in ['course', 'schedule', 'offered']):
                if 'course' in doc.get('collection', '').lower():
                    type_boost = 0.2
            
            final_score = base_score + tf_score + type_boost
            
            doc_copy = doc.copy()
            doc_copy['rerank_score'] = final_score
            scored_docs.append(doc_copy)
        
        scored_docs.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        return scored_docs[:top_k]


def get_reranker():
    config = load_config()
    reranker_model = config.get('reranker', {}).get('model', 'simple')
    
    if 'bge' in reranker_model.lower():
        return BGEReranker()
    else:
        return SimpleReranker()


class Reranker(SimpleReranker):
    pass