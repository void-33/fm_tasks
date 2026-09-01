# FuseMachine Week 15

This workspace contains two related AI assistant implementations:

- [task_1](task_1) is the applied AI assistant with RAG, Gemini integration, and an Ollama fallback.
- [task_2](task_2) is the production-oriented version with caching, rate limiting, and a React frontend.

## Shared Setup

Both tasks use the same root-level `.env` file for shared credentials, and you can create it from the shared root `.env.template`.

## Project Layout

- `task_1/README.md` explains the implementation and run steps for Task 1.
- `task_2/README.md` explains the implementation and run steps for Task 2.
- `data/` contains the corpus used by the assignments.

## Usage

1. Update the root `.env` file with your API key.
2. Follow the task-specific README for the implementation details and run commands.
3. Start the task you want from its own directory using Docker Compose.