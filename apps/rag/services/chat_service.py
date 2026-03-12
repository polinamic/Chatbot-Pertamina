import re
import logging
from typing import List, Dict

from apps.rag.services.retrieval import retrieve_context
from apps.rag.models import DocumentChunk
import ollama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.75
TOP_K = 3

chat_sessions = {}

# =====================================================
# GLOBAL SYSTEM RULE
# =====================================================

SYSTEM_RULE = """
Anda adalah AI IT Support perusahaan yang ramah, profesional, dan sangat kompeten.

ATURAN WAJIB:
- SELALU gunakan Bahasa Indonesia dalam setiap respons.
- DILARANG KERAS menjawab dalam Bahasa Inggris. Istilah teknis boleh tetap dalam Bahasa Inggris (contoh: router, reboot, firewall, IP address).
- Berikan jawaban yang jelas, terstruktur, dan mudah dipahami oleh pengguna awam sekalipun.
- Gunakan format langkah bernomor saat memberikan solusi troubleshooting.
- Tunjukkan empati kepada pengguna yang mengalami masalah IT.
- Akhiri setiap respons dengan kalimat yang memastikan pengguna merasa dibantu.
- Jangan pernah menyerah membantu pengguna.
"""

# =====================================================
# LANGUAGE ENFORCEMENT
# =====================================================

ENGLISH_INDICATORS = [
    r"\b(the|this|that|these|those)\b",
    r"\b(you|your|you're|you've|you'll)\b",
    r"\b(if|when|then|else|while)\b",
    r"\b(check|restart|reboot|reset|try|please|make sure)\b",
    r"\b(router|wifi|internet|problem|issue|error|device|network|connection)\b",
    r"\b(click|open|close|install|uninstall|download|update)\b",
    r"\b(make|sure|need|step|first|next|then|finally)\b",
    r"\b(I|we|they|he|she|it)\s+(am|is|are|was|were|have|has|had|will|would|can|could|should)\b",
]

COMBINED_ENGLISH_PATTERN = re.compile(
    "|".join(ENGLISH_INDICATORS),
    re.IGNORECASE
)


def is_english_response(text: str) -> bool:
    """Deteksi apakah teks mengandung Bahasa Inggris yang signifikan."""
    matches = COMBINED_ENGLISH_PATTERN.findall(text)
    # Toleransi: lebih dari 3 kata bahasa Inggris non-teknis = dianggap respons Inggris
    return len(matches) > 3


def force_indonesian(text: str) -> str:
    """
    Paksa terjemahkan ke Bahasa Indonesia jika model menjawab dalam Bahasa Inggris.
    Istilah teknis tetap dipertahankan.
    """
    if not is_english_response(text):
        return text

    try:
        response = ollama.chat(
            model="llama3:8b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Terjemahkan teks berikut ke Bahasa Indonesia. "
                        "Pertahankan istilah teknis IT dalam Bahasa Inggris seperti: "
                        "router, reboot, firewall, IP address, DNS, LAN, WAN, VPN, browser, dll. "
                        "Jangan tambahkan penjelasan apapun, hanya terjemahan saja."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            options={"temperature": 0}
        )
        translated = response["message"]["content"].strip()
        return translated if translated else text

    except Exception as e:
        logger.warning(f"Force translate gagal: {str(e)}")
        return text


# =====================================================
# LLM CORE
# =====================================================

