import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


class EmbeddingService:
    """
    Service untuk:
    1. Generate embedding dari text
    2. Convert embedding ke format yang bisa disimpan di SQL (VARBINARY)
    """

    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers is not installed. Install it using: pip install sentence-transformers")
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding vector (float32)
        """
        embedding = self.model.encode(text)
        return np.array(embedding, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Generate embedding untuk banyak text sekaligus
        """
        embeddings = self.model.encode(texts)
        return np.array(embeddings, dtype=np.float32)

    @staticmethod
    def to_bytes(vector: np.ndarray) -> bytes:
        """
        Convert numpy vector ke bytes untuk disimpan di SQL (VARBINARY)
        """
        return vector.astype(np.float32).tobytes()

    @staticmethod
    def from_bytes(binary_data: bytes) -> np.ndarray:
        """
        Convert VARBINARY dari SQL kembali ke numpy vector
        """
        return np.frombuffer(binary_data, dtype=np.float32)