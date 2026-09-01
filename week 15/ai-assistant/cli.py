"""CLI interface for the AI Assistant."""

import argparse
import sys
import os
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Make sure we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.llm import llm_client
from app.rag.pipeline import rag
from app.tools.registry import AVAILABLE_TOOLS

console = Console()

def print_header():
    """Print the application header."""
    console.print(Panel.fit(
        "[bold blue]AI Assistant CLI[/bold blue]\n"
        "[dim]Powered by Gemini, LangChain, and ChromaDB[/dim]",
        border_style="blue"
    ))

def ingest_mode(path: str):
    """Run in ingestion mode."""
    console.print(f"[{'bold yellow'}]Ingesting documents from:[/] {path}")
    chunks = rag.ingest_directory(path)
    if chunks > 0:
        console.print(f"[bold green]Success![/] Ingested {chunks} chunks into the vector database.")
    else:
        console.print("[bold red]Failed.[/] No documents ingested.")

def chat_mode(use_rag: bool, use_tools: bool):
    """Run in interactive chat mode."""
    console.print("[bold green]Starting chat session...[/] (Type 'exit' or 'quit' to end, 'clear' to reset history)")

    if use_rag:
        console.print("[dim]- RAG is ENABLED (will search local documents)[/dim]")
    if use_tools:
        console.print("[dim]- Tools are ENABLED (calculator, weather, etc.)[/dim]")

    # Initial setup
    system_prompt = "You are a helpful, professional AI assistant."
    tools = AVAILABLE_TOOLS if use_tools else None

    # We maintain the chat session object
    chat = llm_client.get_chat_session(system_prompt=system_prompt, tools=tools)

    while True:
        try:
            user_input = console.input("\n[bold cyan]You:[/] ")

            if user_input.lower() in ('exit', 'quit'):
                console.print("Goodbye!")
                break

            if user_input.lower() == 'clear':
                chat = llm_client.get_chat_session(system_prompt=system_prompt, tools=tools)
                console.print("[dim]Chat history cleared.[/dim]")
                continue

            if not user_input.strip():
                continue

            # Handle RAG manually per turn in CLI by injecting context if needed
            context_to_inject = ""
            if use_rag:
                docs = rag.search(user_input, top_k=3)
                if docs:
                    contexts = [f"Source {i+1}:\n{doc['text']}" for i, doc in enumerate(docs)]
                    context_chunk = "\n\n".join(contexts)
                    context_to_inject = f"\n\n[CONTEXT FROM KNOWLEDGE BASE]:\n{context_chunk}\n\nPlease use the context above to inform your answer if relevant."

            # Construct the final prompt for this turn
            final_prompt = user_input + context_to_inject

            with console.status("[bold green]Thinking..."):
                response = chat.send_message(final_prompt)

            # Print response
            console.print("\n[bold magenta]Assistant:[/]")
            console.print(Markdown(response.text))

        except KeyboardInterrupt:
            console.print("\nGoodbye!")
            break
        except Exception as e:
            console.print(f"\n[bold red]Error:[/] {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="AI Assistant built with modern LLM stack.")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents into the RAG vector database")
    ingest_parser.add_argument("path", type=str, help="Directory containing documents (pdf, txt, docx)")

    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Start an interactive chat session")
    chat_parser.add_argument("--rag", action="store_true", help="Enable Retrieval-Augmented Generation")
    chat_parser.add_argument("--tools", action="store_true", help="Enable Tool/Function Calling")

    args = parser.parse_args()

    print_header()

    if args.command == "ingest":
        ingest_mode(args.path)
    elif args.command == "chat":
        chat_mode(args.rag, args.tools)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
