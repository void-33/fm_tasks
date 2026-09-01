import chromadb
from google import genai
from app.core.config import settings

class RAGService:
    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path=settings.chroma_db_dir)
        self.collection = self.chroma_client.get_or_create_collection(name="documents")
        
        self.ai_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200):
        chunks = []
        start = 0
        while start < len(text):
            chunks.append(text[start:start+chunk_size])
            start += chunk_size - overlap
        return chunks

    def ingest_text(self, text: str, source_name: str = "upload"):
        if not self.ai_client:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        chunks = self.chunk_text(text)
        if not chunks:
            return 0
            
        # Get embeddings using Gemini
        embeddings = []
        for chunk in chunks:
            response = self.ai_client.models.embed_content(
                model="gemini-embedding-2",
                contents=chunk
            )
            # The structure for google-genai embedding response
            embeddings.append(response.embeddings[0].values)
            
        # Store in ChromaDB
        ids = [f"{source_name}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": source_name} for _ in chunks]
        
        self.collection.add(
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        return len(chunks)

    def retrieve_context(self, query: str, top_k: int = 3):
        if not self.ai_client:
            return "", []
            
        response = self.ai_client.models.embed_content(
            model="gemini-embedding-2",
            contents=query
        )
        query_embedding = response.embeddings[0].values
        
        # Verify collection isn't empty before querying
        if self.collection.count() == 0:
            return "", []
            
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        context = ""
        sources = []
        if results and results['documents'] and results['documents'][0]:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            
            for i in range(len(docs)):
                src = metas[i]['source']
                sources.append(src)
                context += f"Source ({src}):\n{docs[i]}\n\n"
                
        return context.strip(), list(set(sources))
        
rag_service = RAGService()
