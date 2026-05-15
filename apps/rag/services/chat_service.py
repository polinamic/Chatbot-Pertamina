"""
chat_service.py — IT Support Chatbot SITI (Production-Ready)
apps/rag/services/chat_service.py

Arsitektur Intent Detection (3 Layer):
  Layer 1: Rule-based regex   → instant, 0ms, deterministik (~80% kasus)
  Layer 2: Semantic Routing   → embedding cosine similarity (~10% kasus)
  Layer 3: LLM JSON fallback  → akurat tapi lambat (~10% kasus ambigu)

Intent yang didukung:
  - IT_PROBLEM      : Masalah teknis/troubleshoot (jalankan alur RAG)
  - SERVICE_ORDER   : Permintaan pengadaan/pemasangan barang/layanan IT
                      (langsung ke escalation_guide, skip RAG troubleshoot)
  - REQUEST_IT_SUPPORT: User minta dihubungkan ke tim IT manusia
  - REJECT_IT_SUPPORT : User menolak eskalasi
  - GENERAL_CHAT    : Sapaan/small talk
  - OUT_OF_SCOPE    : Pertanyaan di luar domain IT

Fitur utama:
  - OutOfScopeSemanticsDetector: tolak pertanyaan non-IT sebelum LLM dipanggil
  - rewrite_query_for_rag: contextual query rewriting untuk follow-up
  - get_context_for_session: session-level RAG caching, cegah cross-topic drift
  - failed_steps tracking: ingat langkah yang sudah gagal, tidak mengulang
  - Hardcoded DISCLAIMER: 100% muncul saat SOP tidak ditemukan (turn pertama)
  - _process_chat router: pisah sync/stream agar tidak ada campur yield+return
  - Konfirmasi Sudah/Belum: turn ke-2 menawarkan konfirmasi penyelesaian;
    jika "Belum" → langsung arahkan ke form Incident via escalation_guide DB

Perubahan v2 (Refactor):
  - HAPUS TOTAL: CATEGORY_FORMS dictionary (hardcode legacy)
  - HAPUS TOTAL: detect_problem_category(), get_ticket_process() (dead code)
  - HAPUS TOTAL: ROUTING_TEMPLATE_WITH_GUIDE / NO_GUIDE (tidak terpakai)
  - FIX escalation_guide: ekstraksi NAMA FORM & Link kini via Regex,
    menangani URL multi-baris / path terpotong secara utuh
  - FIX _is_valid_link: base URL pendek (tanpa path ≥ 8 char) = INVALID
  - FIX SERVICE_ORDER: query di-refine via _refine_service_order_query()
    sebelum masuk vector search agar keyword item dipertahankan
  - FIX fallback routing di get_llm_response: attempts>=1 → escalation_guide
    langsung (tanpa hardcode kategori)
"""

import os
import re
import json
import time
import logging
import threading
from typing import List, Dict, Optional, Generator, Tuple

import numpy as np

from apps.rag.models import DocumentChunk
from apps.rag.services.retrieval import retrieve_context
import ollama


# =====================================================
# STRUCTURED LOGGING — JsonFormatter
# =====================================================

class JsonFormatter(logging.Formatter):
    """Setiap log entry = satu baris JSON valid. Cocok untuk log aggregator."""
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "time" : self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg"  : record.getMessage(),
        }
        _SKIP = {
            "name","msg","args","levelname","levelno","pathname","filename",
            "module","exc_info","exc_text","stack_info","lineno","funcName",
            "created","msecs","relativeCreated","thread","threadName",
            "processName","process","message","taskName",
        }
        for key, val in record.__dict__.items():
            if key not in _SKIP:
                log_data[key] = val
        return json.dumps(log_data, ensure_ascii=False)


def _setup_logger(name: str) -> logging.Logger:
    """Setup logger dengan JsonFormatter. Aman dipanggil berkali-kali."""
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False  # Jangan propagate ke root Django logger
    return log


logger = _setup_logger("chatbot")


# =====================================================
# KONFIGURASI VIA ENVIRONMENT VARIABLE
# =====================================================

MODEL_NAME         = os.getenv("LLM_MODEL", "llama3:8b")
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))

# Threshold cosine similarity untuk RAG retrieval.
# Nilai 0.35 dengan all-mpnet-base-v2 dan IndexFlatIP:
#   "internet tidak bisa" vs "Tidak bisa terhubung ke internet" → ~0.45-0.55  ✓
#   "tolong bantu" vs "Tidak bisa terhubung ke internet"        → ~0.10-0.20  ✗
# Naikkan ke 0.50+ jika terlalu banyak false positive.
# Turunkan ke 0.30 jika terlalu banyak disclaimer "belum tersedia".
MIN_SIMILARITY_SCORE = float(os.getenv("MIN_SIMILARITY", "0.35"))

# Threshold cosine similarity untuk Semantic Routing (Layer 2).
# Nilai 0.65 cukup ketat — hanya match jika benar-benar mirip anchor.
SEMANTIC_THRESHOLD = float(os.getenv("SEMANTIC_THRESHOLD", "0.65"))

SYSTEM_RULE_CONTENT = (
    "Anda adalah AI IT Support perusahaan yang sangat kompeten.\n\n"
    "⚠️ INSTRUKSI BAHASA PALING KRITIS ⚠️\n"
    "WAJIB 100%: JAWAB HANYA DALAM BAHASA INDONESIA. DILARANG SEKALI INGGRIS.\n"
    "Pengecualian: istilah teknis saja (Cache, Login, Restart, VPN, DNS, BIOS).\n"
    "Jika user bertanya Inggris, TETAP jawab Bahasa Indonesia.\n\n"
    "ATURAN LAINNYA:\n"
    "1. Tunjukkan empati kepada pengguna.\n"
    "2. Jika ada panduan SOP di dalam konteks, IKUTI PERSIS panduan tersebut.\n"
    "3. JANGAN mengarang langkah-langkah di luar SOP tanpa disclaimer.\n"
    "4. Setiap langkah harus jelas dan mudah diikuti.\n"
    "5. Jangan langsung menyuruh eskalasi ke tim lain — coba dulu semua langkah lokal."
)

# Optimized LLM settings per use case.
# Key "reasoning" hanya dokumentasi — di-strip sebelum dikirim ke Ollama.
LLM_SETTINGS: Dict[str, Dict] = {
    # SOP-based: deterministic, ketat ikuti panduan
    "sop_strict": {
        "temperature": 0.0, "top_p": 0.85, "top_k": 20,
        "repeat_penalty": 1.2, "num_predict": 800, "mirostat": 0,
    },
    # General troubleshoot: sedikit lebih natural
    "troubleshoot_general": {
        "temperature": 0.35, "top_p": 0.92, "top_k": 40,
        "repeat_penalty": 1.15, "num_predict": 1000, "mirostat": 0,
    },
    # Fallback (tidak ada SOP): agak kreatif, tetap profesional
    "fallback_general": {
        "temperature": 0.40, "top_p": 0.93, "top_k": 50,
        "repeat_penalty": 1.1, "num_predict": 1500, "mirostat": 0,
    },
    # Sapaan / small talk: natural conversation
    "small_talk": {
        "temperature": 0.55, "top_p": 0.95, "top_k": 50,
        "repeat_penalty": 1.0, "num_predict": 200, "mirostat": 0,
    },
    # Intent classification: zero randomness
    "intent_detect": {
        "temperature": 0.0, "top_p": 0.9, "top_k": 10,
        "repeat_penalty": 1.0, "num_predict": 50, "mirostat": 0,
    },
    # Query rewriting: minimal drift
    "query_rewrite": {
        "temperature": 0.1, "top_p": 0.90, "top_k": 40,
        "repeat_penalty": 1.1, "num_predict": 200, "mirostat": 0,
    },
}


def get_llm_config(config_name: str = "sop_strict") -> dict:
    """Kembalikan Ollama options (tanpa key 'reasoning')."""
    config = LLM_SETTINGS.get(config_name, LLM_SETTINGS["sop_strict"])
    return {k: v for k, v in config.items() if k != "reasoning"}


# =====================================================
# SESSION MANAGER
# =====================================================

def _default_session() -> Dict:
    return {
        "attempts"                   : 0,
        "offered_support"            : False,
        "awaiting_support_confirmation": False,
        "last_it_problem"            : "",
        "cached_context"             : None,   # RAG context turn pertama — reuse untuk follow-up
        "failed_steps"               : [],     # Langkah yang sudah dicoba dan gagal
        "history"                    : [],
    }


class InMemorySessionManager:
    """Session storage di RAM. Hilang saat restart. Cocok untuk development."""
    def __init__(self):
        self._store: Dict[str, Dict] = {}

    def get(self, session_id: str) -> Dict:
        if session_id not in self._store:
            self._store[session_id] = _default_session()
        return self._store[session_id]

    def save(self, session_id: str, session: Dict) -> None:
        self._store[session_id] = session

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)


# Uncomment saat production (Redis):
# class RedisSessionManager: ...

session_manager = InMemorySessionManager()


# =====================================================
# LAYER 2: SEMANTIC ROUTING — OutOfScopeSemanticsDetector
#
# Tujuan: Tolak pertanyaan non-IT SEBELUM LLM dipanggil.
# Cara kerja: Hitung cosine similarity antara query user
# dengan "anchor embedding" tiap kategori out-of-scope.
# Jika similarity > SEMANTIC_THRESHOLD → OUT_OF_SCOPE.
#
# Mengapa sebelum LLM:
#   LLM bisa "tertipu" pertanyaan seperti "siapa pencipta wifi"
#   karena mengandung kata IT. Semantic routing menangkap
#   MAKNA kalimat, bukan hanya keyword.
#
# Performa: ~100ms per query (embedding call lokal, CPU).
# =====================================================

