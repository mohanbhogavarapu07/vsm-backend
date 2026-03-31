import os
from groq import Groq
from sentence_transformers import SentenceTransformer
from app.services.db import get_supabase
from typing import List, Optional

# Load the model directly. In production, consider loading once globally or keeping warm.
# all-MiniLM-L6-v2 produces 384 dimensional embeddings.
_encoder = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text: str, size: int = 300, overlap: int = 50) -> List[str]:
    """
    Splits text into chunks of specified size with overlap to maintain context.
    """
    if not text:
        return []
    
    chunks = []
    # If the text is shorter than the size, return it as a single chunk
    if len(text) <= size:
        return [text]

    for i in range(0, len(text), size - overlap):
        chunk = text[i:i + size]
        chunks.append(chunk)
    
    return chunks

def add_document_to_knowledge_base(project_id: int, content: str, source: str = "manual"):
    """
    Chunks a document, generates embeddings, and stores them in Supabase.
    """
    supabase = get_supabase()
    chunks = chunk_text(content, size=300, overlap=50)
    
    if not chunks:
        return 0
        
    # Generate embeddings and normalize per the user's constraints
    embeddings = _encoder.encode(chunks, normalize_embeddings=True)
    
    # Batch insertion
    rows = []
    for chunk, emb in zip(chunks, embeddings):
        rows.append({
            "project_id": project_id,
            "source": source,
            "content": chunk,
            "embedding": emb.tolist()
        })
    
    # Store in Supabase
    res = supabase.table("project_knowledge").insert(rows).execute()
    
    data = getattr(res, "data", []) or []
    return len(data)

def retrieve_context(project_id: int, query: str, top_k: int = 5, use_top_k: int = 3) -> str:
    """
    Retrieves the most relevant document chunks for the query, using Top-K filtering.
    """
    supabase = get_supabase()
    
    # Embed query and normalize
    query_embedding = _encoder.encode(query, normalize_embeddings=True).tolist()
    
    # Execute RPC for vector match
    try:
        res = supabase.rpc(
            "match_project_knowledge", 
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.2, # Minimum similarity threshold
                "match_count": top_k,   # Retrieve up to top_k
                "p_project_id": project_id
            }
        ).execute()
        
        data = getattr(res, "data", []) or []
        
        # Sort by similarity just to be absolutely sure, and slice down to use_top_k
        docs = sorted(data, key=lambda x: x.get("similarity", 0), reverse=True)
        final_docs = docs[:use_top_k]
        
        if not final_docs:
            return ""
            
        # Combine the selected context
        context_parts = [f"[{doc.get('source', 'Unknown')}] {doc.get('content', '')}" for doc in final_docs]
        return "\n\n".join(context_parts)
        
    except Exception as e:
        print(f"Error querying project knowledge: {e}")
        return ""
