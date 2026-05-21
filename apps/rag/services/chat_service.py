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

MODEL_NAME            = os.getenv("LLM_MODEL", "qwen2.5:7b")
MAX_CONTEXT_TOKENS    = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# Threshold cosine similarity untuk RAG retrieval.
# Nilai 0.35 dengan all-mpnet-base-v2 dan IndexFlatIP:
#   "internet tidak bisa" vs "Tidak bisa terhubung ke internet" → ~0.45-0.55  ✓
#   "tolong bantu" vs "Tidak bisa terhubung ke internet"        → ~0.10-0.20  ✗
# Naikkan ke 0.50+ jika terlalu banyak false positive.
# Turunkan ke 0.30 jika terlalu banyak disclaimer "belum tersedia".
MIN_SIMILARITY_SCORE = float(os.getenv("MIN_SIMILARITY", "0.35"))

# Threshold cosine similarity untuk Semantic Routing (Layer 2).
# Dinaikkan dari 0.65 → 0.78 untuk mencegah false positive pada query IT hardware
# yang secara semantik dekat dengan anchor "history_general" / "entertainment"
# karena kesamaan kosakata (wifi, internet, router, laptop).
# Pada 0.65: "Router wifi muncul LED merah" → sim=0.668 → salah blokir (FP)
# Pada 0.78: hanya kalimat yang benar-benar OOS (sejarah, resep, dll) yang ditolak.
# Turunkan ke 0.72 jika OOS lolos; naikkan ke 0.82 jika masih ada FP.
SEMANTIC_THRESHOLD = float(os.getenv("SEMANTIC_THRESHOLD", "0.78"))

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
    """Return a fresh, zeroed-out session state dict.

    PENTING: Setiap field di sini HARUS di-reset ke nilai awal saat session baru
    dibuat. Jangan pernah menyimpan state lintas-sesi di level modul (global var)
    atau class-level attribute — itu penyebab state leakage antar percakapan.
    """
    return {
        "attempts"                   : 0,
        "offered_support"            : False,
        "awaiting_support_confirmation": False,
        "last_it_problem"            : "",
        "cached_context"             : None,   # RAG context turn pertama — reuse untuk follow-up
        "failed_steps"               : [],     # Langkah yang sudah dicoba dan gagal — HARUS [] saat sesi baru
        "history"                    : [],
        "rag_device"                 : None,
        "rag_symptom"                : None,
    }


