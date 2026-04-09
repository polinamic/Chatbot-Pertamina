from apps.rag.services.embedding import EmbeddingService
from apps.rag.services.metadata_manager import extract_metadata_from_chunk, calculate_metadata_similarity
from apps.rag.services.bm25_search import BM25Search, hybrid_search
from apps.rag.models import DocumentChunk
import logging
import time
import os

logger = logging.getLogger(__name__)

# Global BM25 index (lazy-loaded)
_bm25_index = None
_bm25_last_updated = None

# Global Re-Ranker (lazy-loaded)
_reranker_model = None

# Gunakan model BGE Reranker (Sangat bagus untuk Bahasa Indonesia dan Inggris)
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-base")

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

def _get_reranker():
    """
    Lazy load model Cross-Encoder untuk Re-Ranking.
    Model ini berat, jadi hanya di-load ke RAM saat benar-benar dibutuhkan pertama kali.
    PERBAIKAN: Force CPU untuk menghindari CUDA error pada GPU yang incompatible
    """
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info("loading_reranker_model", extra={"model": RERANKER_MODEL_NAME})
            # Force CPU untuk menghindari CUDA error
            _reranker_model = CrossEncoder(RERANKER_MODEL_NAME, max_length=512, device='cpu')
            logger.info("reranker_model_loaded_successfully")
        except ImportError:
            logger.error("sentence_transformers_not_installed", extra={
                "msg": "Harap jalankan: pip install sentence-transformers"
            })
            return None
        except Exception as e:
            logger.error("reranker_model_load_failed", extra={"error": str(e)})
            return None
    return _reranker_model


def retrieve_context(question, vector_store, embedding_service, doc_type=None, top_k=3):
    """
    [ENTERPRISE LEVEL] Hybrid Retrieval + Cross-Encoder Re-Ranking
    
    Flow:
    1. Semantic search (FAISS vector similarity) -> Ambil kandidat lebih banyak (over-fetch)
    2. BM25 lexical search
    3. Metadata filtering
    4. Hybrid ranking (RRF / Weighted)
    5. Cross-Encoder Re-Ranking (Menyaring kandidat yang "Halusinasi")
    6. Return final top_k
    """
    try:
        timer_start = time.time()
        
        # Wajib load memori agar tidak kosong!
        vector_store.load_embeddings()
        
        # Step 1: Semantic search dengan OVER-FETCH.
        # Jika kita butuh 3 jawaban (top_k), kita ambil 15 kandidat dulu (top_k * 5)
        # agar Re-Ranker punya banyak pilihan untuk disaring.
        search_k = top_k * 5 
        semantic_results = vector_store.search(embedding_service.embed_text(question), search_k)
        
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
        
        filter_bm25 = [r for r in bm25_results if not doc_type or r.get("doc_type") == doc_type]
        
        # Hybrid ranking: Menggabungkan kekuatan Vector (Makna) dan BM25 (Keyword)
        if filter_bm25:
            hybrid_results = hybrid_search(
                question, 
                filtered_semantic, 
                filter_bm25,
                semantic_weight=0.6,
                bm25_weight=0.4,
                top_k=search_k # Tetap pertahankan kandidat banyak untuk di-rerank
            )
        else:
            hybrid_results = sorted(filtered_semantic, key=lambda x: x["score"], reverse=True)[:search_k]

        # ==========================================================
        # Step 5: CROSS-ENCODER RE-RANKING (Obat Anti-Frankenstein)
        # ==========================================================
        reranker = _get_reranker()
        if reranker and hybrid_results:
            # Siapkan pasangan [Pertanyaan User, Isi SOP]
            cross_inp = [[question, doc.get("content", "")] for doc in hybrid_results]
            
            # Prediksi akurasi sebenarnya (output berupa logit score)
            cross_scores = reranker.predict(cross_inp)
            
            # Masukkan skor baru ke dalam kandidat
            for idx, doc in enumerate(hybrid_results):
                doc["rerank_score"] = float(cross_scores[idx])
                
            # Urutkan ulang berdasarkan skor Re-Ranker yang paling tinggi
            hybrid_results = sorted(hybrid_results, key=lambda x: x["rerank_score"], reverse=True)
            
            # (Opsional) Filter: Buang dokumen yang skor rerank-nya terlalu rendah/negatif
            # Ini mencegah dokumen "Webcam" masuk ke pertanyaan "Internet"
            hybrid_results = [doc for doc in hybrid_results if doc["rerank_score"] > -2.0]
            
            used_method = "hybrid_reranked"
        else:
            # Fallback jika model gagal di-load atau belum diinstall
            used_method = "hybrid" if bm25_results else "semantic"

        # Step 6: Potong hasil akhir hanya sesuai top_k yang diminta LLM (misal 3)
        final_results = []
        for r in hybrid_results[:top_k]:
            final_results.append({
                "document_chunk_id": r.get("id") or r.get("document_chunk_id"),
                "score": r.get("rerank_score") if "rerank_score" in r else (r.get("combined_score") or r.get("score")),
                "content": r.get("content"),
                "category": r.get("category"),
                "retrieval_method": used_method
            })
        
        elapsed_ms = int((time.time() - timer_start) * 1000)
        logger.info("retrieval_complete", extra={
            "elapsed_ms": elapsed_ms,
            "question_length": len(question),
            "results_count": len(final_results),
            "doc_type_filter": doc_type,
            "methods_used": used_method
        })
        
        return final_results
        
    except Exception as e:
        import traceback
        logger.error("retrieval_error", extra={
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []
    