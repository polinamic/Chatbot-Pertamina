import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import pyodbc
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.chat_service import chat
from apps.rag.services.embedding import EmbeddingService


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=chatbot_pertamina;"
        "Trusted_Connection=yes;"
    )


def main():
    connection = get_connection()

    # Load FAISS index
    vector_store = VectorStore(connection)
    vector_store.load_embeddings()

    # Load embedding model SEKALI saja
    embedding_service = EmbeddingService()

    print("Chatbot ready. Type 'exit' to quit.\n")

    while True:
        q = input("User: ")

        if q.lower() in ["exit", "quit"]:
            break

        response = chat(q, vector_store, embedding_service)
        print("AI:", response)


if __name__ == "__main__":
    main()