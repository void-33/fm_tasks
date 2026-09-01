import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# App Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001/api/chat")
st.set_page_config(page_title="Production AI Assistant", page_icon="🚀", layout="centered")

st.title("🤖 Production AI Assistant")
st.markdown("""
This is a production-grade Web UI.
The backend features **Async execution**, **Retry Pipelines**, **Rate Limiting**, **Caching**, and **Model Fallbacks**.
""")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar config
with st.sidebar:
    st.header("⚙️ Settings")
    use_cache = st.toggle("Use Response Caching", value=True, help="Hits the backend cache for repeated queries")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "meta" in msg:
            st.caption(msg["meta"])

# Chat input
if prompt := st.chat_input("Ask a question..."):
    # Add user message to state
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # API Request
    with st.chat_message("assistant"):
        with st.spinner("Processing request asynchronously..."):
            try:
                response = requests.post(
                    BACKEND_URL,
                    json={"query": prompt, "use_cache": use_cache},
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("response", "No response content")
                    model = data.get("model_used", "Unknown")
                    cached = "Yes" if data.get("cached") else "No"

                    meta_text = f"**Model:** `{model}` | **Cached:** `{cached}`"

                    st.markdown(answer)
                    st.caption(meta_text)

                    # Add assistant message to state
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "meta": meta_text
                    })

                elif response.status_code == 429:
                    st.error("Too Many Requests! You've hit the backend Rate Limiter (10 req/min).")
                else:
                    st.error(f"Backend Error: {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("Failed to connect to the backend API. Is it running?")
            except requests.exceptions.Timeout:
                st.error("Request timed out.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
