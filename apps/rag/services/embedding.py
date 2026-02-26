import numpy as np
from sentence_transformers import SentenceTransformer
import torch


class EmbeddingService:
    """
    Service untuk:
    1. Generate embedding dari text
    2. Convert embedding ke format yang bisa disimpan di SQL (VARBINARY)
    """

    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.device = "cpu"   # PAKSA CPU
        self.model = SentenceTransformer(model_name, device=self.device)

    def embed_text(self, text: str) -> np.ndarray:
        embedding = self.model.encode(text)
        return np.array(embedding, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(texts)
        return np.array(embeddings, dtype=np.float32)

    @staticmethod
    def to_bytes(vector: np.ndarray) -> bytes:
        return vector.astype(np.float32).tobytes()

    @staticmethod
    def from_bytes(binary_data: bytes) -> np.ndarray:
        return np.frombuffer(binary_data, dtype=np.float32)