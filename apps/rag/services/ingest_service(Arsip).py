import os
import pyodbc
from datetime import datetime
import uuid


class IngestService:

    def __init__(self, connection):
        self.connection = connection

    def ingest_text_file(self, file_path):

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        document_id = str(uuid.uuid4())[:10]

        cursor = self.connection.cursor()

        # Simpan ke Document
        cursor.execute("""
            INSERT INTO Document (document_id, title, source, content, is_active, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, document_id,
             os.path.basename(file_path),
             "local_upload",
             content,
             1,
             datetime.now())

        # Split jadi chunk (simple split per 500 karakter)
        chunks = [content[i:i+500] for i in range(0, len(content), 500)]

        for chunk in chunks:
            chunk_id = str(uuid.uuid4())[:10]

            cursor.execute("""
                INSERT INTO DocumentChunk (document_chunk_id, document_id, chunk_text, created_at)
                VALUES (?, ?, ?, ?)
            """, chunk_id,
                 document_id,
                 chunk,
                 datetime.now())

        self.connection.commit()

        print(f"Document {file_path} ingested successfully.")