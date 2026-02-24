import faiss
import numpy as np


class VectorStore:

    def __init__(self, connection):
        self.connection = connection
        self.index = None
        self.ids = []

    def load_embeddings(self):

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT document_chunk_id, embedding_vector
            FROM DocumentChunk
            WHERE embedding_vector IS NOT NULL
        """)

        rows = cursor.fetchall()

        if not rows:
            print("⚠ No embeddings found in database.")
            self.index = None
            return

        vectors = []
        self.ids = []  # reset setiap load ulang

        for row in rows:
            self.ids.append(row.document_chunk_id)

            # convert VARBINARY → numpy float32
            vec = np.frombuffer(row.embedding_vector, dtype=np.float32)

            if vec.size == 0:
                continue

            vectors.append(vec)

        if not vectors:
            print("⚠ Embeddings exist but failed to parse.")
            self.index = None
            return

        vectors = np.array(vectors, dtype=np.float32)

        # pastikan 2D
        if len(vectors.shape) == 1:
            vectors = vectors.reshape(1, -1)

        dimension = vectors.shape[1]

        print(f"Loaded {len(vectors)} embeddings | Dimension: {dimension}")

        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(vectors)

    def search(self, query_vector, top_k=5):

        if self.index is None:
            raise ValueError("FAISS index not initialized. Call load_embeddings() first.")

        query_vector = np.array([query_vector], dtype=np.float32)

        distances, indices = self.index.search(query_vector, top_k)

        results = []

        for idx, dist in zip(indices[0], distances[0]):
            if idx < len(self.ids):
                results.append({
                    "document_chunk_id": self.ids[idx],
                    "distance": float(dist)
                })

        return results