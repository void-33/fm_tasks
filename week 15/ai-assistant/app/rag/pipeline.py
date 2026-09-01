"""RAG Pipeline including ingestion, chunking, and retrieval."""

import os
import glob
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import logging

from app.config import settings
import traceback

logger = logging.getLogger(__name__)


class RagPipeline:
    """Retrieval-Augmented Generation pipeline."""

    def __init__(self):
        """Initialize the RAG components."""
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set, RAG initialization may fail.")

        # Initialize embeddings model
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY
        )

        # Initialize ChromaDB client
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR
        )

        # The collection we'll use for our documents
        self.collection_name = "ai_assistant_docs"
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"} # Use cosine similarity
            )
        except Exception as e:
            logger.error(f"Failed to create/get ChromaDB collection: {e}")
            raise

    def load_document(self, file_path: str) -> List[Any]:
        """Load a document based on its extension."""
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == '.pdf':
                loader = PyPDFLoader(file_path)
            elif ext == '.docx':
                loader = Docx2txtLoader(file_path)
            elif ext in ['.txt', '.md', '.csv']:
                loader = TextLoader(file_path, encoding='utf-8')
            else:
                logger.warning(f"Unsupported file extension {ext} for file {file_path}")
                return []

            return loader.load()
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {e}")
            return []

    def ingest_directory(self, directory_path: str) -> int:
        """
        Ingest all supported documents from a directory.

        Args:
            directory_path: Path to the directory containing documents

        Returns:
            Number of documents successfully ingested.
        """
        if not os.path.exists(directory_path):
            logger.error(f"Directory {directory_path} does not exist.")
            return 0

        # Find all files
        all_files = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                all_files.append(os.path.join(root, file))

        all_docs = []
        for file_path in all_files:
            docs = self.load_document(file_path)
            all_docs.extend(docs)

        if not all_docs:
            logger.warning("No valid documents found to ingest.")
            return 0

        # Chunk documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""]
        )

        chunks = text_splitter.split_documents(all_docs)
        logger.info(f"Split {len(all_docs)} documents into {len(chunks)} chunks.")

        # Prepare for ChromaDB
        ids = [f"doc_{i}" for i in range(len(chunks))]
        texts = [chunk.page_content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        # Get embeddings (LangChain wraps this, but we're using raw ChromaDB)
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        try:
            embeddings_list = self.embeddings.embed_documents(texts)

            # Add to ChromaDB
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                documents=texts,
                metadatas=metadatas
            )
            logger.info("Successfully ingested into Vector DB.")
            return len(chunks)
        except Exception as e:
            logger.error(f"Error during embedding generation or insertion: {e}")
            traceback.print_exc()
            return 0

    def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Search for relevant documents in the vector database.

        Args:
           query: The search query.
           top_k: Number of results to return (defaults to settings.TOP_K_RESULTS).

        Returns:
            List of dictionaries with document 'text' and 'metadata'.
        """
        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        try:
            # Generate embedding for the query
            query_embedding = self.embeddings.embed_query(query)

            # Search ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )

            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                docs = results['documents'][0]
                metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(docs)

                for i in range(len(docs)):
                    formatted_results.append({
                        "text": docs[i],
                        "metadata": metadatas[i]
                    })

            return formatted_results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def clear(self):
        """Clear all data from the vector store."""
        try:
            if hasattr(self.chroma_client, "delete_collection"):
                self.chroma_client.delete_collection(self.collection_name)
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Vector store cleared.")
            else:
                logger.warning("ChromaDB client does not support delete_collection.")
        except Exception as e:
            logger.error(f"Error clearing vector store: {e}")

# Initialize a global instance
rag = RagPipeline()