class OutOfScopeSemanticsDetector:
    """
    Deteksi out-of-scope menggunakan cosine similarity terhadap anchor embeddings.

    Anchor = kalimat representatif dari setiap kategori non-IT.
    Jika query user semantically mirip dengan salah satu anchor → OUT_OF_SCOPE.
    """

    def __init__(self, embedding_service, threshold: float = SEMANTIC_THRESHOLD):
        self.embedding_service = embedding_service
        self.threshold = threshold
        self.anchors: Dict[str, np.ndarray] = self._build_anchors()

    def _build_anchors(self) -> Dict[str, np.ndarray]:
        """
        Buat embedding untuk setiap anchor teks.
        Setiap kategori diwakili kalimat panjang agar embedding lebih representatif.
        """
        anchor_texts = {
            "craft_and_hobbies": (
                "tutorial cara membuat origami pesawat mainan kertas panduan DIY "
                "kerajinan tangan dari barang bekas cara membuat hiasan boneka"
            ),
            "culinary": (
                "resep memasak nasi goreng panduan membuat kue dari tepung "
                "cara membuat minuman smoothie tips chef memasak kuliner masakan"
            ),
            "entertainment": (
                "jokes lucu tentang wifi dan laptop kumpulan meme dan humor "
                "cerita lucu dan komedi film movie recommendations lagu musik artis"
            ),
            "advice_opinion": (
                "mending beli iphone atau android rekomendasi smartphone terbaik "
                "perbandingan produk laptop hp lenovo mana yang lebih baik saran beli gadget"
            ),
            "history_general": (
                "siapa pencipta wifi dan internet sejarah teknologi kapan ditemukan "
                "komputer pertama biografi tokoh penemu asal usul"
            ),
            "lifestyle": (
                "tips fashion dan pakaian panduan beauty makeup skincare relationship "
                "health fitness olahraga pertandingan bola zodiak cuaca ramalan"
            ),
            # "physical_damage": (
            #     "laptop lecet baret jatuh pecah layar retak body penyok "
            #     "cara membersihkan keyboard dari debu kotor cuci poles gosok"
            # ),
        }

        anchors = {}
        for category, text in anchor_texts.items():
            try:
                embedding = self.embedding_service.embed_text(text)
                anchors[category] = np.array(embedding, dtype=np.float32)
                logger.info("semantic_anchor_built", extra={"category": category})
            except Exception as e:
                logger.error("semantic_anchor_failed", extra={
                    "category": category, "error": str(e)
                })
        return anchors

    def detect(self, question: str) -> Tuple[Optional[str], float]:
        """
        Cek apakah question out-of-scope.

        Returns:
            (category_name, similarity_score) jika out-of-scope
            (None, 0.0) jika in-scope atau error
        """
        if not self.anchors:
            return (None, 0.0)

        try:
            q_embedding = np.array(
                self.embedding_service.embed_text(question), dtype=np.float32
            )

            best_category: Optional[str] = None
            best_similarity: float = 0.0

            for category, anchor_embedding in self.anchors.items():
                # Cosine similarity via dot product setelah normalisasi L2
                norm_q = q_embedding / (np.linalg.norm(q_embedding) + 1e-8)
                norm_a = anchor_embedding / (np.linalg.norm(anchor_embedding) + 1e-8)
                similarity = float(np.dot(norm_q, norm_a))

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_category = category

            if best_similarity > self.threshold:
                logger.info("semantic_oos_detected", extra={
                    "category": best_category,
                    "similarity": round(best_similarity, 3),
                    "threshold": self.threshold,
                    "query": question[:60],
                })
                return (best_category, best_similarity)

            return (None, 0.0)

        except Exception as e:
            logger.error("semantic_detection_error", extra={"error": str(e)})
            return (None, 0.0)  # Fail-safe: jangan crash, lanjutkan ke LLM


# Singleton detector — diinisialisasi saat pertama kali dibutuhkan.
# Lock untuk thread-safety (Django bisa handle request bersamaan).
_detector_instance: Optional[OutOfScopeSemanticsDetector] = None
_detector_lock = threading.Lock()


def get_semantic_detector(embedding_service) -> OutOfScopeSemanticsDetector:
    """
    Kembalikan singleton OutOfScopeSemanticsDetector.
    Thread-safe dengan double-check locking pattern.
    """
    global _detector_instance
    if _detector_instance is None:
        with _detector_lock:
            if _detector_instance is None:  # Double-check setelah acquire lock
                logger.info("semantic_detector_init", extra={
                    "threshold": SEMANTIC_THRESHOLD
                })
                _detector_instance = OutOfScopeSemanticsDetector(embedding_service)
    return _detector_instance


# =====================================================
# CORE LLM FUNCTIONS
# =====================================================

def generate_llm(
    messages: List[Dict[str, str]],
    temperature: float = None,
    config_name: str = "sop_strict",
) -> str:
    """Panggil LLM, kembalikan teks lengkap (non-streaming)."""
    # PENTING: Jangan duplikasi system message. 
    # Jika messages[0] sudah system, gunakan itu saja (sudah include SYSTEM_RULE_CONTENT).
    # Jika messages[0] bukan system, tambahkan SYSTEM_RULE_CONTENT.
    final_messages = messages
    if not messages or messages[0].get("role") != "system":
        final_messages = [{"role": "system", "content": SYSTEM_RULE_CONTENT}] + messages
    
    llm_config = get_llm_config(config_name)
    if temperature is not None:
        llm_config["temperature"] = temperature

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=final_messages,
            options=llm_config,
        )
        text = response.get("message", {}).get("content", "").strip()
        logger.info("llm_ok", extra={
            "config": config_name,
            "temp": llm_config["temperature"],
            "out_len": len(text),
        })
        return text if text else "Maaf, saya gagal memproses respons."
    except Exception as e:
        logger.error("llm_error", extra={"config": config_name, "error": str(e)})
        return "Sistem AI sedang gangguan teknis. Hubungi IT Support."


def generate_llm_stream(
    messages: List[Dict[str, str]],
    temperature: float = None,
    config_name: str = "sop_strict",
) -> Generator[str, None, None]:
    """Generator streaming — yield token per token ke client."""
    # PENTING: Jangan duplikasi system message.
    final_messages = messages
    if not messages or messages[0].get("role") != "system":
        final_messages = [{"role": "system", "content": SYSTEM_RULE_CONTENT}] + messages
    
    llm_config = get_llm_config(config_name)
    if temperature is not None:
        llm_config["temperature"] = temperature

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=final_messages,
            stream=True,
            options=llm_config,
        )
        for chunk in response:
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
        logger.info("llm_stream_ok", extra={"config": config_name})
    except Exception as e:
        logger.error("llm_stream_error", extra={"config": config_name, "error": str(e)})
        yield "Sistem AI sedang gangguan teknis. Hubungi IT Support."


# =====================================================
# QUERY REWRITING — Contextual RAG
#
# Masalah: "masih tidak bisa" tidak bisa di-query ke RAG
# karena tidak punya konteks. Perlu ditulis ulang menjadi:
# "wifi tidak bisa konek setelah mencoba forget network dan flush DNS"
#
# Perbaikan kritis dari versi sebelumnya:
# - Hanya kirim pesan USER ke rewriter (bukan jawaban bot)
#   → mencegah rewriter terpengaruh isi SOP di jawaban sebelumnya
# - original_problem sebagai anchor agar topik tidak bergeser
# - Skip rewrite jika pertanyaan sudah panjang/spesifik
# =====================================================

def rewrite_query_for_rag(
    question: str,
    history: List[Dict[str, str]],
    original_problem: str = "",
) -> str:
    """
    Tulis ulang pertanyaan user menjadi standalone query untuk RAG.
    Return original question jika tidak perlu rewrite.
    
    INSTRUKSI WAJIB:
    - Ekstrak HANYA pesan dengan role="user" dari history (bukan jawaban bot/SOP)
    - Gunakan original_problem sebagai anchor agar topik tidak berubah
    - Bertujuan mencegah LLM rewriter terpengaruh isi jawaban bot sebelumnya
    
    Contoh kasus penting:
      Turn 1: "wifi bermasalah"
      Bot jawab: "Coba cek apakah router berkedip..."
      Turn 2: User: "masih tidak bisa"
      
      SALAH: Kirim chatbot jawab → LLM rewriter bisa confused dengan instruksi teknis
      BENAR: Kirim hanya user messages + original_problem → "wifi tidak bisa" → RAG fokus
    """
    # Tidak perlu rewrite jika belum ada history atau pertanyaan sudah panjang
    if not history or len(question.split()) > 8:
        return question

    # INSTRUKSI KRITIS: Ambil HANYA pesan user (role="user"), skip assistant messages
    # Ini mencegah LLM rewriter terpengaruh oleh jawaban/instruksi bot di turn sebelumnya
    user_messages = [
        msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
        for msg in history[-6:]
        if msg["role"] == "user"
    ]

    if not user_messages:
        return question

    history_text = "\n".join(f"- {m}" for m in user_messages)
    anchor = f"Topik masalah utama: {original_problem}\n" if original_problem else ""

    rewrite_prompt = (
        f"{anchor}"
        f"Pesan-pesan user sebelumnya:\n{history_text}\n"
        f"Pesan terbaru: {question}\n\n"
        "Tugas: Tulis ulang pesan terbaru menjadi satu kalimat pencarian mandiri "
        "dalam Bahasa Indonesia untuk database pencarian.\n"
        "WAJIB: Pertahankan topik masalah yang SAMA, sertakan apa yang sudah dicoba.\n"
        "DILARANG: Mengubah topik, menambah masalah baru, atau menginterpretasi jawaban bot.\n"
        "Jawab HANYA dengan kalimat pencariannya saja, tanpa penjelasan."
    )

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": rewrite_prompt}],
            options=get_llm_config("query_rewrite"),
        )
        rewritten = response.get("message", {}).get("content", "").strip()

        if not rewritten or len(rewritten) < 5:
            return original_problem or question

        logger.info("query_rewritten", extra={
            "original": question[:60],
            "rewritten": rewritten[:60],
            "anchor": original_problem[:40],
            "user_messages_count": len(user_messages),
        })
        return rewritten

    except Exception as e:
        logger.warning("query_rewrite_failed", extra={"error": str(e)})
        return original_problem or question


# =====================================================
# INTENT DETECTION — 3 LAYER PIPELINE
# =====================================================

