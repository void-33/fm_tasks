# 🤖 AI Assistant (Applied AI Project)

A robust AI assistant built with modern generative AI technologies, featuring RAG (Retrieval-Augmented Generation) and Tool Calling via the Google Gemini API.

## 🌟 Key Features

*   **🧠 LLM Integration**: Powered by Google's Gemini API (`gemini-2.0-flash` typically for reasoning)
*   **📚 RAG Pipeline**: Ingests PDF, DOCX, and TXT files, chunks them, and stores embeddings using `ChromaDB` and Langchain.
*   **🛠️ Tool Calling**: Equipped with external tools (calculator, weather simulation, time checks) that the LLM can dynamically call during conversations.
*   **🌐 REST API**: Built with `FastAPI` for seamless integration into web apps.
*   **💻 Interactive CLI**: Includes a rich terminal interface for interacting with the agent natively.
*   **🐳 Containerized**: Fully Dockerized for simple deployment.

## 🏗️ Architecture Diagram

```mermaid
graph TD
    User([User]) <--> |REST API / CLI| App[FastAPI Application]
    
    subgraph AI Assistant Backend
        App <--> |Prompts & Functions| LLM[LLM Manager]
        App <--> |Query & Documents| RAG[RAG Pipeline]
        App <--> |Execute Tool| Tools[Tool Registry]
    end
    
    subgraph External Services
        LLM <--> |API Calls| Gemini[Google Gemini API]
    end
    
    subgraph Data Layer
        RAG --> |Vector Search| VectorDB[(ChromaDB)]
        RAG <-- |Load & Chunk| Docs[/Local Documents/]
    end
    
    Gemini -.-> |Triggers Function| Tools
```

## 🚀 Getting Started

### Prerequisites

*   Python 3.10+
*   Docker & Docker Compose (optional)
*   [Google Gemini API Key](https://aistudio.google.com/apikey)

### 1. Local Setup

Clone the repository and set up a virtual environment:

```bash
cd ai-assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

Copy the template environment file and add your API key:

```bash
cp .env.template .env
```
Edit `.env` and insert your API key:
`GEMINI_API_KEY="your-api-key"`

### 3. Usage via CLI 🖥️

You can interact with the assistant directly from the terminal.

**Ingest Documents (RAG setup):**
```bash
# First create a folder and put some documents there
mkdir -p data/documents
# Copy pdf/txt files into data/documents

# Ingest them into the vector DB
python cli.py ingest data/documents
```

**Chat with the Assistant:**
```bash
# Standard chat
python cli.py chat

# Chat with RAG enabled
python cli.py chat --rag

# Chat with Tools enabled
python cli.py chat --tools

# Chat with everything enabled
python cli.py chat --rag --tools
```

### 4. Usage via REST API 🌐

Start the FastAPI development server:

```bash
uvicorn app.main:app --reload
```

The API docs will be available at: http://localhost:8000/docs

**Example API Call:**
```bash
curl -X POST "http://localhost:8000/api/chat" \
     -H "Content-Type: application/json" \
     -d '{"query": "Calculate the square root of 9999", "use_tools": true}'
```

### 5. Running with Docker 🐳

To run the entire application via Docker:

```bash
docker-compose up --build
```
This maps port `8000` to the host machine and persists ChromaDB data in the `./data` directory.

## 📂 Project Structure

```
ai-assistant/
├── app/
│   ├── __init__.py
│   ├── config.py         # Central configuration schema
│   ├── llm.py            # Gemini API integration wrapper
│   ├── main.py           # FastAPI server & endpoints
│   ├── rag/
│   │   ├── __init__.py
│   │   └── pipeline.py   # Langchain & ChromaDB logic
│   └── tools/
│       ├── __init__.py
│       └── registry.py   # External tools/functions definition
├── cli.py                # Rich terminal UI
├── .env.template         # Environment variables template
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Service orchestration
└── requirements.txt      # Dependency list
```

## 📝 Technologies Used

*   **[Google GenAI SDK](https://ai.google.dev/)** - LLM inference and embeddings
*   **[LangChain](https://python.langchain.com/)** - Document loading and chunking orchestration
*   **[ChromaDB](https://www.trychroma.com/)** - Lightweight persistent vector store
*   **[FastAPI](https://fastapi.tiangolo.com/)** - High-performance web framework
*   **[Rich](https://rich.readthedocs.io/)** - CLI formatting and markdown rendering
