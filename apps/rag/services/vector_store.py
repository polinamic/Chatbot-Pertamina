import faiss
import numpy as np
from apps.rag.models import DocumentChunk
from apps.rag.services.embedding import EmbeddingService


class VectorStore:

    def __init__(self):
        self.index = None
        self.ids = []
        self.embedding_service = EmbeddingService()

    # =========================================
    # LOAD ALL EMBEDDINGS FROM DATABASE
    # =========================================
    def load_embeddings(self):

        # Reset index setiap load
        self.index = None
        self.ids = []

        chunks = DocumentChunk.objects.exclude(embedding_vector=None)

        vectors = []

        for chunk in chunks:
            vec = self.embedding_service.from_bytes(chunk.embedding_vector)

            if vec is None:
                continue

            vectors.append(vec)
            self.ids.append(chunk.id)

        if not vectors:
            return

        # Convert ke numpy float32
        vectors = np.array(vectors).astype("float32")

        dimension = vectors.shape[1]

        # =========================================
        # COSINE SIMILARITY
        # =========================================

        # Normalize vector untuk cosine
        faiss.normalize_L2(vectors)

        # Gunakan Inner Product (IP) untuk cosine
        self.index = faiss.IndexFlatIP(dimension)

        self.index.add(vectors)

    # =========================================
    # SEARCH FUNCTION
    # =========================================
    def search(self, query_vector, top_k=5):

        if self.index is None:
            return []

        # Convert dan normalize query
        query_vector = np.array([query_vector]).astype("float32")
        faiss.normalize_L2(query_vector)

        scores, indices = self.index.search(query_vector, top_k)

        results = []

        for i, idx in enumerate(indices[0]):

            if idx == -1:
                continue

            chunk_id = self.ids[idx]
            similarity_score = float(scores[0][i])  # cosine similarity

            results.append({
                "document_chunk_id": chunk_id,
                "score": similarity_score
            })

        return results