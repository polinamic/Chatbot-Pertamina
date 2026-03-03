from apps.rag.services.retrieval import retrieve_context
from apps.rag.models import DocumentChunk
import ollama

# =====================================================
# CONFIGURATION
# =====================================================

SIMILARITY_THRESHOLD = 0.60
TOP_K = 3

# =====================================================
# HELPER
# =====================================================

def get_chunk_text(chunk_id):
    try:
        chunk = DocumentChunk.objects.get(id=chunk_id)
        return chunk.content
    except DocumentChunk.DoesNotExist:
        return ""


def is_small_talk(text: str):
    text = text.lower().strip()

    greetings = [
        "halo", "hai", "hi", "permisi",
        "selamat pagi", "selamat siang",
        "selamat sore", "terima kasih"
    ]

    if text in greetings:
        return True

    if len(text.split()) <= 2 and any(text.startswith(g) for g in greetings):
        return True

    return False


# =====================================================
# LLM CORE
# =====================================================

def generate_llm(messages, temperature=0.3):

    response = ollama.chat(
        model="llama3:8b",
        messages=messages,
        options={
            "temperature": temperature,
            "top_p": 0.9,
            "num_predict": 512
        }
    )

    return response["message"]["content"]


# =====================================================
# SMALL TALK MODE
# =====================================================

def small_talk_response(question):

    system_prompt = """
Anda adalah AI IT Support internal perusahaan.

Tugas:
- Jawab sapaan dengan ramah.
- Tetap profesional.
- Gunakan Bahasa Indonesia.
- Jangan menjawab pertanyaan di luar domain IT Support.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    return generate_llm(messages, temperature=0.5)


# =====================================================
# REASONING LAYER
# =====================================================

def reasoning_layer(question, context_text):

    system_prompt = """
Anda adalah AI IT Support yang sangat teliti dan logis.

TUGAS:
1. Tentukan apakah konteks benar-benar relevan dengan pertanyaan.
2. Jika relevan, ambil hanya fakta penting yang berhubungan langsung.
3. Jika tidak relevan, tulis: Relevansi: Tidak Relevan

JANGAN menjawab pertanyaan pengguna.
Hanya berikan hasil analisis dalam format:

Relevansi: ...
Fakta Penting:
- ...
- ...
Ringkasan:
...
Gunakan Bahasa Indonesia.
"""

    user_prompt = f"""
KONTEKS:
{context_text}

PERTANYAAN:
{question}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return generate_llm(messages, temperature=0.2)


# =====================================================
# FINAL ANSWER GENERATOR
# =====================================================

def generate_final_answer(reasoning_output, question):

    # Jika reasoning menyatakan tidak relevan → tolak
    if "Tidak Relevan" in reasoning_output:
        return "Informasi tersebut tidak tersedia dalam sistem IT Support."

    system_prompt = """
Anda adalah AI IT Support profesional internal perusahaan.

Gunakan hasil analisis berikut untuk menjawab dengan:

- Bahasa Indonesia
- Profesional
- Terstruktur
- Jelas
- Tidak bertele-tele
- Tidak menambahkan informasi di luar analisis

Struktur:
1. Ringkasan solusi
2. Langkah-langkah (jika ada)
3. Catatan tambahan (jika relevan)
"""

    user_prompt = f"""
HASIL ANALISIS:
{reasoning_output}

Sekarang berikan jawaban final untuk pengguna.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return generate_llm(messages, temperature=0.3)


# =====================================================
# MAIN CHAT FUNCTION
# =====================================================

def chat(question, vector_store, embedding_service):

    question = question.strip()

    # ================= SMALL TALK =================
    if is_small_talk(question):
        return small_talk_response(question)

    # ================= RETRIEVAL =================
    results = retrieve_context(
        question,
        vector_store,
        embedding_service
    )

    if not results:
        return "Informasi tersebut tidak tersedia dalam sistem IT Support."

    best_match = results[0]

    # ================= SIMILARITY CHECK =================
    if best_match["score"] < SIMILARITY_THRESHOLD:
        return "Informasi tersebut tidak tersedia dalam sistem IT Support."

    # ================= BUILD CONTEXT =================
    context_texts = []

    for result in results[:TOP_K]:
        chunk_text = get_chunk_text(result["document_chunk_id"])
        if chunk_text:
            context_texts.append(chunk_text)

    if not context_texts:
        return "Informasi tersebut tidak tersedia dalam sistem IT Support."

    combined_context = "\n\n".join(context_texts)

    # ================= REASONING LAYER =================
    reasoning_output = reasoning_layer(question, combined_context)

    # ================= FINAL ANSWER =================
    final_answer = generate_final_answer(reasoning_output, question)

    return final_answer