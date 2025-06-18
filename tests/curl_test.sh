
# Test LiteLLM API
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ollama/deepseek-r1:1.5b",
    "messages": [{"role": "user", "content": "Hello, what is 2+2?"}]
  }'

# Test Ollama API
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-r1:1.5b",
    "prompt": "Hello, what is 2+2?",
    "stream": false
  }'

# Test Network Connectivity Inside LiteLLM Container
docker exec -it rowboat-litellm-1 curl -v http://ollama:11434/api/tags