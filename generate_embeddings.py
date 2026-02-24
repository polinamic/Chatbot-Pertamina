import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import pyodbc
from apps.rag.services.embedding_service import EmbeddingService


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=chatbot_pertamina;"
        "Trusted_Connection=yes;"
    )


def main():
    connection = get_connection()
    service = EmbeddingService(connection)
    service.generate_and_store_embeddings()


if __name__ == "__main__":
    main()