# ── Layer 1 patterns ──────────────────────────────────────
_ESCALATION_PATTERNS = re.compile(
    r'\b(hubungi|bicara dengan|minta tolong|it support|operator|teknisi|'
    r'helpdesk|eskalasi|bantuan manusia|'
    r'buat|buatlah|buatkan|membuat|'
    r'link|form|panduan|escalat|ticket|tiket)\b',
    re.IGNORECASE,
)
_REJECT_PATTERNS = re.compile(
    r'\b(jangan|batal|tidak perlu|ga usah|gak usah|cancel)\b',
    re.IGNORECASE,
)
_OUT_OF_SCOPE_OPINION_PATTERNS = re.compile(
    r'\b(mending beli|mana yang lebih baik|rekomendasi|saran beli|tips beli|review|review produk|perbandingan|yang terbaik|barang terbaik|pilih yang mana)\b',
    re.IGNORECASE,
)
# Sapaan singkat — diambil dari versi lama (lebih lengkap)
_GREETING_PATTERNS = re.compile(
    r'^(halo|hai|hi|hey|selamat\s+(pagi|siang|sore|malam)|good\s+(morning|afternoon)|'
    r'terima kasih|makasih|thanks|thank\s+you|oke|ok|sip|siap|noted|'
    r'permisi|saya ada pertanyaan.*|mau tanya.*|bisa bantu.*)[!.,\s]*$',
    re.IGNORECASE,
)
_ACCIDENT_PATTERNS = re.compile(
    r'\b(accident|kecelakaan|incident|kejadian)\b',
    re.IGNORECASE
    
)
# PEMBERSIHAN: _NON_IT_INTENT_PATTERNS telah dihapus sepenuhnya.
# Alasan: Layer 2 (OutOfScopeSemanticsDetector) dengan cosine similarity embedding
# sudah lebih akurat mendeteksi non-IT/out-of-scope queries dibanding regex manual.
# Regex manual terlalu rigid dan banyak false positives/negatives.
# Contoh:
#   - "siapa pencipta wifi" bisa terdeteksi salah jika user bilang "wifi creator"
#   - "jokes laptop" VS "laptop error" sama-sama ada "laptop", regex bingung
#   - "laptop lecet" (physical) VS "laptop tidak menyala" (IT) sulit dibedakan regex
# Layer 2 semantic routing menangani ini dengan makna (embedding), tidak keyword matching.
# Kalimat yang JELAS butuh bantuan IT teknis
_IT_PROBLEM_PATTERNS = re.compile(
    r'\b((?:file|data|folder|aplikasi|program|sistem)\s+hilang|'
    r'tidak\s+bisa|gabisa|nggak\s+bisa|tidak\s+berfungsi|tidak\s+konek|'
    r'error|eror|hang|freeze|lambat|lemot|mati|rusak|bermasalah|'
    r'gagal|fail|crash|bluescreen|blue\s+screen|not\s+responding|'
    r'lupa\s+password|reset\s+password|tidak\s+bisa\s+login|'
    r'terkunci|'
    r'tidak\s+terdeteksi|tidak\s+muncul|tidak\s+nyambung|putus|'
    r'install|uninstall|update|upgrade|setting|konfigurasi|setup|'
    # Ketidakstabilan koneksi/jaringan/perangkat
    r'tidak\s+stabil|nggak\s+stabil|ga\s+stabil|kurang\s+stabil|'
    r'sering\s+putus|putus[\s-]putus|'
    r'gangguan|terganggu|'
    # Sinyal lemah — match 0-2 kata di antara 'sinyal' dan 'lemah'/'buruk'
    r'sinyal\s+(?:\w+\s+){0,2}lemah|sinyal\s+(?:\w+\s+){0,2}buruk|'
    r'signal\s+(?:\w+\s+){0,2}lemah|'
    # Koneksi drop/terputus
    r'koneksi\s+drop|koneksi\s+terputus|'
    # Intent perbaikan — "cara memperbaiki/mengatasi X"
    r'cara\s+memperbaiki|cara\s+mengatasi|'
    r'bagaimana\s+cara\s+(?:memperbaiki|mengatasi|fix|repair)|'
    # Tidak terhubung
    r'tidak\s+(?:bisa\s+)?terhubung|'
    # Istilah teknis jaringan (dibatasi konteks IT agar tidak false positive)
    r'disconnect|offline|'
    r'(?:sistem|server|layanan|aplikasi|jaringan)\s+down)\b',
    re.IGNORECASE,
)

# ── SERVICE_ORDER pattern — Layer 1 ──────────────────────────────────────────
# Mendeteksi permintaan pengadaan, pemesanan, atau pemasangan item/layanan IT.
# Berbeda dari IT_PROBLEM (troubleshoot kerusakan/error), SERVICE_ORDER adalah
# request aktif user untuk mendapatkan/memasang sesuatu yang BELUM ADA atau
# sengaja diminta baru.
#
# Contoh match:
#   "pesan printer"   → SERVICE_ORDER  (bukan: "printer tidak terdeteksi" → IT_PROBLEM)
#   "order cctv"      → SERVICE_ORDER
#   "pasang wifi"     → SERVICE_ORDER  (bukan: "wifi tidak bisa konek" → IT_PROBLEM)
#   "pengadaan laptop"→ SERVICE_ORDER
#   "peminjaman notebook" → SERVICE_ORDER (PERBAIKAN: tambah pattern ini)
#   "pesenin HT baru" → SERVICE_ORDER  (colloquial "pesan")
#
# KRITIS: Pola ini harus dicek SEBELUM _IT_PROBLEM_PATTERNS agar kata seperti
# "pasang" atau "install" pada konteks pengadaan tidak jatuh ke IT_PROBLEM.
_SERVICE_ORDER_PATTERNS = re.compile(
    r'(?:'
    # "pesan X" / "pesenin X" / "order X" — pemesanan item dengan/tanpa kata depan
    # Catches: pesan, pesenin, pesen, order, pinjam, peminjaman, dll
    r'(?:mau\s+|ingin\s+|minta\s+|butuh\s+|perlu\s+|tolong\s+)?(?:pesen|pesan|order|pinjam|peminjaman)\w*\s+\w+'
    # "baru" keyword di tengah atau akhir kalimat menunjukkan pengadaan item baru
    r'|\b(?:HT|handset|handy.?talky|laptop|notebook|tablet|printer|monitor|mouse|keyboard|headset|webcam|cctv|kamera|proyektor|switch|router|server|harddisk|ssd|memori|keyboard|perangkat)\b.*\bBARU\b'
    # "pasang X" — pemasangan fisik perangkat/layanan IT
    r'|pasang\s+(?:wifi|wi-fi|cctv|kamera|jaringan|telepon|printer|proyektor|internet|vpn|lan|switch|access\s*point)'
    # "pengadaan X" — permintaan pengadaan resmi
    r'|\bpengadaan\b'
    # "ajukan/pengajuan perangkat/layanan" — formulir pengajuan
    r'|\b(?:ajukan|pengajuan)\s+(?:perangkat|layanan|akses|hardware|software|laptop|komputer|printer|cctv|handset|HT)'
    r')',
    re.IGNORECASE,
)

# ── Layer 3 system prompt ─────────────────────────────────
_INTENT_SYSTEM_PROMPT = (
    "Kamu adalah classifier intent untuk chatbot IT Support perusahaan.\n"
    "Tugasmu: tentukan apakah user butuh BANTUAN TEKNIS IT, atau bukan.\n\n"
    "Jawab HANYA dengan JSON:\n"
    '{"intent": "<LABEL>"}\n\n'
    "LABEL:\n"
    "- IT_PROBLEM         : User MENGALAMI masalah teknis atau butuh panduan IT\n"
    "- SERVICE_ORDER      : User MEMESAN atau MEMINTA PENGADAAN perangkat/layanan IT baru\n"
    "                       (belum rusak, tapi minta dipasang/dipesan/diadakan)\n"
    "- REQUEST_IT_SUPPORT : User minta dihubungkan ke tim IT manusia\n"
    "- REJECT_IT_SUPPORT  : User menolak eskalasi\n"
    "- GENERAL_CHAT       : Sapaan singkat saja (halo, terima kasih, ok)\n"
    "- OUT_OF_SCOPE       : Pertanyaan yang BUKAN tentang masalah IT\n\n"
    "=== CRITICAL RULES ===\n"
    "1. Masalah TEKNIS/MALFUNCTION perangkat IT = IT_PROBLEM (keyboard tidak berfungsi)\n"
    "2. PEMESANAN/PENGADAAN perangkat atau layanan IT = SERVICE_ORDER\n"
    "   Keywords: pesan, pesenin, order, pinjam, peminjaman, pengadaan, pasang, ajukan, minta\n"
    "   + New items: HT baru, laptop baru, printer baru, notebook baru, tablet baru\n"
    "   (Contoh: pesan printer, order cctv, pasang wifi, pengadaan laptop)\n"
    "3. Pertanyaan EDUKASI tentang teknologi (tanpa masalah) = OUT_OF_SCOPE\n"
    "4. KERUSAKAN FISIK atau PEMBERSIHAN perangkat = OUT_OF_SCOPE\n"
    "   (Contoh: laptop lecet, keyboard kotor, rusak fisik, goresan, penyok)\n"
    "5. Pertanyaan tentang Rekomendasi/opini produk atau saran beli = OUT_OF_SCOPE\n"
    "6. Pertanyaan tentang SEJARAH/PEMBUAT teknologi = OUT_OF_SCOPE\n"
    "7. Tutorial/Panduan/Cara MEMBUAT sesuatu (non-IT) = OUT_OF_SCOPE\n\n"
    "=== FEW-SHOT EXAMPLES ===\n\n"
    "CONTOH SERVICE_ORDER (PENGADAAN/PEMESANAN):\n"
    "  1. 'pesan printer untuk ruangan saya'           → SERVICE_ORDER\n"
    "  2. 'order cctv baru'                            → SERVICE_ORDER\n"
    "  3. 'pasang wifi di ruang meeting'               → SERVICE_ORDER\n"
    "  4. 'minta pengadaan laptop baru'                → SERVICE_ORDER\n"
    "  5. 'bisa tolong pasang access point di sini'    → SERVICE_ORDER\n"
    "  6. 'tolong dong pesenin HT baru'                → SERVICE_ORDER (colloquial: pesenin=pesan)\n"
    "  7. 'mau order notebook baru dong'               → SERVICE_ORDER\n"
    "  8. 'butuh tablet baru untuk tim'                → SERVICE_ORDER\n"
    "  9. 'pengajuan printer untuk kantor cabang'      → SERVICE_ORDER\n"
    "  10. 'minta handset baru donk'                   → SERVICE_ORDER\n\n"
    "CONTOH OUT_OF_SCOPE (BUKAN masalah IT)::\n"
    "  1. 'siapa pencipta wifi'                        → OUT_OF_SCOPE (sejarah/edukasi)\n"
    "  2. 'berikan jokes tentang wifi'                 → OUT_OF_SCOPE (hiburan)\n"
    "  3. 'mending beli iPhone atau Android'           → OUT_OF_SCOPE (opini/rekomendasi produk)\n"
    "  4. 'bagaimana cara kerja VPN'                   → OUT_OF_SCOPE (edukasi, bukanmasalah)\n"
    "  5. 'cara membuat origami pesawat dari kertas'   → OUT_OF_SCOPE (kerajinan)\n"
    "  5. 'bagaimana resep soto ayam'                  → OUT_OF_SCOPE (kuliner)\n"
    "  6. 'laptop jatuh dan lecet fisik'               → OUT_OF_SCOPE (kerusakan fisik)\n"
    "  7. 'cara membersihkan keyboard dari debu'       → OUT_OF_SCOPE (pembersihan fisik)\n"
    "  8. 'cara membuat hiasan gantungan kunci'        → OUT_OF_SCOPE (kerajinan DIY)\n"
    "  9. 'siapa presiden indonesia'                   → OUT_OF_SCOPE (pengetahuan umum)\n"
    "  10. 'apakah tuhan ada'                          → OUT_OF_SCOPE (agama/filsafat))\n\n"
    "CONTOH IT_PROBLEM (MASALAH TEKNIS)::\n"
    "  1. 'wifi saya tidak bisa konek'                 → IT_PROBLEM (malfunction)\n"
    "  2. 'vpn saya error dan lambat'                  → IT_PROBLEM (performance issue)\n"
    "  3. 'lupa password domain'                       → IT_PROBLEM (account/access)\n"
    "  4. 'keyboard tidak berfungsi'                   → IT_PROBLEM (hardware malfunction)\n"
    "  5. 'laptop saya sangat lambat'                  → IT_PROBLEM (performance)\n"
    "  6. 'tidak bisa login email perusahaan'          → IT_PROBLEM (access issue)\n"
    "  7. 'printer tidak terdeteksi'                   → IT_PROBLEM (connectivity)\n"
    "  8. 'aplikasi saya crash/error'                  → IT_PROBLEM (software issue)\n"
    "  9. 'bagaimana cara reset password'              → IT_PROBLEM (bantuan teknis)\n"
    "  10. 'file saya tiba-tiba hilang'                → IT_PROBLEM (data issue)\n"
)


