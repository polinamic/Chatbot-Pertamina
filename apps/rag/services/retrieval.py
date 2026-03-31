from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.metadata_manager import extract_metadata_from_chunk, calculate_metadata_similarity
from apps.rag.services.bm25_search import BM25Search, hybrid_search
from apps.rag.models import DocumentChunk
import logging
import time

logger = logging.getLogger(__name__)

# Global BM25 index (lazy-loaded)
_bm25_index = None
_bm25_last_updated = None

def _init_bm25_index():
    """
    Initialize BM25 index dengan semua chunks yang ada.
    Dilakukan lazy-loading saat pertama kali retrieve_context dipanggil.
    """
    global _bm25_index, _bm25_last_updated
    
    try:
        chunks = DocumentChunk.objects.select_related('document').all()
        documents = []
        
        for chunk in chunks:
            documents.append({
                "id": chunk.id,
                "content": chunk.content,
                "category": extract_metadata_from_chunk(chunk.content).get("primary_category"),
                "doc_type": chunk.document.doc_type if chunk.document else None,
            })
        
        _bm25_index = BM25Search()
        _bm25_index.index_documents(documents)
        _bm25_last_updated = time.time()
        
        logger.info("bm25_index_initialized", extra={
            "total_chunks": len(documents)
        })
    except Exception as e:
        logger.warning("bm25_index_initialization_failed", extra={"error": str(e)})
        _bm25_index = None


def retrieve_context(question, vector_store, embedding_service, doc_type=None, top_k=5):
    """
    [IMPROVED] Hybrid retrieval dengan semantic search + BM25 + metadata filtering.
    
    Backward compatible: function signature sama, implementation lebih baik.
    
    Flow:
    1. Semantic search (FAISS vector similarity)
    2. BM25 lexical search
    3. Metadata filtering (doc_type, category)
    4. Hybrid ranking
    5. Return top-k results
    """
    try:
        timer_start = time.time()
        
        # Wajib load memori agar tidak kosong!
        vector_store.load_embeddings()
        
        # Step 1: Semantic search dengan over-fetch
        query_vector = embedding_service.embed_text(question)
        search_k = top_k * 4 if doc_type else top_k
        semantic_results = vector_store.search(query_vector, search_k)
        
        if not semantic_results:
            logger.info("retrieval_no_results", extra={"phase": "semantic_search"})
            return []
        
        # Step 2: BM25 search (lazy init)
        global _bm25_index
        if _bm25_index is None:
            _init_bm25_index()
        
        bm25_results = []
        if _bm25_index:
            bm25_results = _bm25_index.search(question, top_k=search_k)
        
        # Step 3 & 4: Metadata-aware filtering + hybrid ranking
        filtered_semantic = []
        for r in semantic_results:
            try:
                chunk = DocumentChunk.objects.select_related('document').get(id=r["document_chunk_id"])
                
                # Filter by doc_type jika spesifik
                if doc_type:
                    if not chunk.document.doc_type or chunk.document.doc_type != doc_type:
                        continue
                
                # Add metadata info
                metadata = extract_metadata_from_chunk(chunk.content)
                filtered_semantic.append({
                    "id": chunk.id,
                    "document_chunk_id": chunk.id,
                    "score": r["score"],
                    "content": chunk.content,
                    "category": metadata.get("primary_category"),
                    "doc_type": chunk.document.doc_type if chunk.document else None,
                })
            except DocumentChunk.DoesNotExist:
                continue
        
        filter_bm25 = [r for r in bm25_results 
                      if not doc_type or r.get("doc_type") == doc_type]
        
        # Step 5: Hybrid ranking
        if filter_bm25:
            hybrid_results = hybrid_search(
                question, 
                filtered_semantic, 
                filter_bm25,
                semantic_weight=0.6,
                bm25_weight=0.4,
                top_k=top_k
            )
        else:
            # Jika BM25 kosong, gunakan semantic ranking saja
            hybrid_results = sorted(
                filtered_semantic,
                key=lambda x: x["score"],
                reverse=True
            )[:top_k]
        
        # Normalize output format
        final_results = []
        for r in hybrid_results:
            final_results.append({
                "document_chunk_id": r.get("id") or r.get("document_chunk_id"),
                "score": r.get("combined_score") or r.get("score"),
                "content": r.get("content"),
                "category": r.get("category"),
                "retrieval_method": "hybrid" if "combined_score" in r else "semantic"
            })
        
        elapsed_ms = int((time.time() - timer_start) * 1000)
        logger.info("retrieval_complete", extra={
            "elapsed_ms": elapsed_ms,
            "question_length": len(question),
            "results_count": len(final_results),
            "doc_type_filter": doc_type,
            "methods_used": "hybrid" if bm25_results else "semantic"
        })
        
        return final_results
        
    except Exception as e:
        logger.error("retrieval_error", extra={"error": str(e)})
        return []