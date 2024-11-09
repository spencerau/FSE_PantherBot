import faiss
import numpy as np
from model_managers.llama_manager import LLaMAManager

class RAGPipeline:
    def __init__(self, index_path="data/retrieval_index/faiss_index", model_name="llama3.2"):
        # Load the FAISS index
        self.index = faiss.read_index(index_path)
        self.documents = []  # Load document texts from your knowledge base
        self.model = LLaMAManager(model_name=model_name)

    def retrieve(self, query, top_k=5):
        query_embedding = self.model.embed_text(query)
        query_embedding = np.array(query_embedding).astype("float32").reshape(1, -1)
        distances, indices = self.index.search(query_embedding, top_k)
        retrieved_docs = [self.documents[i] for i in indices[0]]
        return "\n".join(retrieved_docs)

    def generate_answer(self, question):
        context = self.retrieve(question)
        prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
        return self.model.generate_response(prompt)