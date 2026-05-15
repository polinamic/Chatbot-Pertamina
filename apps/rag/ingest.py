from apps.rag.services.embedding import generate_embedding
import pyodbc
import numpy as np
import re
from datetime import datetime

DOC_DELIMITER = re.compile(r'^---\s*$', re.MULTILINE)


def split_documents(text: str) -> list[str]:
    """
    Split the raw knowledgebase text into document blocks using YAML-style delimiters.
    This preserves semantic sections and avoids chunking across unrelated documents.
    """
    parts = [part.strip() for part in re.split(DOC_DELIMITER, text)]
    return [part for part in parts if part]


def chunk_text(text: str, chunk_size: int = 1000) -> list[str]:
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


def ingest_document(document_id, text, connection):
    raw_docs = split_documents(text)
    if not raw_docs:
        raw_docs = [text]

    chunks = []
    for doc_block in raw_docs:
        if len(doc_block) <= 1000:
            chunks.append(doc_block)
        else:
            chunks.extend(chunk_text(doc_block, chunk_size=1000))

    cursor = connection.cursor()

    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)
        embedding_bytes = embedding.astype(np.float32).tobytes()

        cursor.execute("""
            INSERT INTO DocumentChunk
            (document_id, chunk_index, content, embedding_vector, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
        document_id,
        i,
        chunk,
        embedding_bytes,
        datetime.now())

    connection.commit()