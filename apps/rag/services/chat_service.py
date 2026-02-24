from apps.rag.services.retrieval import retrieve_context
import ollama


def get_chunk_text(connection, chunk_id):
    cursor = connection.cursor()
    cursor.execute("""
        SELECT chunk_text
        FROM DocumentChunk
        WHERE document_chunk_id = ?
    """, chunk_id)

    row = cursor.fetchone()
    return row.chunk_text if row else ""


def chat(question, vector_store, embedding_service):

    results = retrieve_context(
        question,
        vector_store,
        embedding_service
    )

    if not results:
        return "Tidak ditemukan dalam panduan resmi. Silakan buat tiket."

    best_match = results[0]
    chunk_id = best_match["document_chunk_id"]

    context = get_chunk_text(vector_store.connection, chunk_id)

    prompt = f"""
Anda adalah AI IT Support.
Jawab hanya berdasarkan konteks berikut.
Jika jawaban tidak ada di konteks, katakan:
"Tidak ditemukan dalam panduan resmi. Silakan buat tiket."

KONTEKS:
{context}

PERTANYAAN:
{question}
"""

    response = ollama.chat(
        model="llama3:8b",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["message"]["content"]