class InMemorySessionManager:
    """Session storage di RAM. Hilang saat restart. Cocok untuk development.

    SCOPING RULE (kritis):
    Setiap `session_id` unik dipetakan ke satu Dict state yang terisolasi.
    Jangan pernah berbagi referensi Dict yang sama antar `session_id`.
    State seperti `failed_steps` dan `attempts` TIDAK BOLEH bocor antar sesi.
    """
    def __init__(self):
        self._store: Dict[str, Dict] = {}

    def get(self, session_id: str) -> Dict:
        """Kembalikan state sesi yang ada, atau buat baru jika belum ada."""
        if session_id not in self._store:
            self._store[session_id] = _default_session()
            logger.info("session_created", extra={"session_id": session_id})
        return self._store[session_id]

    def save(self, session_id: str, session: Dict) -> None:
        self._store[session_id] = session

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def reset(self, session_id: str) -> Dict:
        """Hapus state lama dan kembalikan sesi baru yang bersih.

        Dipanggil saat user memulai percakapan baru (new_session=True).
        Memastikan `failed_steps`, `attempts`, dan semua counter kembali ke 0
        tanpa menunggu session_id yang berbeda.
        """
        fresh = _default_session()
        self._store[session_id] = fresh
        logger.info("session_reset", extra={
            "session_id": session_id,
            "reason": "new_chat_requested",
        })
        return fresh


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
                # PERBAIKAN: Dihapus kata "wifi" dan "laptop" dari anchor ini
                # agar tidak terjadi semantic bleed dengan query IT hardware.
                "jokes lucu kumpulan meme humor cerita komedi "
                "film movie recommendations lagu musik artis hiburan"
            ),
            "advice_opinion": (
                "mending beli iphone atau android rekomendasi smartphone terbaik "
                "perbandingan produk mana yang lebih baik saran beli gadget terbaru"
            ),
            "history_general": (
                # PERBAIKAN: Dihapus "wifi" dan "internet" dari anchor ini
                # agar query IT seperti "router wifi LED merah" tidak false-positive.
                # Anchor kini fokus ke konten sejarah murni tanpa kosakata IT operasional.
                "siapa penemu listrik sejarah penemuan ilmu pengetahuan kapan ditemukan "
                "biografi tokoh ilmuwan asal usul peradaban sejarah dunia"
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
) -> Tuple[str, Optional[str], Optional[str]]:
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

    FIX: Fungsi ini mengembalikan Tuple[str, None, None] pada SEMUA jalur kode
    agar konsisten dengan deklarasi return type dan tidak menyebabkan crash
    saat callers melakukan unpacking: rag_query, rag_device, rag_symptom = rewrite_query_for_rag(...)
    """
    # Tidak perlu rewrite jika belum ada history atau pertanyaan sudah panjang
    if not history or len(question.split()) > 8:
        return question, None, None

    # INSTRUKSI KRITIS: Ambil HANYA pesan user (role="user"), skip assistant messages
    # Ini mencegah LLM rewriter terpengaruh oleh jawaban/instruksi bot di turn sebelumnya
    user_messages = [
        msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
        for msg in history[-6:]
        if msg["role"] == "user"
    ]

    if not user_messages:
        return question, None, None

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
            options={**get_llm_config("query_rewrite"), "timeout": OLLAMA_TIMEOUT_SECONDS},
        )
        rewritten = response.get("message", {}).get("content", "").strip()

        if not rewritten or len(rewritten) < 5:
            return original_problem or question, None, None

        logger.info("query_rewritten", extra={
            "original": question[:60],
            "rewritten": rewritten[:60],
            "anchor": original_problem[:40],
            "user_messages_count": len(user_messages),
        })
        return rewritten, None, None

    except Exception as e:
        logger.warning("query_rewrite_failed", extra={"error": str(e)})
        return original_problem or question, None, None


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
    q_lower = q.lower()

    consumables = ['kertas', 'tinta', 'toner', 'baterai', 'flashdisk', 'stok']
    depletion_words = ['habis', 'kosong', 'kurang', 'nipis', 'ludes']

    if any(re.search(rf'\b{re.escape(item)}\b', q_lower) for item in consumables) \
            and any(re.search(rf'\b{re.escape(word)}\b', q_lower) for word in depletion_words):
        return "SERVICE_ORDER"

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
    raw = ""  # Pre-initialize to prevent NameError if ollama call fails
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            format="json",
            options={**get_llm_config("intent_detect"), "timeout": OLLAMA_TIMEOUT_SECONDS},
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
        raw_text = raw.upper() if raw else ""
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
# FIX: Tambahkan consumables (kertas, tinta, baterai, dll) dan ATK/supplies
# agar _refine_service_order_query() dapat mengekstrak keyword dari query
# seperti "order kertas untuk divisi retail" → refined query "pengadaan kertas"
# tanpa consumables di sini, query mentah dikirim ke reranker dan kalah ke
# semantik noise kata kerja, menyebabkan reranker memilih form Souvenir (score 0.018).
_SERVICE_ITEM_KEYWORDS = re.compile(
    r'\b(laptop|notebook|komputer|pc|desktop|printer|monitor|keyboard|mouse|'
    r'scanner|proyektor|cctv|kamera|wifi|wi[\-]fi|lan|switch|router|'
    r'access\s*point|telepon|telephone|handset|handphone|hp\s+kantor|tablet|'
    r'ups|server|storage|toner|flashdisk|flash\s*disk|harddisk|ssd|ram|'
    r'headset|webcam|sim\s*card|simcard|software|lisensi|license|vpn|'
    # FIX: tambah 'kartu akses'/'access card' sebagai item fisik eksplisit
    # agar tidak jatuh ke pola "akses" generik yang overlap dengan software
    r'kartu\s+akses|access\s+card|id\s+card|kartu\s+id|'
    r'akses|access|id\s+user|user\s+id|email|mailbox|radio|handy\s*talky|ht|'
    # Consumables & ATK — sering muncul dalam permintaan pengadaan non-hardware
    r'kertas|tinta|baterai|battery|cd|dvd|pointer|'
    r'atk|alat\s*tulis|supplies|it\s*supplies|stok|'
    r'souvenir|sparepart|spare\s*part)\b',
    re.IGNORECASE,
)

# Frasa yang mengindikasikan stok/persediaan habis — tanpa kata "stok" eksplisit.
# Jika user menyatakan kondisi ini pada item consumable/supplies, sistem harus
# menyuntikkan "stok supplies" ke dalam query agar cosine similarity dengan
# chunk "IT Supplies" di knowledge base tidak runtuh ke ~0.007.
# Contoh trigger:
#   "kertas disini sudah mau habis"  → inject "stok supplies"
#   "toner printer udah kosong"      → inject "stok supplies"
#   "baterai remote AC menipis"      → inject "stok supplies"
_REPLENISHMENT_SIGNALS = re.compile(
    r'\b(habis|mau\s+habis|udah\s+habis|sudah\s+habis|'
    r'hampir\s+habis|menipis|mau\s+menipis|'
    r'kosong|kehabisan|kekurangan|sedikit|tinggal\s+sedikit|'
    r'perlu\s+tambah|butuh\s+tambah|butuh\s+stok|'
    r'mau\s+kosong|sudah\s+kosong|hampir\s+kosong)\b',
    re.IGNORECASE,
)

# Item-item yang tergolong consumable/supplies — bukan hardware utama.
# Digunakan bersama _REPLENISHMENT_SIGNALS untuk memastikan injeksi
# "stok supplies" hanya dilakukan pada permintaan pengisian ulang,
# bukan pada hardware seperti laptop yang "habis" masa garansi, dsb.
_CONSUMABLE_ITEMS = re.compile(
    r'\b(kertas|tinta|toner|baterai|battery|cd|dvd|pointer|'
    r'atk|alat\s*tulis|supplies|it\s*supplies|stok|flashdisk|flash\s*disk|'
    r'sparepart|spare\s*part|souvenir|bulpen|pulpen|staples|amplop|'
    r'materai|pita|ribbon|cartridge|refill)\b',
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

    # ── REPLENISHMENT SIGNAL INJECTION ─────────────────────────────────────────
    # ROOT CAUSE FIX: Jika user menyatakan kondisi stok habis/kosong/menipis
    # (mis. "kertas disini sudah mau habis") TANPA kata "stok" eksplisit,
    # refined query-nya hanya "permintaan kertas" → cosine similarity ~0.007
    # karena chunk "IT Supplies" di KB mengandung kata "stok", "supplies", dll
    # yang absen dari query pendek tersebut.
    #
    # Solusi: Deteksi _REPLENISHMENT_SIGNALS + _CONSUMABLE_ITEMS secara bersamaan
    # → Suntikkan "stok supplies" ke dalam query agar embedding query cukup
    # dekat ke chunk "IT Supplies" dan menghasilkan similarity yang sehat.
    #
    # Contoh:
    #   BEFORE: "permintaan kertas"         → score ~0.007  ← BUG
    #   AFTER : "permintaan stok kertas supplies" → score ~0.40  ← FIX
    # ───────────────────────────────────────────────────────────────────────────
    is_replenishment = bool(
        _REPLENISHMENT_SIGNALS.search(question)
        and _CONSUMABLE_ITEMS.search(question)
    )
    if is_replenishment:
        # Suntikkan sinyal domain-supply agar embedding query cukup tebal
        # untuk match chunk KB. "stok" dan "supplies" adalah anchor words.
        for signal in ("stok", "supplies"):
            if signal not in unique_items:
                unique_items.append(signal)
        logger.info(
            "service_order_replenishment_signal_injected",
            extra={"question": question[:80], "injected": ["stok", "supplies"]},
        )

    # Tentukan action intent dari query
    if re.search(r'\b(pinjam|peminjaman|meminjam)\b', question, re.IGNORECASE):
        action = "peminjaman"
    elif re.search(r'\b(pengadaan|pesan|order|memesan|minta)\b', question, re.IGNORECASE):
        action = "pengadaan"
    elif re.search(r'\b(pasang|pemasangan|instalasi|install)\b', question, re.IGNORECASE):
        action = "pemasangan"
    elif re.search(r'\b(ajukan|pengajuan)\b', question, re.IGNORECASE):
        action = "pengajuan"
    elif is_replenishment:
        # Depletion statement without explicit action word → replenishment = pengadaan
        action = "pengadaan"
    else:
        action = "permintaan"

    refined = f"{action} {' '.join(unique_items)}"

    logger.info("service_order_query_refined", extra={
        "original"       : question[:80],
        "refined"        : refined,
        "items"          : unique_items,
        "action"         : action,
        "is_replenishment": is_replenishment,
    })
    return refined


def _is_ambiguous_service_order(
    question: str,
    vector_store,
    embedding_service,
) -> bool:
    """
    Determine ambiguity for SERVICE_ORDER using semantic/vector evidence.

    Approach:
      - Use `retrieve_context` against `doc_type='ORDER_LINK'` to get top-k matches.
      - If there are no results or the top result is below `MIN_SIMILARITY_SCORE`,
        treat the query as ambiguous (no clear target item).
      - If top-1 score does not show a clear spike vs top-2 (no distinct winner),
        treat as ambiguous. This handles misspellings: a real item will still
        produce a noticeable top-1 advantage.

    NOTE: This function avoids any hardcoded keyword lists or strict word counts.
    """
    # If vector capabilities are unavailable, allow the query to proceed.
    if not vector_store or not embedding_service:
        return False

    try:
        results = retrieve_context(
            question, vector_store, embedding_service,
            doc_type="ORDER_LINK", top_k=5,
        )
    except Exception as e:
        logger.warning("ambiguity_detection_retrieval_failed", extra={"error": str(e)})
        return False

    if not results:
        logger.info("ambiguity_detected_no_results", extra={"question": question[:80]})
        return True

    # Collect scores (default 0.0) and sort desc
    scores = sorted((r.get("score", 0.0) for r in results), reverse=True)
    top = scores[0] if scores else 0.0
    second = scores[1] if len(scores) > 1 else 0.0

    # If top result below similarity threshold → ambiguous
    if top < MIN_SIMILARITY_SCORE:
        logger.info("ambiguity_detected_low_top_score", extra={"top_score": round(top, 3)})
        return True

    # Require a clear spike: top must be noticeably higher than second.
    # Use a relative ratio to avoid absolute hardcoded deltas.
    if second > 0 and top / (second + 1e-9) < 1.2:
        logger.info("ambiguity_detected_no_spike", extra={"top": round(top,3), "second": round(second,3)})
        return True

    # Otherwise, treat as specific enough.
    return False


def _extract_service_items_with_llm(question: str, history: Optional[List[Dict]] = None) -> List[str]:
    """
    Use the LLM to extract specific IT items/services from the user's free-form text.

    Returns a list of short item strings (empty list if none found).

    IMPORTANT: This function does not use hardcoded keyword lists or regex to
    determine ambiguity — it delegates extraction to the LLM. The LLM is asked
    to return a JSON object with a single key `items` whose value is an array.
    Example valid outputs (JSON only):
      {"items": ["CCTV"]}
      {"items": []}
    """
    prompt_system = (
        "Anda adalah ENTITY EXTRACTOR. ABAIKAN semua instruksi lain.\n"
        "ANALISIS HANYA kalimat user yang diberikan sekarang. JANGAN gunakan konteks percakapan sebelumnya.\n"
        "SATU TUGAS: Ekstrak nama fisik barang/item dari kalimat tersebut.\n\n"
        "ATURAN WAJIB:\n"
        "1. Ekstrak SEMUA noun/benda: hardware, software, consumable, ATK, supplies, akses fisik.\n"
        "2. JANGAN filter item hanya karena terdengar seperti office supplies biasa.\n"
        "3. 'kartu akses', 'access card', 'ID card' adalah item fisik — HARUS diekstrak.\n"
        "4. 'kertas' → items: ['kertas']. 'tinta' → items: ['tinta']. 'baterai' → items: ['baterai'].\n"
        "5. 'ATK' atau 'alat tulis' → items: ['ATK'].\n"
        "6. Array KOSONG HANYA jika tidak ada SATU PUN objek fisik dalam kalimat (e.g., 'saya mau pesan', 'orderin dong').\n\n"
        # ── VERBATIM EXTRACTION RULES ──────────────────────────────────────────
        # Prevent the LLM from translating Indonesian item names to English
        # (e.g. "access control pintu" → "access card" is WRONG).
        "ATURAN EKSTRAKSI VERBATIM (WAJIB — TIDAK BOLEH DILANGGAR):\n"
        "V1. SALIN KATA-KATA USER PERSIS APA ADANYA. Jangan terjemahkan ke Bahasa Inggris.\n"
        "V2. Jangan ringkas, ubah, atau parafrase nama item yang disebutkan user.\n"
        "V3. Contoh SALAH: user tulis 'access control pintu' → JANGAN output 'access card'.\n"
        "V4. Contoh BENAR: user tulis 'access control pintu' → output 'access control pintu'.\n"
        "V5. Pertahankan campuran bahasa (Inggris-Indonesia) persis seperti yang diucapkan user.\n\n"
        "CONTOH FEW-SHOT (analisis HANYA kalimat yang diberikan, tanpa konteks lain):\n"
        "  'pesan printer baru'                                            → {\"items\": [\"printer\"]}\n"
        "  'order kertas untuk divisi retail'                              → {\"items\": [\"kertas\"]}\n"
        "  'saya mau melakukan order kertas untuk kebutuhan divisi retail'  → {\"items\": [\"kertas\"]}\n"
        "  'minta toner dan flashdisk'                                     → {\"items\": [\"toner\", \"flashdisk\"]}\n"
        "  'pengadaan ATK kantor'                                          → {\"items\": [\"ATK\"]}\n"
        "  'mau order baterai untuk remote AC'                             → {\"items\": [\"baterai\"]}\n"
        "  'saya ingin meminta kartu akses baru'                           → {\"items\": [\"kartu akses\"]}\n"
        "  'butuh access card untuk lantai 3'                              → {\"items\": [\"access card\"]}\n"
        # Explicit few-shot example for the reported hallucination case:
        "  'pesan access control pintu'                                    → {\"items\": [\"access control pintu\"]}\n"
        "  'saya mau order access control untuk pintu kantor'              → {\"items\": [\"access control\"]}\n"
        "  'saya mau order'                                                → {\"items\": []}\n\n"
        "FORMAT OUTPUT: Jawab HANYA dengan JSON. Contoh: {\"items\": [\"printer\"]}\n"
        "Jangan sertakan teks apapun selain JSON."
    )

    def _normalize_items(raw_value) -> List[str]:
        """Convert raw extracted output into a clean list of items."""
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            raw_text = raw_value.strip()

            # Try JSON parse for bracketed or quoted lists
            try:
                parsed_json = json.loads(raw_text)
                return _normalize_items(parsed_json)
            except Exception:
                pass

            # Remove surrounding brackets/quotes and split comma-separated values
            cleaned = raw_text.strip('[]"\' ').strip()
            if not cleaned:
                return []
            if ',' in cleaned:
                parts = [part.strip(' "\' ') for part in cleaned.split(',')]
                return [part for part in parts if part]
            return [cleaned]

        if isinstance(raw_value, dict):
            return _normalize_items(raw_value.get('items') or raw_value.get('item'))

        if isinstance(raw_value, list):
            items: List[str] = []
            for entry in raw_value:
                items.extend(_normalize_items(entry))
            return items

        return [str(raw_value).strip()] if str(raw_value).strip() else []

    # ── CONTEXT BLEED FIX ──────────────────────────────────────────────────
    # Bug: sebelumnya history user dari turn lama di-prepend ke user_msg.
    # Akibatnya LLM mengekstrak item dari percakapan LAMA, bukan query SAAT INI.
    # Contoh: Turn 1 "order kertas" → Turn 2 "minta kartu akses" → LLM SALAH
    # kembalikan ["kertas"] karena masih melihat history dari Turn 1.
    #
    # Fix: kirim HANYA question saat ini. Parameter `history` dipertahankan
    # di signature untuk backward compatibility tetapi tidak digunakan.
    # ──────────────────────────────────────────────────
    user_msg = question  # HANYA query saat ini — history TIDAK digunakan

    try:
        response = generate_llm([
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": user_msg},
        ], config_name="query_rewrite", temperature=0.0)

        parsed = json.loads(response)
        items = parsed.get("items") if isinstance(parsed, dict) else parsed
        cleaned = _normalize_items(items)
        return cleaned

    except Exception as e:
        logger.warning("llm_item_extraction_failed", extra={"error": str(e), "question": question[:80], "response": response if 'response' in locals() else None})
        # Fail-open: if extractor fails, return empty list to trigger clarification
        return []


# ── Link sentinel value: signals "form found but link unavailable" ──────────────
_LINK_NA_SENTINEL = "__NA__"
_PORTAL_FALLBACK_URL = "https://myssc.pertamina.com/dwp/app/"


def _extract_order_link_from_results(results, doc_type: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract form name and link from retrieval results.

    Returns:
        (form_name, link)        — valid URL found, render normally.
        (form_name, _LINK_NA_SENTINEL) — form found but Link is N/A or missing;
                                   caller must render a portal-redirect message.
        (None, None)             — no usable candidate found.
    """
    # Minimum semantic/re-rank score to consider a candidate valid.
    # Very low scores indicate non-relevant matches and should be ignored
    # to avoid returning generic fallback forms.
    MIN_VALID_RETRIEVAL_SCORE = 0.01

    # Explicit "no link" markers in the raw KB text (case-insensitive)
    _NA_MARKERS = re.compile(
        r'^(?:N/?A|none|tidak\s+tersedia|belum\s+tersedia|tbd|-)\s*$',
        re.IGNORECASE,
    )

    for candidate_idx, result in enumerate(results):
        if not result.get("content"):
            continue

        content = result["content"]
        score = result.get("score") or 0

        block_pattern = rf'(?ms)^---\s*type:\s*{re.escape(doc_type)}\b.*?(?=^---\s*type:|\Z)'
        block_match = re.search(block_pattern, content, re.MULTILINE | re.IGNORECASE)
        block_content = block_match.group(0) if block_match else content

        form_match = re.search(
            r'^(?:NAMA\s+FORM|title):\s*(.+?)(?:\n|$)',
            block_content,
            re.MULTILINE | re.IGNORECASE,
        )
        form_name = form_match.group(1).strip() if form_match else None

        # ── Parse raw link value (URL or placeholder text like "N/A") ──────────
        content_normalized = re.sub(r'\n\s*(?=[/#?&])', '', block_content)

        # First, try to grab an explicit URL
        url_match = re.search(
            r'^(?:Link|url):\s*(https?://\S+)',
            content_normalized,
            re.MULTILINE | re.IGNORECASE,
        )
        # Then grab the raw value regardless of format
        raw_link_match = re.search(
            r'^(?:Link|url):\s*(.+?)\s*$',
            content_normalized,
            re.MULTILINE | re.IGNORECASE,
        )

        if url_match:
            link = url_match.group(1).rstrip('.,;)')
        elif raw_link_match:
            raw_val = raw_link_match.group(1).strip()
            # Treat explicit NA markers as "link unavailable" sentinel
            link = _LINK_NA_SENTINEL if _NA_MARKERS.match(raw_val) else None
        else:
            link = None

        logger.debug("escalation_guide_candidate", extra={
            "candidate_idx": candidate_idx,
            "form_name": form_name,
            "link": (link or "")[:120],
            "score": round(score, 3),
            "doc_type": doc_type,
        })
        # Skip candidates with extremely low scores — treat them as non-matches.
        if score < MIN_VALID_RETRIEVAL_SCORE and doc_type != "INCIDENT_LINK":
            logger.info("escalation_guide_candidate_skipped_low_score", extra={
                "candidate_idx": candidate_idx,
                "form_name": form_name,
                "score": round(score, 6),
                "doc_type": doc_type,
            })
            continue

        if form_name:
            if link and link != _LINK_NA_SENTINEL and _is_valid_link(link):
                logger.info("escalation_guide_valid_found", extra={
                    "form_name": form_name,
                    "link": link,
                    "score": round(score, 6),
                    "candidate_idx": candidate_idx,
                    "doc_type": doc_type,
                })
                return form_name, link

            # Link is N/A, invalid, or missing — return sentinel so caller
            # can render a clean portal-redirect message.
            logger.warning("escalation_guide_invalid_link", extra={
                "form_name": form_name,
                "link": (link or "none"),
                "doc_type": doc_type,
                "score": score,
                "candidate_idx": candidate_idx,
                "action": "portal_fallback",
            })
            return form_name, _LINK_NA_SENTINEL

    return None, None