def detect_intent_rules(question: str) -> Optional[str]:
    """
    Layer 1: Rule-based regex — hanya untuk kasus yang 100% pasti.
    Return None jika tidak yakin → lanjut ke Layer 2 (Semantic) / Layer 3 (LLM).
    
    Pola yang tersisa:
    - ESCALATION_PATTERNS : "hubungi IT Support", "minta siapa/operator", dll
    - REJECT_PATTERNS     : "batal", "cancel", dll
    - GREETING_PATTERNS   : "halo", "terima kasih", "ok", dll
    - SERVICE_ORDER_PATTERNS: "pesan printer", "order cctv", "pasang wifi", dll
    - IT_PROBLEM_PATTERNS : "tidak bisa", "error", "install", "lupa password", dll
    
    URUTAN KRITIS:
    SERVICE_ORDER WAJIB dicek SEBELUM IT_PROBLEM agar "pasang wifi" (pengadaan)
    tidak jatuh ke IT_PROBLEM karena kata "wifi" juga ada di pola IT.
    
    OUT_OF_SCOPE detection sudah dipindah ke Layer 2 (Semantic Routing)
    menggunakan cosine similarity embedding untuk akurasi lebih tinggi.
    """
    q = question.strip()

    if _ESCALATION_PATTERNS.search(q):     return "REQUEST_IT_SUPPORT"
    if _REJECT_PATTERNS.search(q):         return "REJECT_IT_SUPPORT"
    if _GREETING_PATTERNS.match(q):        return "GENERAL_CHAT"
    if _SERVICE_ORDER_PATTERNS.search(q):  return "SERVICE_ORDER"   # ← SEBELUM IT_PROBLEM
    if _IT_PROBLEM_PATTERNS.search(q):     return "IT_PROBLEM"
    if _OUT_OF_SCOPE_OPINION_PATTERNS.search(q): return "OUT_OF_SCOPE"

    return None  # Ambigu → lanjut ke Layer 2 (Semantic) atau Layer 3 (LLM)


def detect_intent_llm_fallback(question: str) -> str:
    """
    Layer 3: LLM JSON classifier — dipanggil jika Layer 1 & 2 tidak yakin.
    Pakai format="json" untuk output terstruktur + fallback string parsing.
    """
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            format="json",
            options=get_llm_config("intent_detect"),
        )
        raw    = response.get("message", {}).get("content", "").strip()
        parsed = json.loads(raw)
        intent = parsed.get("intent", "").strip().upper()

        valid = {"REQUEST_IT_SUPPORT","REJECT_IT_SUPPORT","GENERAL_CHAT","IT_PROBLEM","OUT_OF_SCOPE","SERVICE_ORDER"}
        if intent in valid:
            return intent

    except (json.JSONDecodeError, Exception) as e:
        logger.warning("intent_json_parse_failed", extra={"error": str(e)})
        # Fallback: string matching pada raw output
        raw_text = response.get("message", {}).get("content", "").upper() \
                   if 'response' in locals() else ""
        for intent in ["REQUEST_IT_SUPPORT","REJECT_IT_SUPPORT","OUT_OF_SCOPE","SERVICE_ORDER","GENERAL_CHAT","IT_PROBLEM"]:
            if intent in raw_text:
                return intent

    logger.warning("intent_detection_fallback_used", extra={"question": question[:80]})
    return "IT_PROBLEM"  # Safe default


