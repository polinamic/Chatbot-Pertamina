import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import pyodbc
from apps.rag.services.ingest_service import IngestService


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=chatbot_pertamina;"
        "Trusted_Connection=yes;"
    )


def main():
    connection = get_connection()
    service = IngestService(connection)

    service.ingest_text_file("data/documents/sop_wifi.txt")


if __name__ == "__main__":
    main()