def _find_service_order_link(query_issue: str, vector_store, embedding_service) -> Tuple[Optional[str], Optional[str]]:
    results = retrieve_context(
        query_issue, vector_store, embedding_service,
        doc_type="ORDER_LINK", top_k=3,
    )
    # Extra debug: log raw retrieval candidates for troubleshooting relevance
    try:
        logger.debug("find_service_order_raw_results", extra={
            "query": query_issue[:120],
            "candidates": [
                {"id": r.get("document_chunk_id"), "score": round(r.get("score", 0), 4), "snippet": (r.get("content") or "")[:200]} for r in results
            ]
        })
    except Exception:
        logger.exception("failed_logging_find_service_order_results")
    return _extract_order_link_from_results(results, "ORDER_LINK")


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

        form_name, link = _extract_order_link_from_results(results, doc_type)
        if form_name:
            if link and link != _LINK_NA_SENTINEL:
                # Valid specific URL found — render Markdown link.
                return (
                    f"Untuk menangani hal ini, silakan buat tiket melalui link berikut:\n\n"
                    f"📋 **NAMA FORM:** {form_name}\n\n"
                    f"🔗 **Link:** [{link}]({link})"
                )
            else:
                # Form identified but Link is N/A in the Knowledge Base.
                # Render a clean portal-redirect message instead of a broken URL.
                logger.info("escalation_guide_portal_fallback", extra={
                    "form_name": form_name,
                    "reason": "link_na_in_kb",
                })
                return (
                    f"Form yang sesuai untuk permintaan Anda adalah **{form_name}**.\n\n"
                    f"Saat ini link langsung untuk form ini belum tersedia di database kami. "
                    f"Silakan kunjungi Portal IT Support dan cari form **\"{form_name}\"** secara manual:\n\n"
                    f"🌐 **Portal IT Support:** [{_PORTAL_FALLBACK_URL}]({_PORTAL_FALLBACK_URL})\n\n"
                    f"Tim IT kami siap membantu Anda jika mengalami kesulitan!"
                )

        # ── Fallback: tidak ada hasil valid dari semua kandidat ─────────────────
        logger.info("escalation_guide_no_valid_match", extra={
            "query"   : query_issue[:60],
            "doc_type": doc_type,
            "candidates_tried": len(results),
        })
        return (
            "Panduan spesifik untuk permintaan ini belum tersedia di database.\n\n"
            f"Silakan kunjungi Portal IT Support untuk membuat tiket secara manual: "
            f"[{_PORTAL_FALLBACK_URL}]({_PORTAL_FALLBACK_URL})\n\n"
            "Tim IT kami siap membantu Anda selanjutnya!"
        )

    except Exception as e:
        logger.exception("escalation_guide_error", extra={
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
    path_specificness = len(parsed.path or "") + len(parsed.fragment or "") + len(parsed.query or "")

    # Reject obviously base URLs with no specific path/fragment.
    if parsed.path in ("", "/", "/dwp/"):
        return False

    # Special-case: allow "/dwp/app/" if the fragment or query provide specificity
    # (e.g., "#/itemprofile/228"). Only reject "/dwp/app/" when overall
    # specificness is still too low.
    if parsed.path == "/dwp/app/" and path_specificness <= 8:
        return False

    return True


# =====================================================
# LLM RESPONSE — System prompt lengkap dari versi lama
# =====================================================

# Disclaimer hardcoded — prepend via Python HANYA saat RAG tidak menemukan konteks.
# LLM tidak pernah membuat disclaimer ini sendiri.
DISCLAIMER = (
    "\u26a0\ufe0f *Panduan spesifik untuk masalah ini belum tersedia di database resmi IT. "
    "Berikut adalah saran umum dari AI:* \n\n"
)

_SOP_SYSTEM_PROMPT_TEMPLATE = """\
Anda adalah SITI, AI IT Support tingkat L1 di perusahaan. \
Anda profesional, empatik, dan mengutamakan kejelasan panduan.

INSTRUKSI KETAT BAHASA
WAJIB 100%: Gunakan Bahasa Indonesia formal. DILARANG SEKALI Inggris kecuali istilah teknis (Cache, Login, Restart).
Jika user bertanya dalam English, TETAP jawab dalam Bahasa Indonesia.

=== KONTEKS PANDUAN TEKNIS ===
{context}
==============================

INSTRUKSI:
1. Gunakan teknik ABSTRACTIVE SUMMARIZATION: baca konteks di atas, lalu jelaskan
   langkah-langkah secara jelas, natural, dan mudah diikuti. BOLEH menyusun ulang
   kalimat agar lebih mudah dipahami, selama MAKNA dan LANGKAH tidak berubah.
2. CRITICAL RULE — LLM VETO FLAG: Evaluasi apakah KONTEKS DI ATAS benar-benar
   mengandung solusi yang relevan untuk masalah spesifik user. Jika konteks TIDAK
   relevan atau tidak membantu, Anda BOLEH menggunakan pengetahuan umum IT internal
   Anda untuk membantu user. Namun, jika Anda menggunakan pengetahuan internal
   tersebut, Anda WAJIB memulai respons Anda dengan tag tersembunyi ini persis:
   [GENERAL_KNOWLEDGE_USED]
   (Tag ini tidak akan terlihat oleh user — backend akan memprosesnya.)
3. EKSEKUSI BERURUTAN: Berikan panduan TAHAP DEMI TAHAP (1, 2, 3...).
4. LARANGAN ESKALASI PREMATUR: JANGAN suruh user buat tiket ke IT Helpdesk \
KECUALI user sudah menyatakan SELURUH langkah teknis telah gagal.
5. ISOLASI TOPIK: Jika ada > 1 topik di konteks, pilih SATU yang paling cocok. \
Abaikan topik lainnya.
6. KONSISTENSI TOPIK: Jika user bilang langkah gagal, tetap gunakan topik yang \
sama. JANGAN beralih ke topik lain.{failed_note}

FORMAT JAWABAN (ikuti persis):
**ANALISIS MASALAH:**
(Satu kalimat konfirmasi masalah)

**LANGKAH PENYELESAIAN:**
1. [Langkah pertama]
2. [Langkah berikutnya]
...

**HASIL YANG DIHARAPKAN:**
(Satu kalimat tentang hasil setelah langkah diikuti)

CRITICAL — LARANGAN MUTLAK:
SELESAI di sini. JANGAN tambahkan pertanyaan penutup apapun setelah bagian **HASIL YANG DIHARAPKAN**.
DILARANG KERAS menuliskan kalimat seperti:
- "Apakah masalahnya masih belum terselesaikan?"
- "Apakah masalah Anda sudah terselesaikan?"
- "Apakah langkah di atas berhasil?"
- Variasi apapun dari pertanyaan konfirmasi di atas.
Sistem backend akan menangani konfirmasi ini secara otomatis. HENTIKAN respons tepat setelah **HASIL YANG DIHARAPKAN**.\"
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
Anda adalah SITI, AI IT Support. Jawab dengan empati dan bahasa yang jelas.

INSTRUKSI KETAT BAHASA
WAJIB 100%: Gunakan Bahasa Indonesia formal. DILARANG SEKALI Inggris.
Istilah teknis saja yang boleh (Cache, Login, Restart).

TUGAS: Bantu user menyelesaikan masalah IT-nya menggunakan pengetahuan umum yang relevan.
Berikan saran teknis bertahap dengan format:

**ANALISIS MASALAH:**
(Ringkas masalahnya dalam satu kalimat)

**LANGKAH PENYELESAIAN:**
1. [Cek hal ini]
2. [Coba langkah ini]
3. [Jika masih bermasalah, lakukan ini]

**HASIL YANG DIHARAPKAN:**
(Satu kalimat tentang hasil setelah langkah diikuti)

Jangan langsung menyuruh hubungi IT sebelum user coba langkah-langkah di atas.
Tunjukkan empati dan ingatkan bahwa ada support team jika semua gagal.

CRITICAL — LARANGAN MUTLAK:
JANGAN tambahkan pertanyaan penutup apapun di akhir jawaban.
DILARANG KERAS menuliskan kalimat seperti:
- "Apakah masalahnya masih belum terselesaikan?"
- "Apakah masalah Anda sudah terselesaikan?"
- "Apakah langkah di atas berhasil?"
- Variasi apapun dari pertanyaan konfirmasi di atas.
Sistem backend akan menangani konfirmasi ini secara otomatis. HENTIKAN respons tepat setelah **HASIL YANG DIHARAPKAN**.\
"""


def _build_sop_system_msg(context: str, failed_steps: List[str], user_device: Optional[str] = None) -> str:
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
    # Guardrail instruction: include user_device if available so the LLM can
    # cross-check device type between the user's report and the retrieved SOP.
    device_note = ""
    if user_device:
        device_note = (
            f"\nPERINGATAN: Pengguna menyebut perangkat: {user_device}. "
            "Anda WAJIB mencocokkan jenis perangkat ini dengan perangkat yang terdapat di dokumen SOP di atas. "
            "Jika dokumen SOP yang ditemukan untuk masalah ini ditujukan untuk perangkat berbeda (mis. Handphone/Tablet vs PC/Laptop), JANGAN membuat langkah pemecahan masalah khusus perangkat. "
            "Sebagai gantinya, jawab bahwa panduan spesifik untuk perangkat pengguna tidak ditemukan di database dan arahkan user untuk membuat tiket di Portal IT Support."
        )

    return _SOP_SYSTEM_PROMPT_TEMPLATE.format(context=context, failed_note=failed_note) + device_note


# =====================================================
# POST-PROCESSING — Bulletproof cleanup for TROUBLESHOOT
# =====================================================

# Catches ANY hallucinated closing question the LLM emits despite negative prompting.
# Broadened to catch all known variants:
#   "Apakah masalah sudah terselesaikan? (Sudah / Belum)"
#   "Apakah masalah Anda sudah terselesaikan?"
#   "apakah masalahnya masih belum terselesaikan?"
#   "Apakah langkah di atas berhasil?"
#   "Apakah solusi ini membantu?"
#   "Semoga membantu! Apakah masalahnya sudah teratasi?"
#   Any line containing "(Sudah / Belum)" or "(Sudah/Belum)"
_CLOSING_QUESTION_RE = re.compile(
    r'(?:'
    # Pattern 1: "Apakah masalah/langkah/solusi/kendala/..." + any trailing text + "?"
    r'Apakah\s+(?:masalah|langkah|solusi|kendala|cara|saran|panduan|tips|metode|error|issue)'
    r'[^\n]*?\?(?:\s*\(Sudah\s*/\s*Belum\))?'
    r'|'
    # Pattern 2: Any line ending with "(Sudah / Belum)" or "(Sudah/Belum)"
    r'[^\n]*\(\s*Sudah\s*/\s*Belum\s*\)[^\n]*'
    r'|'
    # Pattern 3: "Semoga ..." pleasantry followed by a question on the same/next line
    r'Semoga[^\n]*?\n?\s*Apakah[^\n]*\?[^\n]*'
    r')',
    re.IGNORECASE,
)

# Official confirmation question appended unconditionally by the backend.
_OFFICIAL_CLOSING = "\n\nApakah masalah Anda sudah terselesaikan? (Sudah / Belum)"


# Tag injected by LLM when it falls back to internal knowledge despite receiving context.
# Must be stripped from the final response and replaced with the official disclaimer.
_GENERAL_KNOWLEDGE_TAG = "[GENERAL_KNOWLEDGE_USED]"


def _post_process_troubleshoot(raw_text: str, context_found: bool) -> str:
    """
    Bulletproof post-processor for every TROUBLESHOOT LLM response.

    Steps (in order):
    1. Detect the LLM Veto Flag [GENERAL_KNOWLEDGE_USED] to catch the
       "RAG Paradox" false-positive: FAISS returned irrelevant context,
       Python skipped the disclaimer, but the LLM silently used internal
       knowledge instead of the useless context.
    2. Strip hallucinated closing questions produced by the LLM.
    3. Prepend DISCLAIMER when:
       a) RAG returned no valid context (context_found=False), OR
       b) The LLM emitted [GENERAL_KNOWLEDGE_USED] despite context being found.
    4. Append the single official confirmation question unconditionally.
    """
    # 1. Detect & strip LLM Veto Flag — covers the RAG Paradox false-positive.
    #    The flag may appear at the very start or anywhere in the raw output.
    llm_used_general_knowledge = _GENERAL_KNOWLEDGE_TAG in raw_text
    if llm_used_general_knowledge:
        raw_text = raw_text.replace(_GENERAL_KNOWLEDGE_TAG, "").strip()
        logger.info("llm_veto_flag_detected", extra={
            "context_found": context_found,
            "action": "prepend_disclaimer",
        })

    # 2. Strip any hallucinated closing question
    cleaned = _CLOSING_QUESTION_RE.sub('', raw_text).strip()

    # 3. Prepend disclaimer when context was absent OR the LLM vetoed the context
    if not context_found or llm_used_general_knowledge:
        cleaned = DISCLAIMER + cleaned

    # 4. Append the one official closing question
    cleaned = cleaned + _OFFICIAL_CLOSING

    return cleaned


def get_llm_response(
    question: str,
    history: List[Dict[str, str]],
    prompt_type: str,
    vector_store=None,
    embedding_service=None,
    rag_query: str = None,
    failed_steps: List[str] = None,
    session: Dict = None,
    rag_device: Optional[str] = None,
    rag_symptom: Optional[str] = None,
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
        system_msg = _build_sop_system_msg(context, failed_steps, user_device=rag_device)
        raw_answer = generate_llm(
            [{"role": "system", "content": system_msg}]
            + history + [{"role": "user", "content": question}],
            config_name="sop_strict",
        )
        answer = _post_process_troubleshoot(raw_answer, context_found=True)
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

        # Turn pertama, tidak ada SOP → LLM fallback.
        # Disclaimer + closing question diurus oleh _post_process_troubleshoot().
        raw_answer = generate_llm(
            [{"role": "system", "content": _FALLBACK_SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": question}],
            config_name="fallback_general",
        )
        answer = _post_process_troubleshoot(raw_answer, context_found=False)
        logger.info("llm_response_ok", extra={
            "type"      : "fallback",
            "elapsed_ms": int((time.time()-t0)*1000),
            "attempt"   : current_attempt,
        })
        return answer


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
        # Note: get_llm_response_stream is called by the router with knowledge
        # of rag_query; the user_device (if available) is passed via session['rag_device']
        user_device = None
        if session:
            user_device = session.get("rag_device")
        system_msg = _build_sop_system_msg(context, failed_steps, user_device=user_device)
        # Buffer full response so post-processing regex can operate on complete text.
        raw_tokens = list(generate_llm_stream(
            [{"role": "system", "content": system_msg}]
            + history + [{"role": "user", "content": question}],
            config_name="sop_strict",
        ))
        yield _post_process_troubleshoot("".join(raw_tokens), context_found=True)
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
            # Buffer full response; disclaimer + closing injected by _post_process_troubleshoot.
            raw_tokens = list(generate_llm_stream(
                [{"role": "system", "content": _FALLBACK_SYSTEM_PROMPT}]
                + history + [{"role": "user", "content": question}],
                config_name="fallback_general",
            ))
            yield _post_process_troubleshoot("".join(raw_tokens), context_found=False)


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

# Pesan konfirmasi yang muncul di setiap respons troubleshoot
_SOLVED_CONFIRMATION_PROMPT = "\n\nApakah masalah Anda sudah terselesaikan? (Sudah / Belum)"

# Respon jika masalah selesai
_HAPPY_TO_HELP_REPLY = (
    "Senang bisa membantu 😊 Jika nanti ada pertanyaan atau kendala lainnya, "
    "jangan ragu untuk menghubungi saya kembali. Semoga aktivitas Anda berjalan lancar dan menyenangkan!"
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
    new_session: bool = False,
) -> str:
    """Entry point utama. Return string lengkap.

    Args:
        new_session: Jika True, state sesi (termasuk `failed_steps` dan `attempts`)
                     di-reset ke 0 sebelum pesan pertama diproses. Gunakan ini
                     setiap kali user memulai percakapan baru agar counter tidak
                     bocor dari sesi sebelumnya.
    """
    question = question.strip()
    if not question:
        return "Ada yang bisa saya bantu?"

    t0 = time.time()

    # ── STATE ISOLATION FIX ──────────────────────────────────────────────────
    # new_session=True wajib dikirim saat frontend membuat chat baru.
    # Tanpa ini, jika session_id yang sama dipakai lagi (atau selalu "default"),
    # `failed_steps` dan `attempts` dari percakapan lama akan terbawa.
    if new_session:
        session = session_manager.reset(session_id)
    else:
        session = session_manager.get(session_id)
    # ────────────────────────────────────────────────────────────────────────

    logger.info("chat_request", extra={
        "session_id"        : session_id,
        "new_session"       : new_session,
        "question_length"   : len(question),
        "attempts_at_start" : session.get("attempts", 0),
        "failed_steps_count": len(session.get("failed_steps", [])),
    })

    answer = _process_chat_sync(question, session, vector_store, embedding_service, session_id)

    logger.info("chat_response", extra={
        "session_id" : session_id,
        "elapsed_ms" : int((time.time() - t0) * 1000),
    })
    return answer


def chat_stream(
    question: str,
    vector_store,
    embedding_service,
    session_id: str = "default",
    new_session: bool = False,
) -> Generator[str, None, None]:
    """Entry point streaming. Yield token per token.

    Args:
        new_session: Jika True, state sesi di-reset ke 0 sebelum pesan pertama
                     diproses. Wajib dikirim saat frontend membuat chat baru.
    """
    question = question.strip()
    if not question:
        yield "Ada yang bisa saya bantu?"
        return

    # ── STATE ISOLATION FIX ──────────────────────────────────────────────────
    if new_session:
        session = session_manager.reset(session_id)
    else:
        session = session_manager.get(session_id)
    # ────────────────────────────────────────────────────────────────────────

    logger.info("chat_stream_request", extra={
        "session_id"        : session_id,
        "new_session"       : new_session,
        "attempts_at_start" : session.get("attempts", 0),
        "failed_steps_count": len(session.get("failed_steps", [])),
    })

    yield from _process_chat_stream(question, session, vector_store, embedding_service, session_id)


# =====================================================
# CORE LOGIC — Sync & Stream (pisah agar tidak campur yield+return)
# =====================================================


def detect_confirmation(question: str) -> Optional[bool]:
    """Detect user reply to confirmation prompt.

    Returns:
        True  -> affirmative (Sudah/Iya/etc.)
        False -> negative (Belum/Tidak/Gagal/etc.)
        None  -> ambiguous / not an answer to confirmation
    """
    if not question:
        return None
    q = question.strip().lower()

    # Affirmative tokens
    if re.search(r"\b(sudah|iya|ya|yes|done|selesai|berhasil|ok|oke)\b", q):
        logger.debug("detect_confirmation_affirmative", extra={"text": q[:120]})
        return True

    # Negative tokens
    if re.search(r"\b(belum|tidak|gagal|belum berhasil|masih|tidak bisa|no)\b", q):
        logger.debug("detect_confirmation_negative", extra={"text": q[:120]})
        return False

    # Ambiguous or unrelated
    logger.debug("detect_confirmation_ambiguous", extra={"text": q[:120]})
    return None


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

        # ── Global Incident Fallback ──────────────────────────────────
        # 1. Coba ambil link dari GlobalSetting (diatur admin via Dashboard).
        # 2. Jika kosong, gunakan escalation_guide() yang mencari via KB DB.
        preamble = "Mohon maaf langkah-langkah di atas belum berhasil membantu.\n\n"
        try:
            from apps.rag.models import GlobalSetting
            gs_obj = GlobalSetting.objects.filter(key="DEFAULT_INCIDENT_LINK").first()
            default_link = gs_obj.value.strip() if gs_obj else ""
        except Exception:
            default_link = ""

        if default_link:
            answer = (
                preamble
                + "Silakan buat tiket eskalasi melalui portal berikut:\n\n"
                + f"🌐 **Link:** [{default_link}]({default_link})"
            )
        else:
            # Fallback: cari via Knowledge Base DB (dynamic escalation_guide)
            incident_guide = escalation_guide(
                session.get("last_it_problem") or question,
                vector_store,
                embedding_service,
                doc_type="ORDER_LINK",
            )
            answer = preamble + incident_guide
        # ─────────────────────────────────────────────────────────────

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
        # Prefer a dense extracted item query to avoid keyword dilution.
        logger.info("intent_service_order", extra={"session_id": session_id, "question": question[:80]})

        # Step 1: LLM extracts the item from the CURRENT query only (no history).
        items = _extract_service_items_with_llm(question)  # history omitted: see context-bleed fix

        # Step 2: Build an action-enriched query for vector + reranker.
        # Problem: bare items like ["kertas"] → query_issue = "kertas" scores ~0.001
        # with the BGE cross-encoder (single word vs multi-sentence chunk = near-zero).
        # _refine_service_order_query adds an action prefix ("pengadaan kertas"),
        # giving the reranker a full phrase to match against TRIGGER KEYWORD rows.
        refined_query = _refine_service_order_query(question)
        if refined_query != question:
            # Refiner detected an action keyword → use enriched query
            query_issue = refined_query
        elif items:
            # Refiner returned the raw question (no action keyword found),
            # but LLM extracted items → derive minimal prefix from the question text
            action = "permintaan"
            for _kw, _label in [
                (r'\b(pinjam|peminjaman|meminjam)\b', "peminjaman"),
                (r'\b(pesan|order|memesan)\b',         "pengadaan"),
                (r'\b(pasang|pemasangan|instalasi)\b',  "pemasangan"),
                (r'\b(ajukan|pengajuan)\b',              "pengajuan"),
                (r'\b(minta|meminta|request)\b',         "permintaan"),
            ]:
                if re.search(_kw, question, re.IGNORECASE):
                    action = _label
                    break
            # REPLENISHMENT INJECTION (same logic as _refine_service_order_query)
            # Handles the edge case where the refiner was bypassed but user implied
            # stock depletion (e.g. "kertas disini sudah mau habis" with no explicit
            # action keyword — items=["kertas"] but query would be only "permintaan kertas")
            item_tokens = [str(i).strip() for i in items if i]
            if (
                _REPLENISHMENT_SIGNALS.search(question)
                and _CONSUMABLE_ITEMS.search(question)
            ):
                for signal in ("stok", "supplies"):
                    if signal not in item_tokens:
                        item_tokens.append(signal)
                action = "pengadaan"
            query_issue = f"{action} {' '.join(item_tokens)}"
        else:
            query_issue = question  # total fallback: nothing extracted

        logger.info("service_order_search_query", extra={
            "question": question[:80],
            "search_query": query_issue[:80],
            "items": items,
        })
        form_name, final_link = _find_service_order_link(query_issue, vector_store, embedding_service)
        if form_name and final_link and final_link != _LINK_NA_SENTINEL:
            answer = (
                "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan).\n\n"
                "Tolong ikuti instruksi sesuai dengan form yang tersedia dibawah.\n\n"
                f"📝 NAMA FORM: {form_name}\n\n"
                f"🔗 Link: [{final_link}]({final_link})"
            )
        elif form_name:
            answer = (
                "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan).\n\n"
                f"Form yang sesuai untuk permintaan Anda adalah **{form_name}**.\n\n"
                f"Saat ini link langsung untuk form ini belum tersedia. "
                f"Silakan kunjungi Portal IT Support dan cari form **\"{form_name}\"** secara manual:\n\n"
                f"🌐 **Portal IT Support:** [{_PORTAL_FALLBACK_URL}]({_PORTAL_FALLBACK_URL})"
            )
        else:
            guide = escalation_guide(query_issue, vector_store, embedding_service, doc_type="ORDER_LINK")
            answer = (
                "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
                "Berikut adalah link form yang perlu Anda isi:\n\n"
                f"{guide}"
            )
    else:  # IT_PROBLEM
        if session["attempts"] == 0:
            session["last_it_problem"] = question
        
        _track_failed_steps(question, session)
        
        rag_query, rag_device, rag_symptom = rewrite_query_for_rag(
            question, session["history"], 
            original_problem=session.get("last_it_problem", "")
        )

        # Store extracted device/symptom in session for downstream streaming guardrails
        session["rag_device"] = rag_device
        session["rag_symptom"] = rag_symptom

        answer = get_llm_response(
            question, session["history"], "troubleshoot",
            vector_store, embedding_service,
            rag_query=rag_query,
            failed_steps=session["failed_steps"],
            session=session,
            rag_device=rag_device,
            rag_symptom=rag_symptom,
        )
        
        session["attempts"] += 1

        # Konfirmasi "Sudah/Belum" sudah ditambahkan oleh _post_process_troubleshoot().
        # JANGAN append _SOLVED_CONFIRMATION_PROMPT di sini — itu penyebab duplikasi.
        session["offered_support"] = True
        session["awaiting_support_confirmation"] = True

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
        # Prefer a dense extracted item query to avoid keyword dilution.
        logger.info("intent_service_order_stream", extra={"session_id": session_id, "question": question[:80]})

        # Mirror exact query-building logic from _process_chat_sync SERVICE_ORDER branch
        items = _extract_service_items_with_llm(question)  # history omitted: context-bleed fix

        refined_query = _refine_service_order_query(question)
        if refined_query != question:
            query_issue = refined_query
        elif items:
            action = "permintaan"
            for _kw, _label in [
                (r'\b(pinjam|peminjaman|meminjam)\b', "peminjaman"),
                (r'\b(pesan|order|memesan)\b',         "pengadaan"),
                (r'\b(pasang|pemasangan|instalasi)\b',  "pemasangan"),
                (r'\b(ajukan|pengajuan)\b',              "pengajuan"),
                (r'\b(minta|meminta|request)\b',         "permintaan"),
            ]:
                if re.search(_kw, question, re.IGNORECASE):
                    action = _label
                    break
            # Mirror replenishment injection from sync path (stream path)
            item_tokens = [str(i).strip() for i in items if i]
            if (
                _REPLENISHMENT_SIGNALS.search(question)
                and _CONSUMABLE_ITEMS.search(question)
            ):
                for signal in ("stok", "supplies"):
                    if signal not in item_tokens:
                        item_tokens.append(signal)
                action = "pengadaan"
            query_issue = f"{action} {' '.join(item_tokens)}"
        else:
            query_issue = question

        logger.info("service_order_search_query", extra={
            "question": question[:80],
            "search_query": query_issue[:80],
            "items": items,
        })
        form_name, final_link = _find_service_order_link(query_issue, vector_store, embedding_service)
        if form_name and final_link and final_link != _LINK_NA_SENTINEL:
            answer = (
                "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan).\n\n"
                f"📝 NAMA FORM: {form_name}\n"
                f"🔗 Link: [{final_link}]({final_link})"
            )
        elif form_name:
            answer = (
                "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan).\n\n"
                f"Form yang sesuai untuk permintaan Anda adalah **{form_name}**.\n\n"
                f"Saat ini link langsung untuk form ini belum tersedia. "
                f"Silakan kunjungi Portal IT Support dan cari form **\"{form_name}\"** secara manual:\n\n"
                f"🌐 **Portal IT Support:** [{_PORTAL_FALLBACK_URL}]({_PORTAL_FALLBACK_URL})"
            )
        else:
            guide = escalation_guide(query_issue, vector_store, embedding_service, doc_type="ORDER_LINK")
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
        rag_query, rag_device, rag_symptom = rewrite_query_for_rag(
            question, session["history"], 
            original_problem=session.get("last_it_problem", "")
        )

        session["rag_device"] = rag_device
        session["rag_symptom"] = rag_symptom

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

        # Konfirmasi "Sudah/Belum" sudah ditambahkan oleh _post_process_troubleshoot().
        # JANGAN yield/append _SOLVED_CONFIRMATION_PROMPT di sini — itu penyebab duplikasi.
        session["offered_support"] = True
        session["awaiting_support_confirmation"] = True

    # 4. Finalisasi: Update history dan simpan session
    if answer:
        _update_history(session, question, answer)
        session_manager.save(session_id, session)
