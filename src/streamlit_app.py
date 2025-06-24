import yaml
import os
import requests
import json
import streamlit as st


cfg = yaml.safe_load(open(os.path.join("configs", "config.yaml")))
mc = cfg.get("model_llm", {})
model_name = mc["model_name"]
temperature = mc.get("temperature", 0.1)
top_p = mc.get("top_p", 0.95)
max_tokens = mc.get("max_tokens", 2000)


def query_ollama_stream(messages):
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": True,
        "think": False,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens
    }
    resp = requests.post(url, json=payload, stream=True)
    for line in resp.iter_lines():
        if not line:
            continue
        data = json.loads(line.decode())
        yield data.get("message", {}).get("content", "")

def main():
    st.title("Fowler Engineering Academic Advisor")

    if "history" not in st.session_state:
        st.session_state.history = [
            {"role": "system", "content": "You are a helpful academic advisor."}
        ]

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Type your message…"):
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        assistant_msg = ""
        with st.chat_message("assistant"):
            assistant_msg = st.write_stream(query_ollama_stream(st.session_state.history))
        st.session_state.history.append({"role": "assistant", "content": assistant_msg})

if __name__ == "__main__":
    main()