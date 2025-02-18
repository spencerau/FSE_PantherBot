# Configuration Guide for DeepSeek RAG System

This document explains each parameter in the `config.yaml` file used for configuring the DeepSeek-based Retrieval-Augmented Generation (RAG) system.

## **🔹 DeepSeek Model Configuration**

The `deepseek` section defines parameters for the DeepSeek language model, controlling its response behavior.

```yaml
deepseek:
  model_name: "deepseek-r1:7b"
  # Controls randomness in model responses. Lower = more deterministic, higher = more creative.
  temperature: 0.1
  # Top-P (Nucleus Sampling): Limits the probability mass of words chosen. Lower values make responses more focused.
  top_p: 0.6
  # Maximum length of model responses. The model will not generate more than 2000 tokens.
  max_tokens: 2000
```

### **Parameter Explanations**

- `` → Specifies the DeepSeek model version (`7b` refers to a 7-billion parameter model).
- `` → Controls randomness in responses.
  - `0.0` = Fully deterministic (model always gives the same answer for the same input).
  - `1.0` = Highly random (model can generate varied responses).
  - **Recommended**: `0.1` (Keeps responses factual and consistent.)
- `` → Nucleus sampling for token probability selection.
  - `0.5-0.7` ensures the model picks from only the most relevant words.
  - **Recommended**: `0.6` (Balances accuracy and variety.)
- `` → Defines the maximum number of tokens generated in a response.
  - **2000 tokens** ensures responses stay relevant without being too long.

---

## **🔹 LangChain Chunking & Prompt Settings**

The `langchain` section defines how documents are processed and split before being sent to the LLM.

```yaml
langchain:
  # Defines the max size (characters) of each chunk before it is sent to the LLM.
  chunk_size: 3000
  # Overlapping buffer between chunks to preserve context across splits.
  chunk_overlap: 300
  # Template for how the LLM should respond. Uses {question} and {context} placeholders.
  prompt: |
    <s> You are an AI assistant for Academic Advising at Chapman University assisting students with choosing courses as well as developing four year plans, etc. Answer the question based on the given context.
    If you don’t know the answer, say "I don't know." The major and minor catalog of varying dates corresponds to the date the student has joined the University.
    For example, if a student joined in 2020, then their course catalog would be the 2020-2021 one. </s>

    Question: {question}
    Context: {context}
    Answer:
```

### **Parameter Explanations**

- `` → Defines how much text (in characters) is sent to the model at a time.
  - **Recommended**: `3000` (Ensures a good balance of context retention and token limits.)
- `` → Overlapping buffer between chunks for context preservation.
  - **Recommended**: `300` (Ensures responses don’t lose important information between chunks.)
- `` → Defines the prompt template provided to the model for structured responses.
  - `{question}` and `{context}` are placeholders for dynamically inserted text.
  - **Adjust wording** to influence how the model prioritizes information.

---

## **🔹 ChromaDB Configuration**

The `chroma` section defines settings for storing and retrieving vector embeddings in ChromaDB.

```yaml
chroma:
  # Directory where vector embeddings (converted from text) are stored.
  persist_directory: "vector_db"
  # Number of most relevant document chunks to retrieve per query.
  top_k: 7
```

### **Parameter Explanations**

- `` → Defines where the vector database is stored.
  - **Recommended**: `"vector_db"` (Ensures persistence between sessions.)
- `` → Determines how many document chunks to retrieve per query.
  - **Recommended**: `7` (Balances relevance and response accuracy.)

---

## **🚀 How to Use**

1. Modify `config.yaml` as needed.
2. Ensure `config.yaml` is placed in the project’s root directory.
3. Run the program, and it will **automatically load the values** from `config.yaml`.

---