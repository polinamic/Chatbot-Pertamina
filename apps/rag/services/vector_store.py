import faiss
import numpy as np
from apps.rag.models import DocumentChunk
from apps.rag.services.embedding import EmbeddingService


class VectorStore:

    def __init__(self):
        self.index = None
        self.ids = []
        self.embedding_service = EmbeddingService()

    def load_embeddings(self):

        chunks = DocumentChunk.objects.exclude(embedding_vector=None)

        vectors = []

        for chunk in chunks:
            vec = self.embedding_service.from_bytes(chunk.embedding_vector)
            vectors.append(vec)
            self.ids.append(chunk.id)

        if not vectors:
            return

        vectors = np.array(vectors)

        dimension = vectors.shape[1]

        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(vectors)

    def search(self, query_vector, top_k=5):

        if self.index is None:
            return []

        query_vector = np.array([query_vector])
        distances, indices = self.index.search(query_vector, top_k)

        results = []

        for i, idx in enumerate(indices[0]):

            if idx == -1:
                continue

            chunk_id = self.ids[idx]
            score = float(distances[0][i])

            results.append({
                "document_chunk_id": chunk_id,
                "score": score
            })

        return results