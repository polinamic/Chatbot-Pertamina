import faiss
import numpy as np
import logging
import threading
from apps.rag.models import DocumentChunk
from apps.rag.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class VectorStore:
    """
    PERBAIKAN: __init__ sekarang menerima parameter embedding_service opsional.

    Sebelumnya: VectorStore() selalu membuat EmbeddingService() baru di dalam
    constructor → model SentenceTransformer di-load lagi → double load.

    Sekarang: Jika embedding_service diberikan (dari singleton apps.py),
    pakai itu. Jika tidak (backward compatible), buat instance baru.
    """

    def __init__(self, embedding_service: EmbeddingService = None):
        self.index = None
        self.ids = []
        # Gunakan singleton dari luar jika ada, jika tidak buat baru
        self.embedding_service = embedding_service or EmbeddingService()
        self._lock = threading.RLock()

    # =========================================
    # LOAD ALL EMBEDDINGS FROM DATABASE
    # =========================================
    def load_embeddings(self):

        # Reset index setiap load
        self.index = None
        self.ids = []

        chunks = DocumentChunk.objects.exclude(embedding_vector=None)

        vectors = []
        ids_list = []

        for chunk in chunks:
            vec = self.embedding_service.from_bytes(chunk.embedding_vector)

            if vec is None:
                continue

            vectors.append(vec)
            ids_list.append(chunk.id)

        if not vectors:
            logger.warning("vector_store_no_embeddings", extra={"total_chunks": len(chunks)})
            with self._lock:
                self.index = None
                self.ids = []
            return

        # Convert ke numpy float32
        vectors = np.array(vectors).astype("float32")

        dimension = vectors.shape[1]
        num_vectors = len(vectors)
        norms = np.linalg.norm(vectors, axis=1)
        avg_norm = float(np.mean(norms))
        min_norm = float(np.min(norms))
        max_norm = float(np.max(norms))

        logger.info("vector_store_loaded", extra={
            "dimension": dimension,
            "num_vectors": num_vectors,
            "avg_norm": round(avg_norm, 3),
            "min_norm": round(min_norm, 3),
            "max_norm": round(max_norm, 3)
        })

        # =========================================
        # COSINE SIMILARITY
        # =========================================

        # Normalize vector untuk cosine
        faiss.normalize_L2(vectors)

        # Gunakan Inner Product (IP) untuk cosine
        new_index = faiss.IndexFlatIP(dimension)
        new_index.add(vectors)

        with self._lock:
            self.index = new_index
            self.ids = ids_list

    # =========================================
    # SEARCH FUNCTION
    # =========================================
    def search(self, query_vector, top_k=5):

        with self._lock:
            if self.index is None:
                logger.warning("vector_store_search_no_index")
                return []

            # Convert dan normalize query
            query_vector = np.array([query_vector]).astype("float32")
            faiss.normalize_L2(query_vector)

            query_norm = float(np.linalg.norm(query_vector))
            logger.debug("vector_store_search_query", extra={
                "query_norm": round(query_norm, 3),
                "dimension": query_vector.shape[1]
            })

            scores, indices = self.index.search(query_vector, top_k)
            ids_snapshot = list(self.ids)

        results = []

        for i, idx in enumerate(indices[0]):

            if idx == -1:
                continue

            if idx >= len(ids_snapshot):
                logger.warning("vector_store_idx_out_of_bounds", extra={"idx": int(idx), "ids_len": len(ids_snapshot)})
                continue

            chunk_id = ids_snapshot[idx]
            similarity_score = float(scores[0][i])  # cosine similarity

            results.append({
                "document_chunk_id": chunk_id,
                "score": similarity_score
            })

        logger.debug("vector_store_search_results", extra={
            "top_k": top_k,
            "results_count": len(results),
            "scores": [round(r["score"], 3) for r in results[:5]]  # log first 5
        })

        return results