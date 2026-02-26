from apps.rag.services.retrieval import retrieve_context
import ollama
from apps.rag.models import DocumentChunk


SIMILARITY_THRESHOLD = 1.2  # semakin kecil semakin mirip (karena L2)


def get_chunk_text(chunk_id):
    try:
        chunk = DocumentChunk.objects.get(id=chunk_id)
        return chunk.content
    except DocumentChunk.DoesNotExist:
        return ""


def is_small_talk(text: str):
    greetings = [
        "halo", "hai", "hi", "permisi", "selamat pagi",
        "selamat siang", "selamat sore", "terima kasih"
    ]
    text = text.lower()
    return any(greet in text for greet in greetings)


def chat(question, vector_store, embedding_service):

    # 1️⃣ Small talk mode
    if is_small_talk(question):
        response = ollama.chat(
            model="llama3:8b",
            messages=[
                {
                    "role": "system",
                    "content": "Anda adalah AI IT Support yang ramah, profesional, dan komunikatif."
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )
        return response["message"]["content"]

    # 2️⃣ Retrieval mode
    results = retrieve_context(
        question,
        vector_store,
        embedding_service
    )

    if not results:
        return fallback_llm(question)

    best_match = results[0]

    # 3️⃣ Similarity check
    if best_match["score"] > SIMILARITY_THRESHOLD:
        return fallback_llm(question)

    # 4️⃣ Ambil beberapa chunk (top 3)
    context_texts = []

    for result in results[:3]:
        chunk_text = get_chunk_text(result["document_chunk_id"])
        context_texts.append(chunk_text)

    combined_context = "\n\n".join(context_texts)

    prompt = f"""
Anda adalah AI IT Support profesional.

Gunakan informasi di bawah ini untuk menjawab pertanyaan.
Jika informasi tidak cukup, jawab secara umum dengan profesional.

KONTEKS:
{combined_context}

PERTANYAAN:
{question}
"""

    response = ollama.chat(
        model="llama3:8b",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["message"]["content"]


def fallback_llm(question):
    response = ollama.chat(
        model="llama3:8b",
        messages=[
            {
                "role": "system",
                "content": "Anda adalah AI IT Support yang membantu pengguna dengan ramah dan profesional."
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )
    return response["message"]["content"]