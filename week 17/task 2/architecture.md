# Architecture: Bounded Cross-Source Verification Agent

This document illustrates the architecture of the AI Assistant with the Task 3 agentic loop extension and Week 17 MLOps pipeline.

## System Architecture

```mermaid
flowchart TD
    subgraph Client["Client Tier"]
        UI["React Frontend (Vite + Nginx :3000)"]
        Harness["Deterministic Eval Harness (run_evaluation.py)"]
    end

    subgraph Gateway["API Layer (FastAPI :8000)"]
        RL["SlowAPI Rate Limiter (30/min agent, 60/min chat)"]
        CacheCheck{"Redis Cache Check"}
        LegacyRoute["POST /api/v1/chat (W15 Baseline)"]
        AgentRoute["POST /api/v1/agent/chat (Task 3 Agent)"]
    end

    subgraph StateTier["Cache & Persistence"]
        Redis[("Redis :6379 (agent: & chat: keyspaces)")]
        Chroma[("ChromaDB Vector Store (Persistent :8000)")]
    end

    subgraph AgentLoop["Bounded Agent Decision Loop (agent.py)"]
        InitState["Initialize Task State & Fetch Source Catalog"]
        Decision["Model Decision Step (Structured JSON Action)"]
        ValidateAction{"Action Validator"}
        
        SearchAct["Action: search(query, sources, top_k)"]
        ClarifyAct["Action: clarify(question)"]
        FinalAct["Action: final(answer, citations)"]
        
        ToolCall["Bounded Tool: retrieve_chunks()"]
        Compaction["Context Engineering: Evidence Compaction & Deduplication"]
        StopCond{"Stopping Conditions Met?<br/>(Max 6 steps, Max 4 searches, No-progress, Timeout)"}
        
        ValidateCitations{"Validate Citations against Ledger"}
        SafeTerminal["Return AgentResponse<br/>(completed / needs_clarification / insufficient_evidence / bounded_failure)"]
    end

    subgraph ModelTier["LLM Providers"]
        Gemini["Google Gemini API (Primary: gemini-2.0-flash)"]
        Ollama["Ollama Local LLM (Fallback: qwen2.5:0.5b :11434)"]
    end

    subgraph MLOpsTier["MLOps & Evaluation Tier (Week 17)"]
        Prompts["Versioned Prompts<br/>(prompt_v1, prompt_v2, prompt_v3)"]
        MLflow["MLflow Tracking (:5000)<br/>Experiment: agent_prompt_experiments<br/>(Metrics, Prompts, Traces)"]
        Evidently["Evidently AI Regression Suite<br/>(5 Golden Queries, Semantic Overlap, HTML Reports)"]
        Airflow["Airflow Nightly DAG<br/>(agent_regression_dag.py)"]
    end

    %% Client flows
    UI -->|Agent Mode Request| RL
    UI -->|Legacy Chat Request| RL
    Harness -->|Direct In-Process / HTTP| AgentRoute

    %% MLOps flows
    Prompts --> Harness
    Harness --> MLflow
    Prompts --> Evidently
    Evidently --> MLflow
    Airflow --> Evidently
    Airflow --> MLflow

    RL --> CacheCheck
    CacheCheck -- "Cache HIT" --> UI
    CacheCheck -- "Cache MISS (chat:)" --> LegacyRoute
    CacheCheck -- "Cache MISS (agent:)" --> AgentRoute

    %% Legacy flow
    LegacyRoute -->|Single Retrieval| Chroma
    LegacyRoute -->|Single Generation| Gemini

    %% Agent Flow
    AgentRoute --> InitState
    InitState --> Chroma
    InitState --> Decision
    Decision --> Gemini
    Gemini -.->|Fallback on error| Ollama
    Decision --> ValidateAction

    ValidateAction -- "Action = clarify" --> ClarifyAct --> SafeTerminal
    ValidateAction -- "Action = final" --> FinalAct --> ValidateCitations
    ValidateCitations -- "Valid Ledger Citations" --> SafeTerminal
    ValidateCitations -- "No Valid Citations" --> SafeTerminal
    
    ValidateAction -- "Action = search" --> SearchAct --> ToolCall
    ToolCall --> Chroma
    ToolCall --> Compaction
    Compaction --> StopCond
    StopCond -- "Continue" --> Decision
    StopCond -- "Cap Reached / No Progress" --> SafeTerminal

    SafeTerminal -->|Store Result (agent: key)| Redis
    SafeTerminal --> UI
```

## Component Legend

| Component | Role & Boundary |
|---|---|
| **React Frontend (:3000)** | User interface supporting both Single-Pass Legacy mode (`/chat`) and Agent Mode (`/agent/chat`). Displays model status tags, source citations, step iteration counts, and system health. |
| **FastAPI Backend (:8000)** | Web server hosting REST routes, rate limiting, dependency injection, and request validation. |
| **Redis Cache (:6379)** | Low-latency response cache with strict namespace partitioning: `chat:<sha256>` for single-pass requests and `agent:<sha256>` for agent trajectories. |
| **ChromaDB Vector Store** | Persistent embeddings and document chunks storage. Accessed via bounded tool `retrieve_chunks()`. |
| **Agent Decision Loop (`agent.py`)** | Central orchestrator enforcing a maximum of 6 steps and 4 searches per request. Evaluates intermediate evidence to dynamically decide the next action. |
| **Evidence Ledger & Compaction** | Context-engineering engine that deduplicates retrieved chunks, enforces length/count caps (12 items / 12,000 chars), and clears raw Chroma query payloads between iterations. |
| **Action Validator** | Pydantic model validator ensuring mutually exclusive fields for `search`, `clarify`, and `final`. Issues up to 1 structured JSON repair prompt on malformed output. |
| **Evaluation Harness (`run_evaluation.py`)** | From-scratch deterministic offline test harness verifying 11 diverse test cases including multi-source verification, conflicting evidence, tool failures, and infinite loop caps. |
| **MLflow Experiment Tracking** | Logs prompt versions (v1, v2, v3), configuration parameters, evaluation metrics, and full step-by-step agent traces (`agent_prompt_experiments`). |
| **Evidently AI Regression Suite** | Automated regression testing comparing new prompt responses against approved golden references; generates HTML diagnostic reports in `reports/`. |
| **Airflow Orchestration DAG** | Nightly pipeline (`agent_regression_dag.py`) evaluating prompt regression against a 60% threshold, triggering alerts on quality degradation. |
