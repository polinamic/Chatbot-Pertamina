import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name="sentence-transformers/all-mpnet-base-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str):
        if not text:
            return None
        vector = self.model.encode(text)
        return vector.astype(np.float32)

    def to_bytes(self, vector):
        return vector.tobytes()

    def from_bytes(self, byte_data):
        return np.frombuffer(byte_data, dtype=np.float32)