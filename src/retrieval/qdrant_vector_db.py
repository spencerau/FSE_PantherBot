from old.embeddings import qdrant, COLLECTION, embed_texts
from qdrant_client import models

class QdrantVectorDB:
    def __init__(self, collection=COLLECTION):
        self.collection = collection
        self.qdrant = qdrant

    def search(self, query, top_k=5, filters=None):
        """
        Search for relevant chunks in the vector database.
        
        Args:
            query: The search query
            top_k: Number of results to return
            filters: Dictionary of filters to apply
        """
        query_emb = embed_texts([query])[0]
        
        search_filter = None
        if filters:
            filter_conditions = []
            
            for key, value in filters.items():
                filter_conditions.append(
                    models.FieldCondition(
                        key=f"metadata.{key}",
                        match=models.MatchValue(value=value)
                    )
                )
            
            if filter_conditions:
                search_filter = models.Filter(must=filter_conditions)
        
        hits = self.qdrant.search(
            collection_name=self.collection,
            query_vector=query_emb,
            limit=top_k,
            query_filter=search_filter
        )
        
        return [
            {
                'text': hit.payload.get('text', ''), 
                'score': hit.score,
                'metadata': hit.payload.get('metadata', {})
            }
            for hit in hits
        ]
