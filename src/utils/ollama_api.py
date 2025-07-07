import requests
import json
from typing import List, Dict, Any, Iterator, Optional
import os


class OllamaAPI:
    """Fast Ollama API client using direct REST calls for better GPU utilization"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or f"http://{self._get_ollama_host()}:11434"
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Connection': 'keep-alive'
        })
    
    def _get_ollama_host(self) -> str:
        return os.environ.get("OLLAMA_HOST", "localhost")
    
    def get_embeddings(self, model: str, prompt: str) -> List[float]:
        url = f"{self.base_url}/api/embeddings"
        payload = {"model": model, "prompt": prompt}
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json().get('embedding', [])
        except Exception as e:
            print(f"Error getting embeddings: {e}")
            return []
    
    def chat(self, model: str, messages: List[Dict], stream: bool = True, think: Optional[bool] = None, 
             hide_thinking: bool = False, **kwargs) -> str:
        """
        Chat completion with optional thinking mode
        
        Args:
            model: Model name
            messages: List of message dicts
            stream: Whether to use streaming (default True)
            think: Enable/disable thinking mode (None=auto, True=force, False=disable)
            hide_thinking: If True, hide <think></think> tags from output while still thinking
        """
        if stream:
            return ''.join(self.chat_stream(model, messages, think=think, hide_thinking=hide_thinking, **kwargs))
        
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        if think is not None:
            payload["think"] = think
        
        try:
            response = self.session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            content = data.get('message', {}).get('content', '')
            
            if hide_thinking and content:
                content = self._strip_thinking_tags(content)
            
            return content
        except Exception as e:
            print(f"Error in chat completion: {e}")
            return ""
    
    def chat_stream(self, model: str, messages: List[Dict], think: Optional[bool] = None, 
                    hide_thinking: bool = False, **kwargs) -> Iterator[str]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs
        }
        
        if think is not None:
            payload["think"] = think
        
        try:
            response = self.session.post(url, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line.decode())
                    if 'message' in data and 'content' in data['message']:
                        content = data['message']['content']
                        if hide_thinking and content:
                            content = self._strip_thinking_tags(content)
                        yield content
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Error in streaming chat: {e}")
            yield ""
    
    def chat_with_thinking(self, model: str, messages: List[Dict], stream: bool = True, **kwargs) -> Dict[str, str]:
        """Chat with thinking enabled, returns both thinking and content"""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "think": True,
            **kwargs
        }
        
        if stream:
            thinking = ""
            content = ""
            
            try:
                response = self.session.post(url, json=payload, stream=True, timeout=60)
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode())
                        if 'message' in data:
                            if 'thinking' in data['message']:
                                thinking += data['message']['thinking']
                            if 'content' in data['message']:
                                content += data['message']['content']
                    except json.JSONDecodeError:
                        continue
                        
                return {"thinking": thinking, "content": content}
            except Exception as e:
                print(f"Error in streaming chat with thinking: {e}")
                return {"thinking": "", "content": ""}
        else:
            try:
                response = self.session.post(url, json=payload, timeout=60)
                response.raise_for_status()
                data = response.json()
                message = data.get('message', {})
                return {
                    "thinking": message.get('thinking', ''),
                    "content": message.get('content', '')
                }
            except Exception as e:
                print(f"Error in chat with thinking: {e}")
                return {"thinking": "", "content": ""}
    
    def check_model(self, model: str) -> bool:
        url = f"{self.base_url}/api/tags"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [m['name'] for m in data.get('models', [])]
            return model in models or any(model in m for m in models)
        except Exception as e:
            print(f"Error checking models: {e}")
            return False
    
    def _strip_thinking_tags(self, content: str) -> str:
        """Remove <think></think> tags from content while preserving other text"""
        import re
        # Remove thinking tags but preserve surrounding whitespace structure
        return re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)


_ollama_api = None

def get_ollama_api() -> OllamaAPI:
    global _ollama_api
    if _ollama_api is None:
        _ollama_api = OllamaAPI()
    return _ollama_api
