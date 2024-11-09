from src.retrieval.rag_pipeline import RAGPipeline

def test_rag_pipeline():
    pipeline = RAGPipeline(model_name="llama3.2")
    question = "What is Chapman University known for?"
    answer = pipeline.generate_answer(question)
    print("Answer:", answer)

if __name__ == "__main__":
    test_rag_pipeline()