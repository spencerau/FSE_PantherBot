# Configuration Guide for DeepSeek RAG System

This document explains each parameter in the `config.yaml` file used for configuring the DeepSeek-based Retrieval-Augmented Generation (RAG) system.

## **DeepSeek Model Configuration**

The `deepseek` section defines parameters for the DeepSeek language model, controlling its response behavior.

```yaml
model_llm:
  model_name: "deepseek-r1:1.5b"
  # Controls randomness in model responses. Lower = more deterministic, higher = more creative.
  temperature: 0.1
  # Top-P (Nucleus Sampling): Limits the probability mass of words chosen. Lower values make responses more focused.
  top_p: 0.6
  # Maximum length of model responses. The model will not generate more than 2000 tokens.
  max_tokens: 2000
  system_prompt: >
    You are an expert AI academic advisor serving the Fowler School of
    Engineering's undergraduate students within Chapman University. 
    You provide accurate, clear guidance on degree requirements, course selection, 
    prerequisites, and school resources. Always remind students to verify any
    information with a faculty academic advisor or peer advisor, and
    encourage them to double-check deadlines, graduation requirements,
    or registration instructions with official campus resources.
    When you don't know an answer, direct them to appropriate university
    staff. Be professional, friendly, and supportive.
```

### **Parameter Explanations**

- `model_name` → Specifies the llm model version (`1.5b` refers to a 1.5-billion parameter model).
- `temperature` → Controls randomness in responses.
  - `0.0` = Fully deterministic (model always gives the same answer for the same input).
  - `1.0` = Highly random (model can generate varied responses).
  - **Recommended**: `0.1` (Keeps responses factual and consistent.)
- `top_p` → Nucleus sampling for token probability selection.
  - `0.5-0.7` ensures the model picks from only the most relevant words.
  - **Recommended**: `0.6` (Balances accuracy and variety.)
- `max_tokens` → Defines the maximum number of tokens generated in a response.
  - **2000 tokens** ensures responses stay relevant without being too long.
- `system_prompt` → A detailed system prompt that sets the context for the model.
  - **Recommended**: A prompt that clearly defines the model's role and expectations, ensuring it provides accurate and helpful responses to students.

---

## **Embeddings and Qdrant**

```yaml
embedding:
  embed_model: "nomic-embed-text"
  # Defines the max size (characters) of each chunk before it is sent to the LLM.
  chunk_size: 400
  # Overlapping buffer between chunks to preserve context across splits.
  chunk_overlap: 80

qdrant:
  url: "http://localhost:6333"
  collection: "pantherbot"
```

### **Parameter Explanations**
- `embedding.embed_model` → Specifies the embedding model used for text representation.
  - **Recommended**: `nomic-embed-text` (A robust model for generating text embeddings.)
- `embedding.chunk_size` → Defines how much text (in characters) is sent to the model at a time.
  - **Recommended**: `400` (Ensures a good balance of context retention and token limits.)
- `embedding.chunk_overlap` → Overlapping buffer between chunks for context preservation.
  - **Recommended**: `80` (Ensures responses don’t lose important information between chunks.)
- `qdrant.url` → URL for the Qdrant vector database.
- `qdrant.collection` → Name of the collection in Qdrant where embeddings are stored.

---

## **How to Use**

1. Modify `config.yaml` as needed.
2. Ensure `config.yaml` is placed in the project’s root directory.
3. Run the program, and it will **automatically load the values** from `config.yaml`.

---