def generate_llm(messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
    """Generate respons dari model LLM dengan enforced Bahasa Indonesia."""

    system_rule = {
        "role": "system",
        "content": (
            "Anda adalah AI IT Support perusahaan yang sangat kompeten dan profesional.\n\n"
            "ATURAN MUTLAK — WAJIB DIIKUTI TANPA PENGECUALIAN:\n"
            "1. SELALU gunakan Bahasa Indonesia dalam SETIAP kalimat respons Anda.\n"
            "2. DILARANG KERAS menggunakan Bahasa Inggris dalam kalimat penjelas.\n"
            "3. Istilah teknis IT boleh tetap dalam Bahasa Inggris (router, reboot, IP address, firewall, dll).\n"
            "4. Jika Anda tidak yakin terjemahannya, tetap tulis dalam Bahasa Indonesia semampu mungkin.\n"
            "5. Respons harus terstruktur, jelas, dan profesional.\n"
            "6. Tunjukkan empati kepada pengguna.\n"
        )
    }

    full_messages = [system_rule] + messages

    try:
        response = ollama.chat(
            model="llama3:8b",
            messages=full_messages,
            options={
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 600,
                "num_ctx": 4096,
                "repeat_penalty": 1.1,
            }
        )

        text = response.get("message", {}).get("content", "").strip()

        if not text:
            return "Maaf, saya tidak dapat menghasilkan respons saat ini. Silakan coba lagi."

        # Paksa ke Bahasa Indonesia jika masih ada Bahasa Inggris berlebihan
        text = force_indonesian(text)

        return text

    except Exception as e:
        logger.error(f"Ollama Error: {str(e)}")
        return (
            "Mohon maaf, sistem AI kami sedang mengalami gangguan teknis. "
            "Silakan coba beberapa saat lagi atau hubungi tim IT Support secara langsung."
        )


# =====================================================
# INTENT DETECTION
# =====================================================

def detect_intent(question: str) -> str:
    """
    Deteksi maksud pengguna dari pesan yang dikirim.
    Mengembalikan salah satu dari: IT_PROBLEM, REQUEST_IT_SUPPORT, REJECT_IT_SUPPORT, GENERAL_CHAT
    """

    system_prompt = (
        "Anda adalah sistem klasifikasi intent untuk chatbot IT Support.\n\n"
        "Tentukan kategori intent dari pesan pengguna berikut.\n\n"
        "Kategori yang tersedia:\n"
        "- IT_PROBLEM        : Pengguna melaporkan atau mendeskripsikan masalah IT (komputer, jaringan, printer, software, dll)\n"
        "- REQUEST_IT_SUPPORT: Pengguna secara eksplisit meminta dihubungkan atau dibantu oleh tim IT Support\n"
        "- REJECT_IT_SUPPORT : Pengguna menolak saran eskalasi ke IT Support\n"
        "- GENERAL_CHAT      : Percakapan umum yang tidak berkaitan dengan masalah IT\n\n"
        "Jawab HANYA dengan satu label kategori saja, tanpa penjelasan tambahan."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    result = generate_llm(messages, temperature=0).strip().upper()

    # Parsing hasil dengan prioritas
    for intent in ["REQUEST_IT_SUPPORT", "REJECT_IT_SUPPORT", "GENERAL_CHAT", "IT_PROBLEM"]:
        if intent in result:
            return intent

    # Default fallback
    return "IT_PROBLEM"


# =====================================================
# SMALL TALK & TROUBLESHOOTING
# =====================================================

def get_llm_response(
    question: str,
    history: List[Dict[str, str]],
    vector_store,
    embedding_service
) -> str:

    try:

        results = retrieve_context(
            question,
            vector_store,
            embedding_service,
            doc_type="TROUBLESHOOT",
            top_k=TOP_K
        )

        context_text = ""

        for r in results:

            try:
                chunk = DocumentChunk.objects.get(
                    id=r["document_chunk_id"]
                )

                if r["score"] >= SIMILARITY_THRESHOLD:
                    context_text += chunk.content + "\n\n"

            except DocumentChunk.DoesNotExist:
                continue

        if not context_text:
            context_text = (
                "Tidak ada dokumentasi troubleshooting yang sangat relevan ditemukan."
            )

        system_msg = f"""
Anda adalah teknisi IT Support profesional.

Gunakan informasi berikut sebagai referensi troubleshooting:

{context_text}

Instruksi:
1. Jawab dalam Bahasa Indonesia
2. Berikan langkah troubleshooting bernomor
3. Gunakan bahasa yang mudah dipahami user awam
"""

        messages = [{"role": "system", "content": system_msg}] + history + [
            {"role": "user", "content": question}
        ]

        return generate_llm(messages)

    except Exception as e:

        logger.error(f"Troubleshoot RAG error: {str(e)}")

        return "Maaf, terjadi kesalahan saat mengambil panduan troubleshooting."


# =====================================================
# ESCALATION GUIDE (RAG ONLY)
# =====================================================

def escalation_guide(query_issue: str, vector_store, embedding_service) -> str:

    try:

        results = retrieve_context(
            query_issue,
            vector_store,
            embedding_service,
            doc_type="ESCALATION",
            top_k=TOP_K
        )

        if not results:
            return (
                "Panduan eskalasi IT Support tidak ditemukan di database."
            )

        best_match = results[0]

        chunk = DocumentChunk.objects.get(
            id=best_match["document_chunk_id"]
        )

        return chunk.content

    except Exception as e:

        logger.error(f"Escalation retrieval error: {str(e)}")

        return (
            "Mohon maaf, terjadi kesalahan saat mengambil panduan IT Support."
        )


# =====================================================
# CONFIRMATION DETECTION
# =====================================================

def detect_confirmation(text: str) -> bool:
    """
    Deteksi apakah pengguna mengkonfirmasi (setuju) atau menolak tawaran eskalasi IT Support.
    Mengembalikan True jika setuju, False jika menolak.
    """

    text = text.lower().strip()

    # Pola penolakan — dicek lebih dulu karena lebih spesifik
    negative_pattern = (
        r'\b(tidak|tak|ga|gak|nggak|enggak)\b.*\b(jadi|lanjut|proses|pakai|gunakan|coba|lakukan|perlu|butuh)\b'
        r'|\b(batal|stop|skip|jangan|jangan dulu|tidak usah|tidak perlu|tidak mau|belum perlu)\b'
    )
    if re.search(negative_pattern, text):
        return False

    # Pola konfirmasi — kata tunggal
    confirmation_words = [
        "iya", "ya", "yap", "yep", "betul", "benar", "tepat",
        "oke", "ok", "okey", "sip", "siap", "mantap",
        "boleh", "silakan", "lanjut", "lanjutkan",
        "mau", "setuju", "gas", "coba", "hayuk", "ayo",
        "monggo", "tolong", "bantu"
    ]
    word_pattern = r'\b(' + '|'.join(confirmation_words) + r')\b'
    if re.search(word_pattern, text):
        return True

    # Pola konfirmasi — frasa
    confirmation_phrases = [
        "boleh lanjut", "lanjut saja", "lanjutkan saja", "silakan lanjut",
        "silakan diproses", "tolong lanjutkan", "ya sudah", "yaudah",
        "ya lanjut", "coba saja", "kerjakan saja", "tidak masalah",
        "tidak apa apa", "tidak apa-apa", "gapapa", "gpp",
        "lanjut aja", "boleh diproses", "tolong bantu",
        "minta tolong", "bantu saya", "ya tolong", "iya tolong",
    ]
    for phrase in confirmation_phrases:
        if phrase in text:
            return True

    return False


# =====================================================
# MAIN CHAT
# =====================================================

def chat(question: str, vector_store, embedding_service, session_id: str = "default") -> str:
    """
    Fungsi utama untuk memproses pesan pengguna dan menghasilkan respons chatbot IT Support.

    Args:
        question        : Pesan dari pengguna.
        vector_store    : Instance vector store untuk pencarian RAG.
        embedding_service: Service embedding untuk menghasilkan vektor.
        session_id      : ID sesi untuk mempertahankan konteks percakapan.

    Returns:
        String respons dari chatbot dalam Bahasa Indonesia.
    """

    question = question.strip()

    if not question:
        return "Halo! Ada yang bisa saya bantu terkait masalah IT Anda hari ini?"

    # Inisialisasi sesi baru jika belum ada
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "attempts": 0,
            "offered_support": False,
            "awaiting_support_confirmation": False,
            "last_it_problem": "",
            "history": []
        }

    session = chat_sessions[session_id]

    # =====================================================
    # PENANGANAN KONFIRMASI ESKALASI IT SUPPORT
    # =====================================================

    if session["awaiting_support_confirmation"]:
        session["awaiting_support_confirmation"] = False

        if detect_confirmation(question):
            session["attempts"] = 0

            # Gunakan masalah IT terakhir sebagai query RAG agar lebih relevan
            query_for_rag = session["last_it_problem"] if session["last_it_problem"] else question

            guide = escalation_guide(query_for_rag, vector_store, embedding_service)

            return (
                "Baik, saya akan bantu mencarikan panduan eskalasi untuk Anda.\n\n"
                f"{guide}\n\n"
                "Semoga masalah Anda segera terselesaikan! Jika masih ada yang perlu ditanyakan, saya siap membantu."
            )

        else:
            session["offered_support"] = False
            return (
                "Baik, tidak apa-apa. Saya akan tetap berusaha membantu Anda di sini. "
                "Silakan ceritakan kembali masalahnya atau coba langkah yang belum dicoba, ya!"
            )

    # =====================================================
    # DETEKSI INTENT
    # =====================================================

    intent = detect_intent(question)
    logger.info(f"[Session: {session_id}] Intent terdeteksi: {intent} | Pertanyaan: {question[:80]}")

    # =====================================================
    # PENANGANAN BERDASARKAN INTENT
    # =====================================================

    if intent == "GENERAL_CHAT":
        answer = get_llm_response(question, session["history"], "small_talk")

    elif intent == "REQUEST_IT_SUPPORT":
        session["attempts"] = 0
        session["offered_support"] = False

        intro = (
            "Tentu! Saya akan langsung mencarikan panduan dari tim IT Support untuk Anda.\n\n"
        )
        guide = escalation_guide(question, vector_store, embedding_service)
        answer = intro + guide

    elif intent == "REJECT_IT_SUPPORT":
        session["offered_support"] = False
        answer = (
            "Baik, saya mengerti. Tidak apa-apa. "
            "Saya akan tetap berusaha membantu Anda menemukan solusi di sini. "
            "Silakan ceritakan lebih lanjut atau coba langkah lain yang belum dicoba!"
        )

    else:  # IT_PROBLEM

        session["last_it_problem"] = question

        answer = get_llm_response(
            question,
            session["history"],
            vector_store,
            embedding_service
        )

        session["attempts"] += 1

        if session["attempts"] >= 3 and not session["offered_support"]:

            session["offered_support"] = True
            session["awaiting_support_confirmation"] = True

            answer += (
                "\n\n---\n"
                "Saya melihat masalah ini cukup persisten dan beberapa solusi sudah dicoba.\n"
                "Saya dapat mencarikan **panduan eskalasi resmi dari tim IT Support**.\n\n"
                "Apakah Anda ingin saya bantu mengeceknya? (Ya / Tidak)"
            )

    # =====================================================
    # UPDATE HISTORY PERCAKAPAN
    # =====================================================

    session["history"].append({"role": "user", "content": question})
    session["history"].append({"role": "assistant", "content": answer})

    # Batasi history untuk menjaga performa (simpan 6 pesan terakhir = 3 giliran)
    if len(session["history"]) > 6:
        session["history"] = session["history"][-6:]

    return answer