def detect_intent(question: str, embedding_service=None) -> str:
    """
    Entry point intent detection: 3-layer pipeline FINAL ARCHITECTURE.

    INSTRUKSI WAJIB (Poin 3 dari 5):
    Layer 2 (Semantic Routing) WAJIB dipanggil SETELAH Layer 1 (Rules)
    dan SEBELUM Layer 3 (LLM Fallback), menggunakan cosine similarity.

    Pipeline:
      Layer 1 (RULES)
        ├─ Instant keputusan untuk: Escalation, Reject, Greeting, IT_Problem
        ├─ Performa: < 1ms, 100% deterministic
        └─ Coverage: ~80% kasus standar

      Layer 2 (SEMANTIC ROUTING) ← PENDETEKSI OUT_OF_SCOPE UTAMA
        ├─ Cosine similarity embedding vs anchor texts
        ├─ Tolerance: jika tidak menemukan akan fallback ke Layer 3
        ├─ Performa: ~100-200ms per query (embedding call)
        └─ Coverage: ~10% kasus out-of-scope (craft, culinary, physical damage, dll)

      Layer 3 (LLM FALLBACK)
        ├─ JSON format classification dengan Few-Shot examples
        ├─ Performa: ~500ms-2s (depends on model)
        └─ Coverage: ~10% kasus ambigu/edge case

    PERBAIKAN DARI VERSI LAMA:
    - Hapus _NON_IT_INTENT_PATTERNS dari Layer 1 (pindah ke Layer 2)
    - Layer 2 sekarang menangani OUT_OF_SCOPE detection dengan semantic understanding
    - LLM prompt (Layer 3) diperkaya dengan Few-Shot examples
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LAYER 1: RULE-BASED CLASSIFICATION (Instant)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    rule_result = detect_intent_rules(question)
    if rule_result:
        logger.info("intent_detected", extra={
            "intent_source": "layer1_rules",
            "intent": rule_result,
            "confidence": 0.95,
            "latency_ms": "<1",
        })
        return rule_result

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LAYER 2: SEMANTIC ROUTING (Cosine Similarity)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if embedding_service:
        try:
            detector = get_semantic_detector(embedding_service)
            semantic_category, similarity = detector.detect(question)
            if semantic_category:
                logger.info("intent_detected", extra={
                    "intent_source": "layer2_semantic_routing",
                    "intent": "OUT_OF_SCOPE",
                    "category": semantic_category,
                    "similarity": round(similarity, 3),
                    "threshold": SEMANTIC_THRESHOLD,
                    "confidence": round(similarity, 3),
                    "latency_ms": "~100-200",
                })
                return "OUT_OF_SCOPE"
            else:
                logger.debug("layer2_semantic_no_match", extra={
                    "question": question[:80],
                    "best_similarity": round(similarity, 3),
                    "threshold": SEMANTIC_THRESHOLD,
                })
        except Exception as e:
            # Semantic layer gagal → lanjut ke LLM, jangan crash
            logger.warning("layer2_semantic_error", extra={
                "error": str(e),
                "fallback": "to_layer3_llm"
            })

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LAYER 3: LLM JSON CLASSIFIER (Fallback untuk kasus ambigu)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    llm_result = detect_intent_llm_fallback(question)
    logger.info("intent_detected", extra={
        "intent_source": "layer3_llm_fallback",
        "intent": llm_result,
        "confidence": 0.75,
        "latency_ms": "~500-2000",
        "reason": "ambiguous_query",
    })
    return llm_result


# =====================================================
# RAG CONTEXT RETRIEVAL
# =====================================================

def _estimate_tokens(text: str) -> int:
    """Estimasi kasar: 1 token ≈ 4 karakter."""
    return len(text) // 4


def build_context_with_limit(
    chunks: List[str],
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> str:
    """
    Gabungkan chunks SOP hingga batas token.
    Chunk pertama (paling relevan dari RAG) diprioritaskan.
    Chunk yang tidak muat di-skip (tidak dipotong) agar tidak ada konten terpotong.
    """
    total_tokens = 0
    selected = []

    for chunk in chunks:
        chunk_tokens = _estimate_tokens(chunk)
        if total_tokens + chunk_tokens <= max_tokens:
            selected.append(chunk)
            total_tokens += chunk_tokens
        else:
            logger.warning("context_truncated", extra={
                "used_tokens"         : total_tokens,
                "skipped_chunk_tokens": chunk_tokens,
            })
            break

    return "\n\n---\n\n".join(selected)


def get_relevant_context(
    question: str,
    vector_store,
    embedding_service,
) -> Optional[str]:
    """
    Ambil konteks RAG. Return None jika tidak ada yang cukup relevan.
    Log setiap chunk yang ditemukan untuk debugging cross-topic drift.
    """
    if not vector_store or not embedding_service:
        return None

    results = retrieve_context(
        question, vector_store, embedding_service,
        doc_type="TROUBLESHOOT", top_k=3,
    )

    if not results:
        logger.info("rag_no_results", extra={"query": question[:60]})
        return None

    relevant = [r for r in results if r.get("score", 0) >= MIN_SIMILARITY_SCORE]

    if not relevant:
        top_score = max((r.get("score", 0) for r in results), default=0)
        logger.info("rag_below_threshold", extra={
            "threshold": MIN_SIMILARITY_SCORE,
            "top_score": round(top_score, 3),
            "query"    : question[:60],
        })
        return None

    for r in relevant:
        logger.info("rag_found", extra={
            "score"          : round(r.get("score", 0), 3),
            "content_preview": r["content"][:80],
        })

    texts = [r["content"] for r in relevant]
    return build_context_with_limit(texts)


def get_context_for_session(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
) -> Optional[str]:
    """
    Session-level RAG caching — fix utama untuk cross-topic drift.

    Turn 1: Panggil RAG → simpan hasilnya di session["cached_context"]
    Turn 2+: Pakai cached_context, TIDAK panggil RAG lagi

    Mengapa ini penting:
      Turn 1: "wifi bermasalah"  → RAG → chunk WIFI ✓
      Turn 2: "masih bermasalah" → RAG bisa return chunk PRINTER ✗
      Dengan cache: Turn 2 selalu pakai chunk WIFI dari Turn 1 ✓

    Cache direset saat user memulai masalah baru (attempts == 0).
    """
    if session["attempts"] == 0 or session["cached_context"] is None:
        context = get_relevant_context(question, vector_store, embedding_service)
        session["cached_context"] = context
        logger.info("rag_cache_set", extra={
            "found": context is not None,
            "query": question[:60],
        })
        return context

    logger.info("rag_cache_hit", extra={"attempts": session["attempts"]})
    return session["cached_context"]


# =====================================================
# PROACTIVE CLARIFICATION
# =====================================================

# Gabungan dari versi baru (youtube, jaringan, koneksi) dan lama (email, printer)
_CLARIFICATION_TRIGGERS = {
    r'\blaptop\b'                                        : "Laptop bermasalah dalam hal apa? (Tidak menyala / Layar hitam / Lambat / Lainnya?)",
    r'\bkomputer\b|\bpc\b'                               : "Komputer bermasalah dalam hal apa? (Tidak menyala / Lambat / Error tertentu?)",
    r'\bprinter\b'                                       : "Printer bermasalah bagaimana? (Tidak terdeteksi / Hasil cetakan buruk / Antrean nyangkut?)",
    r'\binternet\b|\bwifi\b|\bwi-fi\b|\bjaringan\b|\bkoneksi\b': "Masalah koneksinya seperti apa? (Tidak konek sama sekali / Lambat / Sering putus? Pakai Wi-Fi atau kabel LAN?)",
    r'\bemail\b'                                         : "Email bermasalah bagaimana? (Tidak bisa login / Tidak bisa kirim-terima / Lainnya?)",
    r'\byoutube\b|\bvideo\b|\bstreaming\b'               : "Terkait hal tersebut, apakah masalahnya ada di koneksi internet (putus/lambat) atau perangkat (kamera/suara tidak muncul)?",
}


def needs_clarification(question: str, history: List[Dict]) -> Optional[str]:
    """
    Tanya balik jika pertanyaan terlalu ambigu.
    Tidak tanya jika sudah ada history atau pertanyaan sudah panjang (>6 kata).
    Threshold >6 kata dari versi lama — lebih konservatif dari >15.
    """
    if history:                         return None
    if len(question.split()) > 6:       return None

    q_lower = question.lower()
    for pattern, msg in _CLARIFICATION_TRIGGERS.items():
        if re.search(pattern, q_lower):
            return msg
    return None


# =====================================================
# ESCALATION GUIDE (REWRITTEN - DATABASE DRIVEN)
# =====================================================
# NOTE: get_ticket_process() DELETED - replaced by escalation_guide()
# ===== DELETED: _is_valid_link() and _extract_form_info() =====
# These were helper functions for old category-based escalation routing
# New dynamic approach handles validation within escalation_guide()


CATEGORY_FORMS = {  # DEPRECATED — dihapus, hanya placeholder agar tidak NameError jika ada referensi sisa
    # Seluruh dictionary ini dikosongkan. Routing sepenuhnya dilakukan oleh
    # Vector Store / RAG via escalation_guide(). Tidak ada hardcode kategori di sini.

}



# =====================================================
# SERVICE ORDER QUERY PREPROCESSOR (FIX 4)
# =====================================================
# Kata kunci item/perangkat IT yang relevan untuk SERVICE_ORDER.
# Pattern ini digunakan oleh _refine_service_order_query() untuk
# mengekstrak entitas barang dari query mentah user sebelum
# dilempar ke vector search. Tanpa ini, kata kerja noise seperti
# "saya ingin melakukan peminjaman untuk mitra kerja" mendominasi
# embedding sehingga vector search salah memilih form.
_SERVICE_ITEM_KEYWORDS = re.compile(
    r'\b(laptop|notebook|komputer|pc|desktop|printer|monitor|keyboard|mouse|'
    r'scanner|proyektor|cctv|kamera|wifi|wi[\-]fi|lan|switch|router|'
    r'access\s*point|telepon|telephone|handset|handphone|hp\s+kantor|tablet|'
    r'ups|server|storage|toner|flashdisk|flash\s*disk|harddisk|ssd|ram|'
    r'headset|webcam|sim\s*card|simcard|software|lisensi|license|vpn|'
    r'akses|access|id\s+user|user\s+id|email|mailbox|radio|handy\s*talky|ht)\b',
    re.IGNORECASE,
)


def _refine_service_order_query(question: str) -> str:
    """
    Preprocessing query SERVICE_ORDER sebelum masuk ke escalation_guide.

    Masalah (root cause bug "IT Supplies" untuk "peminjaman notebook"):
    Query mentah "saya ingin melakukan peminjaman notebook untuk mitra kerja"
    mengandung noise kata kerja tinggi. Embedding-nya didominasi semantik
    "melakukan peminjaman untuk mitra kerja" bukan "notebook/laptop".
    Vector search lalu return form "IT Supplies" (toner, flashdisk, aksesoris)
    karena embedding-nya lebih dekat ke semantik generic "permintaan barang".

    Solusi: Ekstrak kata kunci item IT yang eksplisit → buat query bersih
    dengan format "<action> <item>" sehingga vector search fokus ke entitas
    barangnya, bukan kata kerjanya.

    Contoh:
      Input : "saya ingin melakukan peminjaman notebook untuk mitra kerja"
      Output: "peminjaman laptop notebook"

      Input : "tolong pasang wifi di ruang meeting lantai 3"
      Output: "pasang wifi"

      Input : "pengadaan komputer baru untuk tim saya"
      Output: "pengadaan komputer"
    """
    item_matches = _SERVICE_ITEM_KEYWORDS.findall(question)

    if not item_matches:
        # Tidak ada keyword item spesifik → kembalikan query original
        logger.debug("service_order_no_item_keyword", extra={"question": question[:80]})
        return question

    # Deduplicate, preserve order, lowercase
    seen: set = set()
    unique_items = []
    for m in item_matches:
        key = m.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_items.append(key)

    # Normalise sinonim yang paling umum agar vector lebih presisi
    _SYNONYM_MAP = {"notebook": "laptop", "komputer": "komputer desktop", "hp kantor": "handset"}
    unique_items = [_SYNONYM_MAP.get(i, i) for i in unique_items]

    # Tentukan action intent dari query
    if re.search(r'\b(pinjam|peminjaman|meminjam)\b', question, re.IGNORECASE):
        action = "peminjaman"
    elif re.search(r'\b(pengadaan|pesan|order|memesan|minta)\b', question, re.IGNORECASE):
        action = "pengadaan"
    elif re.search(r'\b(pasang|pemasangan|instalasi|install)\b', question, re.IGNORECASE):
        action = "pemasangan"
    elif re.search(r'\b(ajukan|pengajuan)\b', question, re.IGNORECASE):
        action = "pengajuan"
    else:
        action = "permintaan"

    refined = f"{action} {' '.join(unique_items)}"

    logger.info("service_order_query_refined", extra={
        "original" : question[:80],
        "refined"  : refined,
        "items"    : unique_items,
        "action"   : action,
    })
    return refined


def escalation_guide(query_issue: str, vector_store, embedding_service, doc_type: str = "ORDER_LINK") -> str:
    """
    Database-driven escalation guide menggunakan Vector + BM25 search.

    TIDAK ADA HARDCODE DICTIONARY. Semua routing dinamis dari database.

    Args:
        query_issue   : Query/deskripsi masalah user (sebaiknya sudah di-refine)
        vector_store  : Vector store untuk semantic search
        embedding_service: Embedding service untuk encoding vektor
        doc_type      : Tipe dokumen ('ORDER_LINK' atau 'INCIDENT_LINK')

    Returns:
        String berisi NAMA FORM dan Link jika ditemukan, atau pesan fallback.

    Ekstraksi NAMA FORM dan Link menggunakan Regex (FIX 2):
    - Tidak lagi split() berbasis posisi karakter → rapuh terhadap format bervariasi.
    - Regex menangkap seluruh URL secara utuh, termasuk path, hash (#), query (?),
      meskipun URL terpotong baris baru di dalam chunk database.
    """
    try:
        logger.info("escalation_guide_request", extra={
            "query"   : query_issue[:80],
            "doc_type": doc_type,
        })

        if doc_type == "INCIDENT_LINK":
            # Bypass semantic search for incident escalation and load the incident doc directly.
            chunk = DocumentChunk.objects.filter(content__contains='type: INCIDENT_LINK').first()
            results = []

            if chunk and chunk.content:
                results.append({
                    "content": chunk.content,
                    "score": 0,
                })
        else:
            results = retrieve_context(
                query_issue, vector_store, embedding_service,
                doc_type=doc_type, top_k=3,
            )

        # Iterate over all results to find first valid link
        for candidate_idx, result in enumerate(results):
            if not result.get("content"):
                continue

            content = result["content"]
            score   = result.get("score") or 0

            # If the retrieved chunk contains multiple YAML-style sections,
            # prefer the first matching block for the requested doc_type.
            block_pattern = rf'(?ms)^---\s*type:\s*{re.escape(doc_type)}\b.*?(?=^---\s*type:|\Z)'
            block_match = re.search(block_pattern, content, re.MULTILINE | re.IGNORECASE)
            block_content = block_match.group(0) if block_match else content

            # ── FIX 2: Ekstraksi NAMA FORM (title) via Regex ─────────────────────────
            # Pattern mencari baris yang diawali dengan "title: "
            form_match = re.search(
                r'^title:\s*(.+?)(?:\n|$)',
                block_content,
                re.MULTILINE | re.IGNORECASE,
            )
            form_name = form_match.group(1).strip() if form_match else None

            # ── FIX 2: Ekstraksi Link (url) via Regex (URL-safe, multi-line) ───────
            content_normalized = re.sub(r'\n\s*(?=[/#?&])', '', block_content)

            # Pattern mencari baris yang diawali dengan "url: "
            link_match = re.search(
                r'^url:\s*(https?://\S+)',
                content_normalized,
                re.MULTILINE | re.IGNORECASE,
            )
            link = link_match.group(1).rstrip('.,;)') if link_match else None

            logger.debug("escalation_guide_candidate", extra={
                "candidate_idx": candidate_idx,
                "form_name": form_name,
                "link"     : (link or "")[:120],
                "score"    : round(score, 3),
                "doc_type" : doc_type,
            })

            if form_name:
                fallback_link = "https://myssc.pertamina.com/dwp/app/"
                if link and _is_valid_link(link):
                    logger.info("escalation_guide_valid_found", extra={
                        "form_name": form_name,
                        "link"     : link,
                        "score"    : round(score, 3),
                        "candidate_idx": candidate_idx,
                        "doc_type" : doc_type,
                    })
                    return (
                        f"Untuk menangani hal ini, silakan buat tiket melalui link berikut:\n\n"
                        f"📋 **NAMA FORM:** {form_name}\n\n"
                        f"🔗 **Link:** {link}"
                    )

                logger.warning("escalation_guide_invalid_link", extra={
                    "form_name": form_name,
                    "link"     : (link or "none"),
                    "doc_type" : doc_type,
                    "score"    : score,
                    "candidate_idx": candidate_idx,
                })
                return (
                    f"Untuk menangani hal ini, silakan buat tiket melalui link berikut:\n\n"
                    f"📋 **NAMA FORM:** {form_name}\n\n"
                    f"🔗 **Link:** {fallback_link}"
                )

        # ── Fallback: tidak ada hasil valid dari semua kandidat ──────────────────────────────────────────
        logger.info("escalation_guide_no_valid_match", extra={
            "query"   : query_issue[:60],
            "doc_type": doc_type,
            "candidates_tried": len(results),
        })
        return (
            "Panduan spesifik untuk permintaan ini belum tersedia di database.\n\n"
            "Silakan kunjungi Portal IT Support untuk membuat tiket secara manual.\n\n"
            "Tim IT kami siap membantu Anda selanjutnya!"
        )

    except Exception as e:
        logger.error("escalation_guide_error", extra={
            "error"   : str(e),
            "doc_type": doc_type,
        })
        return (
            "Terjadi kesalahan saat mengambil panduan eskalasi.\n\n"
            "Silakan hubungi IT Support melalui Portal IT Support."
        )


def _is_valid_link(link: str) -> bool:
    """
    Validasi bahwa link adalah URL spesifik yang benar-benar mengarah ke form.

    FIX 3 — Perketat validasi:
    Base URL yang pendek/tanpa path spesifik dianggap TIDAK VALID agar sistem
    tidak menampilkan link yang tidak berguna kepada user.

    VALID   : https://myssc.pertamina.com/dwp/app/#/catalog-form/preview-form/75
    INVALID : https://myssc.pertamina.com/          ← hanya base URL, path < 4 char
    INVALID : https://myssc.pertamina.com/dwp/      ← path terlalu pendek/generik
    INVALID : [LINK_BELUM_TERSEDIA]                 ← placeholder
    """
    from urllib.parse import urlparse

    if not link:
        return False

    link_lower = link.lower()

    # Tolak placeholder eksplisit
    _PLACEHOLDERS = (
        '[link_belum_tersedia', '[belum', 'not available',
        'tbd', 'null', 'n/a', 'belum tersedia',
    )
    if any(p in link_lower for p in _PLACEHOLDERS):
        return False

    # Parse URL dan periksa komponen
    try:
        parsed = urlparse(link)
    except Exception:
        return False

    # Harus scheme http/https dan netloc ada
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return False

    # ── INTI FIX 3: path harus spesifik ─────────────────────────────────────
    # Gabungkan path + fragment (#...) + query (?...) sebagai "specificness measure".
    # Base URL "https://myssc.pertamina.com/" → path='/', fragment='', query='' → total=1
    # URL form "https://myssc.pertamina.com/dwp/app/#/.../75" → total >> 8
    path_total = (
        len(parsed.path.rstrip('/'))      # path tanpa trailing slash
        + len(parsed.fragment)            # bagian setelah #
        + len(parsed.query)               # bagian setelah ?
    )
    MIN_PATH_LENGTH = 8  # "/dwp/app" = 8 karakter → threshold aman
    if path_total < MIN_PATH_LENGTH:
        logger.debug("invalid_link_too_short", extra={
            "link"       : link[:120],
            "path_total" : path_total,
            "threshold"  : MIN_PATH_LENGTH,
        })
        return False

    return True





# ===== DELETED: detect_problem_category() =====
# This large if-else chain categorized queries into hardcoded categories
# New system uses pure vector/BM25 search filtered by doc_type parameter
# No category detection needed - routing handled by intent detection instead


# ===== DELETED: get_contact_info() and get_required_info() =====
# These static functions returned hardcoded contact info per category
# New system gets all info directly from database records via escalation_guide()


def detect_confirmation(text: str) -> Optional[bool]:
    text = text.lower().strip()
    if re.search(r'\b(tidak|belum|gagal|ga|gak|nggak|batal|belum kelar)\b', text): return False
    if re.search(r'\b(iya|ya|sudah|selesai|kelar|aman|oke|ok|sip|betul)\b', text): return True
    return None


# =====================================================
# LLM RESPONSE — System prompt lengkap dari versi lama
# =====================================================

# Disclaimer hardcoded (bukan instruksi ke LLM) → 100% muncul saat SOP tidak ada
DISCLAIMER = (
    "⚠️ *Masalah ini belum tercatat dalam panduan SOP resmi kami.*\n\n"
    "Namun, berikut beberapa langkah umum yang dapat Anda coba terlebih dahulu:\n\n"
)

_SOP_SYSTEM_PROMPT_TEMPLATE = """\
Anda adalah SITI, AI IT Support tingkat L1 di perusahaan. \
Anda sangat disiplin, profesional, dan kaku terhadap prosedur.

INSTRUKSI KETAT BAHASA
WAJIB 100%: Gunakan Bahasa Indonesia formal. DILARANG SEKALI Inggris kecuali istilah teknis (Cache, Login, Restart).

Jika user bertanya dalam English, TETAP jawab dalam Bahasa Indonesia.

=== KONTEKS SOP RESMI (WAJIB DIIKUTI 100%) ===
{context}
==============================================

INSTRUKSI KETAT:
1. KEPATUHAN SOP: Anda HANYA boleh memberikan langkah yang tertulis di KONTEKS SOP di atas. \
DILARANG mengarang, menambah, atau memodifikasi berdasarkan pengetahuan eksternal.
2. EKSEKUSI BERURUTAN: Berikan panduan TAHAP DEMI TAHAP (1, 2, 3...). \
JANGAN melompati atau merangkum beberapa langkah.
3. LARANGAN ESKALASI PREMATUR: JANGAN suruh user buat tiket ke IT Helpdesk \
KECUALI user sudah menyatakan SELURUH langkah teknis telah gagal.
4. ISOLASI TOPIK: Jika ada >1 KATEGORI SOP di konteks, pilih SATU yang paling cocok. \
Abaikan kategori lainnya.
5. KONSISTENSI TOPIK: Jika user bilang langkah gagal, tetap gunakan SOP dari KATEGORI \
yang sama. JANGAN comot langkah dari kategori lain.{failed_note}

FORMAT JAWABAN (ikuti persis):
**ANALISIS MASALAH:**
(Satu kalimat konfirmasi masalah)

**LANGKAH PENYELESAIAN:**
1. [Langkah dari SOP]
2. [Langkah dari SOP]
...

**HASIL YANG DIHARAPKAN:**
(Satu kalimat tentang hasil setelah langkah diikuti)\
"""

_SMALL_TALK_SYSTEM_PROMPT = """\
Anda adalah SITI, asisten IT Support internal perusahaan.

ATURAN MUTLAK:
1. Balas sapaan dengan singkat, ramah, dan tawarkan bantuan IT.
2. JIKA pertanyaan di luar topik IT: Gunakan kalimat ini persis \
(tanpa tambahan apapun):
   "Mohon maaf, saya adalah asisten IT Support. Saya tidak diprogram \
untuk menjawab pertanyaan di luar kendala teknis IT perusahaan. \
Apakah ada masalah jaringan/perangkat yang bisa saya bantu?"
3. JANGAN gunakan kata "Namun" atau "Tetapi".\
"""

_FALLBACK_SYSTEM_PROMPT = """\
Anda adalah teknisi IT Support. Jawab dengan empati.

INSTRUKSI KETAT BAHASA 
WAJIB 100%: Gunakan Bahasa Indonesia formal. DILARANG SEKALI Inggris.
Istilah teknis saja yang boleh (Cache, Login, Restart).

PENTING: Masalah ini TIDAK ADA di SOP resmi kami. 
Berikan saran umum yang terstruktur bertahap:

FORMAT:
**ANALISIS MASALAH:**
(Ringkas masalahnya)

**LANGKAH PENYELESAIAN:**
1. [Cek hal ini]
2. [Coba langkah ini]
3. [Jika masih bermasalah, lakukan ini]

Jangan langsung menyuruh hubungi IT sebelum user coba langkah-langkah di atas.
Tunjukkan empati dan ingatkan bahwa ada support team jika semua gagal.\
"""


def _build_sop_system_msg(context: str, failed_steps: List[str]) -> str:
    """Bangun system prompt SOP dengan failed_note jika ada."""
    if failed_steps:
        failed_list  = "\n".join(f"  - {s}" for s in failed_steps)
        failed_note  = (
            f"\n\nPERHATIAN — Langkah berikut sudah DICOBA user dan GAGAL:\n"
            f"{failed_list}\n"
            "JANGAN ulangi langkah di atas. Berikan langkah BERIKUTNYA dari SOP."
        )
    else:
        failed_note = ""
    return _SOP_SYSTEM_PROMPT_TEMPLATE.format(context=context, failed_note=failed_note)


def get_llm_response(
    question: str,
    history: List[Dict[str, str]],
    prompt_type: str,
    vector_store=None,
    embedding_service=None,
    rag_query: str = None,
    failed_steps: List[str] = None,
    session: Dict = None,
) -> str:
    """Generate jawaban LLM (non-streaming)."""
    t0 = time.time()
    failed_steps = failed_steps or []

    if prompt_type == "small_talk":
        answer = generate_llm(
            [{"role": "system", "content": _SMALL_TALK_SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": question}],
            config_name="small_talk",
        )
        logger.info("llm_response_ok", extra={
            "type": "small_talk", "elapsed_ms": int((time.time()-t0)*1000)
        })
        
        return answer

    # Ambil context (pakai cache jika session ada)
    if session is not None:
        context = get_context_for_session(
            rag_query or question, session, vector_store, embedding_service
        )
    else:
        context = get_relevant_context(rag_query or question, vector_store, embedding_service)

    if context:
        system_msg = _build_sop_system_msg(context, failed_steps)
        answer = generate_llm(
            [{"role": "system", "content": system_msg}]
            + history + [{"role": "user", "content": question}],
            config_name="sop_strict",
        )
        logger.info("llm_response_ok", extra={
            "type": "sop", "elapsed_ms": int((time.time()-t0)*1000),
            "ctx_len": len(context),
        })
        return answer
    else:
        # ======================================================================
        # FALLBACK ROUTING (CLEANED UP — FIX 1)
        #
        # Tidak ada SOP ditemukan di RAG untuk pertanyaan ini.
        # - Turn 0 (attempts == 0): Berikan troubleshooting umum via LLM + DISCLAIMER.
        #   User perlu diberi kesempatan mencoba dulu sebelum dieskalasi.
        # - Turn 1+ (attempts >= 1): User sudah mencoba tapi gagal → langsung
        #   arahkan ke form Incident via escalation_guide (tanpa hardcode kategori).
        #
        # detect_problem_category() dan get_ticket_process() DIHAPUS.
        # Tidak ada lagi if-else hardcode kategori di sini.
        # ======================================================================
        current_attempt = session.get("attempts", 0) if session else 0

        if current_attempt >= 1:
            # User sudah mencoba sebelumnya → eskalasikan ke service/repair form via DB
            incident_guide = escalation_guide(
                question, vector_store, embedding_service, doc_type="ORDER_LINK"
            )
            logger.info("fallback_routing_escalation", extra={
                "attempt"   : current_attempt,
                "elapsed_ms": int((time.time()-t0)*1000),
            })
            return (
                "Langkah-langkah sebelumnya tampaknya belum berhasil menyelesaikan masalah Anda. "
                "Berikut panduan untuk membuat tiket resmi ke tim IT:\n\n"
                f"{incident_guide}"
            )

        # Turn pertama, tidak ada SOP → LLM fallback dengan DISCLAIMER
        llm_answer = generate_llm(
            [{"role": "system", "content": _FALLBACK_SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": question}],
            config_name="fallback_general",
        )
        logger.info("llm_response_ok", extra={
            "type"      : "fallback",
            "elapsed_ms": int((time.time()-t0)*1000),
            "attempt"   : current_attempt,
        })
        return DISCLAIMER + llm_answer


def get_llm_response_stream(
    question: str,
    history: List[Dict[str, str]],
    prompt_type: str,
    vector_store=None,
    embedding_service=None,
    rag_query: str = None,
    failed_steps: List[str] = None,
    session: Dict = None,
) -> Generator[str, None, None]:
    """Versi streaming dari get_llm_response."""
    failed_steps = failed_steps or []

    if prompt_type == "small_talk":
        yield from generate_llm_stream(
            [{"role": "system", "content": _SMALL_TALK_SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": question}],
            config_name="small_talk",
        )
        return

    if session is not None:
        context = get_context_for_session(
            rag_query or question, session, vector_store, embedding_service
        )
    else:
        context = get_relevant_context(rag_query or question, vector_store, embedding_service)

    if context:
        system_msg = _build_sop_system_msg(context, failed_steps)
        yield from generate_llm_stream(
            [{"role": "system", "content": system_msg}]
            + history + [{"role": "user", "content": question}],
            config_name="sop_strict",
        )
    else:
        # Streaming fallback — mirror logika sync (FIX 1)
        current_attempt = session.get("attempts", 0) if session else 0

        if current_attempt >= 1:
            # User sudah mencoba → eskalasi ke service/repair form
            incident_guide = escalation_guide(
                question, vector_store, embedding_service, doc_type="ORDER_LINK"
            )
            yield (
                "Langkah-langkah sebelumnya tampaknya belum berhasil menyelesaikan masalah Anda. "
                "Berikut panduan untuk membuat tiket resmi ke tim IT:\n\n"
                f"{incident_guide}"
            )
        else:
            yield DISCLAIMER
            yield from generate_llm_stream(
                [{"role": "system", "content": _FALLBACK_SYSTEM_PROMPT}]
                + history + [{"role": "user", "content": question}],
                config_name="fallback_general",
            )


# =====================================================
# FAILURE SIGNAL DETECTION
# =====================================================

_FAILURE_SIGNALS = re.compile(
    r'\b(masih|belum|tidak berhasil|gagal|tidak bisa|sama saja|tidak mempan|'  
    r'tetap|tidak reset|tidak membantu|masih error|langkah tidak berhasil)\b',
    re.IGNORECASE,
)


def _track_failed_steps(question: str, session: Dict) -> None:
    """
    Track langkah-langkah yang sudah dicoba user tapi GAGAL.
    
    Mekanisme:
    1. Deteksi kata-kata failure: "masih tidak bisa", "gagal", "belum berhasil", dll
    2. Jika terdeteksi, ambil ringkasan jawaban bot sebelumnya yang berisi instruksi
    3. Simpan ke session["failed_steps"] sebagai catatan
    4. LLM SOP akan MENGHINDARI mengulangi langkah yang sama
    
    Contoh:
      Turn 1: Bot → "Langkah 1: Cek DNS di Settings > Network..."
               session["failed_steps"] = ["Cek DNS di Settings > Network..."]
      Turn 2: User → "masih tidak bisa"
               LLM akan: SKIP langkah DNS → maret ke Langkah 2 berdasarkan SOP
    
    Update versi ini:
    - Lebih panjang ringkasan (hingga 150 karakter) untuk konteks lebih jelas
    - Extrak HANYA bullet points/numbered steps dari jawaban bot, skip disclaimer
    - Deduplicate: jangan track langkah yang sama 2x
    - Log setiap step yang di-track untuk debugging
    """
    if _FAILURE_SIGNALS.search(question) and session["history"]:
        last_bot_msgs = [m["content"] for m in session["history"] if m["role"] == "assistant"]
        if last_bot_msgs:
            bot_answer = last_bot_msgs[-1]
            
            # Extract langkah-langkah dari jawaban bot (cari pola "1. ", "2. ", "- ", dll)
            # Bukan hanya substring pertama, tapi instruksi yang meaningful
            step_pattern = re.compile(r'^\s*(?:\d+\.|[-*]|►)\s*(.+?)$', re.MULTILINE)
            steps = step_pattern.findall(bot_answer)
            
            if steps:
                # Ambil beberapa langkah pertama yang paling relevan (max 2-3 langkah)
                for step in steps[:3]:
                    step_summary = step.strip()[:100].rstrip('.')
                    # Deduplicate: jangan track langkah duplikat
                    if step_summary and step_summary not in session["failed_steps"]:
                        session["failed_steps"].append(step_summary)
                        logger.info("failed_step_tracked", extra={
                            "step": step_summary[:80],
                            "total_failed_steps": len(session["failed_steps"])
                        })
            else:
                # Fallback: ambil ringkasan dari seluruh jawaban bot (150 karakter)
                # Tapi skip disclaimer dan formatting noise
                summary = bot_answer.replace("⚠️", "").replace("**", "")[:150].strip()
                if summary and summary not in session["failed_steps"]:
                    session["failed_steps"].append(summary)
                    logger.info("failed_step_tracked_fallback", extra={
                        "step": summary[:80],
                        "total_failed_steps": len(session["failed_steps"])
                    })


def _update_history(session: Dict, question: str, answer: str) -> None:
    """Simpan percakapan, batasi 6 pesan terakhir (3 turn)."""
    session["history"].append({"role": "user",      "content": question})
    session["history"].append({"role": "assistant", "content": answer})
    if len(session["history"]) > 6:
        session["history"] = session["history"][-6:]


# =====================================================
# ESCALATION PROMPT
# =====================================================

# =====================================================
# CONTEXTUAL MESSAGES
# =====================================================

# Pesan konfirmasi yang muncul di turn ke-2
_SOLVED_CONFIRMATION_PROMPT = (
    "\n\n---\n"
    "**Apakah masalah Anda sudah terselesaikan?** (Sudah / Belum)"
)

# Respon jika masalah selesai
_HAPPY_TO_HELP_REPLY = (
    "Alhamdulillah, saya senang bisa membantu! 😊 Jika ada kendala IT lainnya di kemudian hari, "
    "jangan ragu untuk menyapa saya kembali. Selamat beraktivitas!"
)

# NOTE: _INCIDENT_ESCALATION_REPLY DELETED
# Reason: Now using escalation_guide(doc_type="INCIDENT_LINK") for dynamic responses
# This ensures all incident handling uses real database links instead of hardcoded URLs

# Respon penolakan non-IT (dari versi sebelumnya)
_OUT_OF_SCOPE_REPLY = (
    "Maaf, saya hanya dapat membantu dengan pertanyaan seputar IT seperti "
    "masalah wifi, printer, laptop, email, VPN, atau software perusahaan. 😊\n\n"
    "Apakah ada masalah IT yang bisa saya bantu?"
)



# =====================================================
# IT SUPPORT TEAM ROUTING
# =====================================================
# NOTE: ROUTING_TEMPLATE_WITH_GUIDE dan ROUTING_TEMPLATE_NO_GUIDE dihapus.
# Keduanya hanya dipakai oleh detect_problem_category/get_ticket_process
# yang sudah dihapus (dead code). Routing sekarang sepenuhnya via escalation_guide().
# =====================================================



# =====================================================
# MAIN CHAT — PUBLIC API
# =====================================================

def chat(
    question: str,
    vector_store,
    embedding_service,
    session_id: str = "default",
) -> str:
    """Entry point utama. Return string lengkap."""
    question = question.strip()
    if not question:
        return "Ada yang bisa saya bantu?"

    t0      = time.time()
    session = session_manager.get(session_id)
    answer  = _process_chat_sync(question, session, vector_store, embedding_service, session_id)

    logger.info("chat_request", extra={
        "session_id"     : session_id,
        "question_length": len(question),
        "elapsed_ms"     : int((time.time() - t0) * 1000),
    })
    return answer


def chat_stream(
    question: str,
    vector_store,
    embedding_service,
    session_id: str = "default",
) -> Generator[str, None, None]:
    """Entry point streaming. Yield token per token."""
    question = question.strip()
    if not question:
        yield "Ada yang bisa saya bantu?"
        return

    session = session_manager.get(session_id)
    yield from _process_chat_stream(question, session, vector_store, embedding_service, session_id)


# =====================================================
# CORE LOGIC — Sync & Stream (pisah agar tidak campur yield+return)
# =====================================================

def _handle_escalation_confirmation(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    session_id: str,
) -> Optional[str]:
    """
    Proses konfirmasi penyelesaian masalah.
    - True  (Sudah): Tampilkan pesan sukses & reset state.
    - False (Belum): Call escalation_guide() dengan doc_type="INCIDENT_LINK" untuk dynamic response.
    - None  (Ambigu): Kembalikan None agar logic utama memproses sebagai masalah baru.

    PERUBAHAN BESAR: Sekarang menggunakan escalation_guide(doc_type="INCIDENT_LINK")
    untuk mendapatkan form dan link dari database, bukan hardcoded string.
    """
    confirmation = detect_confirmation(question)

    if confirmation is True:  # User menjawab "Sudah/Iya/Selesai"
        session["awaiting_support_confirmation"] = False
        session["offered_support"] = False
        session["attempts"] = 0
        session["cached_context"] = None
        answer = _HAPPY_TO_HELP_REPLY
        _update_history(session, question, answer)
        session_manager.save(session_id, session)
        return answer

    elif confirmation is False:  # User menjawab "Belum/Tidak/Gagal"
        session["awaiting_support_confirmation"] = False
        # Use dynamic escalation_guide with ORDER_LINK
        # This retrieves actual form and link from the database for service/repair requests
        preamble = "Mohon maaf langkah-langkah di atas belum berhasil membantu.\n\n"
        incident_guide = escalation_guide(
            session.get("last_it_problem") or question, 
            vector_store, 
            embedding_service, 
            doc_type="ORDER_LINK"
        )
        answer = preamble + incident_guide
        _update_history(session, question, answer)
        session_manager.save(session_id, session)
        return answer

    else:
        # Jika user tidak menjawab "Sudah/Belum" tapi malah bertanya hal lain
        session["awaiting_support_confirmation"] = False
        session["offered_support"] = False
        # Kita kembalikan None agar logic utama memproses 'question' sebagai masalah baru
        return None

def _process_chat_sync(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    session_id: str,
) -> str:
    # 1. Handle jika sedang dalam mode menunggu konfirmasi "Sudah/Belum"
    if session.get("awaiting_support_confirmation"):
        result = _handle_escalation_confirmation(
            question, session, vector_store, embedding_service, session_id
        )
        if result is not None:
            return result

    # 2. Intent Detection
    intent = detect_intent(question, embedding_service)

    # 3. Routing Berdasarkan Intent
    if intent == "GENERAL_CHAT":
        answer = get_llm_response(question, session["history"], "small_talk")
    elif intent == "OUT_OF_SCOPE":
        answer = _OUT_OF_SCOPE_REPLY
    elif intent == "REQUEST_IT_SUPPORT":
        # NEW TOPIC: Clear stale state from previous IT_PROBLEM turns
        session["last_it_problem"] = ""
        session["attempts"] = 0
        session["offered_support"] = False
        # Use current question, NOT stale last_it_problem from previous turn
        guide = escalation_guide(question, vector_store, embedding_service, doc_type="ORDER_LINK")
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
    elif intent == "SERVICE_ORDER":
        # NEW TOPIC: Clear stale state from previous IT_PROBLEM turns
        session["last_it_problem"] = ""
        session["attempts"] = 0
        session["offered_support"] = False
        # SERVICE_ORDER: skip alur RAG troubleshoot, langsung cari form pengadaan yang relevan
        # via escalation_guide dengan doc_type="ORDER_LINK".
        # Pass raw query directly to preserve critical context. Vector/BM25 search handles
        # full context better than over-simplified refinements (e.g., "request kirim broadcast email
        # dan pasang video display di videotron" should not be reduced to "pemasangan email").
        logger.info("intent_service_order", extra={"session_id": session_id, "question": question[:80]})
        guide = escalation_guide(question, vector_store, embedding_service, doc_type="ORDER_LINK")
        answer = (
            "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
            "Berikut adalah link form yang perlu Anda isi:\n\n"
            f"{guide}"
        )
    else:  # IT_PROBLEM
        if session["attempts"] == 0:
            session["last_it_problem"] = question
        
        _track_failed_steps(question, session)
        
        rag_query = rewrite_query_for_rag(
            question, session["history"], 
            original_problem=session.get("last_it_problem", "")
        )

        answer = get_llm_response(
            question, session["history"], "troubleshoot",
            vector_store, embedding_service,
            rag_query=rag_query,
            failed_steps=session["failed_steps"],
            session=session,
        )
        
        session["attempts"] += 1

        # Turn ke-2: Tambahkan pertanyaan konfirmasi penyelesaian
        if session["attempts"] >= 2 and not session.get("offered_support"):
            session["offered_support"] = True
            session["awaiting_support_confirmation"] = True
            answer += _SOLVED_CONFIRMATION_PROMPT

    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer

def _process_chat_stream(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    session_id: str,
) -> Generator[str, None, None]:
    """
    STREAMING logic — Menangani semua intent agar tidak ada respons kosong.
    """
    # 1. Handle konfirmasi "Sudah/Belum" jika sedang aktif
    if session.get("awaiting_support_confirmation"):
        result = _handle_escalation_confirmation(
            question, session, vector_store, embedding_service, session_id
        )
        if result is not None:
            yield result
            return

    # 2. Deteksi intent
    intent = detect_intent(question, embedding_service)
    logger.info("intent_resolved_stream", extra={"session_id": session_id, "intent": intent})

    # Variable untuk menyimpan jawaban lengkap guna update history di akhir
    answer = ""

    # 3. Routing Berdasarkan Intent
    if intent == "GENERAL_CHAT":
        full_answer_list = []
        for token in get_llm_response_stream(question, session["history"], "small_talk"):
            full_answer_list.append(token)
            yield token
        answer = "".join(full_answer_list)

    elif intent == "OUT_OF_SCOPE":
        answer = _OUT_OF_SCOPE_REPLY
        yield answer

    elif intent == "REQUEST_IT_SUPPORT":
        # NEW TOPIC: Clear stale state from previous IT_PROBLEM turns
        session["last_it_problem"] = ""
        session["attempts"] = 0
        session["offered_support"] = False
        # Use current question, NOT stale last_it_problem from previous turn
        guide = escalation_guide(question, vector_store, embedding_service, doc_type="ORDER_LINK")
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
        yield answer

    elif intent == "SERVICE_ORDER":
        # NEW TOPIC: Clear stale state from previous IT_PROBLEM turns
        session["last_it_problem"] = ""
        session["attempts"] = 0
        session["offered_support"] = False
        # SERVICE_ORDER: skip alur RAG troubleshoot, langsung cari form pengadaan yang relevan
        # via escalation_guide dengan doc_type="ORDER_LINK".
        # Pass raw query directly to preserve critical context. Vector/BM25 search handles
        # full context better than over-simplified refinements.
        logger.info("intent_service_order_stream", extra={"session_id": session_id, "question": question[:80]})
        guide = escalation_guide(question, vector_store, embedding_service, doc_type="ORDER_LINK")
        answer = (
            "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
            "Berikut adalah link form yang perlu Anda isi:\n\n"
            f"{guide}"
        )
        yield answer

    elif intent == "REJECT_IT_SUPPORT":
        session["offered_support"] = False
        answer = "Baik, saya akan tetap berusaha membantu Anda di sini. Silakan ceritakan masalahnya lebih lanjut."
        yield answer

    else:  # IT_PROBLEM
        # Turn pertama: simpan masalah utama untuk anchor RAG & Eskalasi
        if session["attempts"] == 0:
            session["last_it_problem"] = question
        
        # Track langkah gagal jika user bilang "masih tidak bisa" dsb.
        _track_failed_steps(question, session)
        
        # Tulis ulang query untuk RAG agar kontekstual
        rag_query = rewrite_query_for_rag(
            question, session["history"], 
            original_problem=session.get("last_it_problem", "")
        )

        full_answer_list = []
        # Panggil generator streaming dari LLM
        for token in get_llm_response_stream(
            question, session["history"], "troubleshoot",
            vector_store, embedding_service,
            rag_query=rag_query,
            failed_steps=session["failed_steps"],
            session=session,
        ):
            full_answer_list.append(token)
            yield token
        
        answer = "".join(full_answer_list)
        session["attempts"] += 1

        # Turn ke-2+: Tawarkan konfirmasi penyelesaian (Sudah/Belum)
        if session["attempts"] >= 2 and not session.get("offered_support"):
            session["offered_support"] = True
            session["awaiting_support_confirmation"] = True
            yield _SOLVED_CONFIRMATION_PROMPT
            answer += _SOLVED_CONFIRMATION_PROMPT

    # 4. Finalisasi: Update history dan simpan session
    if answer:
        _update_history(session, question, answer)
        session_manager.save(session_id, session)