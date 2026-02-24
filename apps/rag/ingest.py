from apps.rag.services.embedding import generate_embedding
import pyodbc
import numpy as np
from datetime import datetime

def chunk_text(text, chunk_size=500):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def ingest_document(document_id, text, connection):

    chunks = chunk_text(text)

    cursor = connection.cursor()

    for i, chunk in enumerate(chunks):

        embedding = generate_embedding(chunk)
        embedding_bytes = embedding.astype(np.float32).tobytes()

        cursor.execute("""
            INSERT INTO DocumentChunk
            (document_chunk_id, document_id, chunk_text, embedding_vector, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
        f"{document_id}_{i}",
        document_id,
        chunk,
        embedding_bytes,
        datetime.now())

    connection.commit()