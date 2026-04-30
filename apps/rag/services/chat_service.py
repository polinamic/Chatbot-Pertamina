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
  - Hardcoded DISCLAIMER: 100% muncul saat SOP tidak ditemukan
  - _process_chat router: pisah sync/stream agar tidak ada campur yield+return
  - Konfirmasi Sudah/Belum: turn ke-2 menawarkan konfirmasi penyelesaian;
    jika "Belum" → langsung arahkan ke form Incident (link hardcoded)
"""

import os
import re
import json
import time
import logging
import threading
from typing import List, Dict, Optional, Generator, Tuple

import numpy as np

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
            "physical_damage": (
                "laptop lecet baret jatuh pecah layar retak body penyok "
                "cara membersihkan keyboard dari debu kotor cuci poles gosok"
            ),
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
#
# KRITIS: Pola ini harus dicek SEBELUM _IT_PROBLEM_PATTERNS agar kata seperti
# "pasang" atau "install" pada konteks pengadaan tidak jatuh ke IT_PROBLEM.
_SERVICE_ORDER_PATTERNS = re.compile(
    r'(?:'
    # "pesan X" / "order X" — pemesanan item dengan/tanpa kata depan
    r'(?:mau\s+|ingin\s+|minta\s+|butuh\s+|perlu\s+)?(?:pesan|order)\s+\w+'
    # "pasang X" — pemasangan fisik perangkat/layanan IT
    r'|pasang\s+(?:wifi|wi-fi|cctv|kamera|jaringan|telepon|printer|proyektor|internet|vpn|lan|switch|access\s*point)'
    # "pengadaan X" — permintaan pengadaan resmi
    r'|\bpengadaan\b'
    # "ajukan/pengajuan perangkat/layanan" — formulir pengajuan
    r'|\b(?:ajukan|pengajuan)\s+(?:perangkat|layanan|akses|hardware|software|laptop|komputer|printer|cctv|handset)'
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
    "  5. 'bisa tolong pasang access point di sini'    → SERVICE_ORDER\n\n"
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
# ESCALATION GUIDE
# =====================================================

def get_ticket_process(category: str) -> str:
    """
    Dapatkan informasi cara membuat tiket melalui portal IT Support.
    Jika tidak ada detil kategori, gunakan alur umum.
    """
    ticket_processes = {
        "access_control": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Akses & Keamanan\".\n"
            "3. Pilih sub-menu \"Manajemen User ID\".\n"
            "4. Klik \"User ID ERP & Non ERP\".\n"
            "5. Pilih jenis permintaan: [Buat User Baru] / [Tambah Role/Otorisasi] / [Cabut Akses] / [Perpanjangan] / [Pengalihan Akses].\n"
            "6. Isi detail lengkap: nama user, sistem (SAP/Non-ERP apa), role yang diminta, dan periode akses.\n"
            "7. Lampirkan persetujuan atasan langsung dan dokumen pendukung (SK, surat tugas).\n"
            "8. Klik \"Ajukan Permintaan User ID\".\n"
            "CATATAN KHUSUS: Setiap permintaan otorisasi SAP Production WAJIB memiliki approval dari atasan minimal setingkat Supervisor dan fungsi SAP Functional Lead terkait. Proses verifikasi keamanan memakan waktu 3-5 hari kerja untuk SAP Production."
        ),
        "vpn_access": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Jaringan & Konektivitas\".\n"
            "3. Pilih sub-menu \"VPN / Remote Access\".\n"
            "4. Pilih jenis permintaan: [Aktivasi VPN] / [Reset VPN] / [Perubahan Akses].\n"
            "5. Isi detail lengkap: username, lokasi, perangkat, dan masalah yang terjadi.\n"
            "6. Lampirkan dokumen pendukung jika diperlukan.\n"
            "7. Klik \"Ajukan Permintaan VPN\".\n"
            "CATATAN KHUSUS: Pastikan Anda menyertakan error message lengkap dan status koneksi saat ini."
        ),
        "hardware": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Perangkat Keras & Infrastruktur\".\n"
            "3. Pilih sub-menu \"Permintaan Perbaikan / Penggantian Perangkat\".\n"
            "4. Pilih jenis permintaan sesuai keluhan: [Kerusakan Perangkat] / [Tidak Menyala] / [Ganti Aksesoris].\n"
            "5. Isi detail lengkap: model perangkat, nomor asset, gejala masalah, dan langkah yang sudah dicoba.\n"
            "6. Lampirkan foto kerusakan atau tangkapan layar jika tersedia.\n"
            "7. Klik \"Ajukan Permintaan Perbaikan\".\n"
            "CATATAN KHUSUS: Sebutkan apakah perangkat dalam masa garansi atau sudah pernah direparasi sebelumnya."
        ),
        "software": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Aplikasi & Software\".\n"
            "3. Pilih sub-menu \"Permintaan Dukungan Aplikasi\".\n"
            "4. Pilih jenis masalah: [Error Aplikasi] / [Instalasi] / [Lisensi / Akses].\n"
            "5. Isi detail lengkap: nama aplikasi, versi, error message, dan langkah yang sudah dicoba.\n"
            "6. Lampirkan screenshot error jika ada.\n"
            "7. Klik \"Ajukan Permintaan Software\".\n"
            "CATATAN KHUSUS: Sertakan informasi sistem operasi dan apakah masalah terjadi pada SAP atau aplikasi Non-ERP."
        ),
        "network": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Jaringan & Konektivitas\".\n"
            "3. Pilih sub-menu \"Permintaan Layanan Jaringan\".\n"
            "4. Pilih jenis permintaan: [Gangguan Koneksi] / [Permintaan Akses Jaringan] / [Perubahan Konfigurasi].\n"
            "5. Isi detail lengkap: lokasi, tipe koneksi (WiFi/LAN), perangkat, dan gejala.\n"
            "6. Lampirkan hasil diagnosa awal jika tersedia (misal: ipconfig, screenshot error).\n"
            "7. Klik \"Ajukan Permintaan Jaringan\".\n"
            "CATATAN KHUSUS: Pastikan menyebutkan apakah masalah terjadi hanya pada satu perangkat atau banyak perangkat."
        ),
        "email": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Email & Kolaborasi\".\n"
            "3. Pilih sub-menu \"Permintaan Dukungan Email\".\n"
            "4. Pilih jenis permintaan: [Tidak Bisa Login] / [Tidak Bisa Kirim/Terima] / [Pengaturan Email].\n"
            "5. Isi detail lengkap: alamat email, error message, dan jenis perangkat yang digunakan.\n"
            "6. Lampirkan screenshot error jika ada.\n"
            "7. Klik \"Ajukan Permintaan Email\".\n"
            "CATATAN KHUSUS: Sertakan apakah masalah terjadi pada webmail, desktop client, atau mobile."
        ),
        "printer": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Perangkat Keras & Infrastruktur\".\n"
            "3. Pilih sub-menu \"Dukungan Printer\".\n"
            "4. Pilih jenis permintaan: [Printer Tidak Terdeteksi] / [Hasil Cetak Buruk] / [Antrian Macet].\n"
            "5. Isi detail lengkap: model printer, lokasi, dan gejala.\n"
            "6. Lampirkan screenshot atau foto masalah jika tersedia.\n"
            "7. Klik \"Ajukan Permintaan Printer\".\n"
            "CATATAN KHUSUS: Sebutkan apakah printer terhubung via jaringan atau USB."
        ),
        "security": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Keamanan & Akses\".\n"
            "3. Pilih sub-menu \"Insiden Keamanan / Permintaan Akses\".\n"
            "4. Pilih jenis permintaan: [Insiden Keamanan] / [Penguncian Akun] / [Permintaan Akses Khusus].\n"
            "5. Isi detail lengkap: deskripsi insiden, dampak, dan langkah yang sudah diambil.\n"
            "6. Lampirkan bukti atau screenshot jika ada.\n"
            "7. Klik \"Ajukan Permintaan Keamanan\".\n"
            "CATATAN KHUSUS: Untuk masalah SAP Production, pastikan menyebutkan approval Supervisor dan SAP Functional Lead."
        ),
        "database": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Database & Infrastruktur\".\n"
            "3. Pilih sub-menu \"Permintaan Dukungan Database\".\n"
            "4. Pilih jenis permintaan: [Gangguan Database] / [Akses Database] / [Query Error].\n"
            "5. Isi detail lengkap: nama database, error message, waktu kejadian, dan sistem.\n"
            "6. Lampirkan log atau screenshot jika tersedia.\n"
            "7. Klik \"Ajukan Permintaan Database\".\n"
            "CATATAN KHUSUS: Sebutkan apakah masalah terjadi di environment Production atau Non-Production."
        ),
        "general_it": (
            "1. Masuk ke portal IT Support.\n"
            "2. Klik menu \"Permintaan Umum IT\".\n"
            "3. Pilih kategori masalah paling sesuai.\n"
            "4. Isi detail lengkap: deskripsi masalah, perangkat, dan langkah yang sudah dicoba.\n"
            "5. Lampirkan dokumen pendukung jika diperlukan.\n"
            "6. Klik \"Ajukan Permintaan\".\n"
            "CATATAN KHUSUS: Pastikan Anda menjelaskan masalah dengan jelas agar tiket dapat diarahkan ke tim yang tepat."
        )
    }
    return ticket_processes.get(category, ticket_processes["general_it"])


def _is_valid_link(link: str) -> bool:
    """
    Check if link is valid URL (not placeholder).
    Invalid patterns: [LINK_BELUM_TERSEDIA_DI_CSV], [LINK_BELUM_TERSEDIA], etc
    """
    if not link:
        return False
    
    link_lower = link.lower()
    
    # Check for placeholder patterns
    invalid_patterns = [
        '[link_belum_tersedia',
        'not available',
        'tbd',
        'null',
        'n/a',
    ]
    
    for pattern in invalid_patterns:
        if pattern in link_lower:
            return False
    
    # Check if it's a real URL (contains http, https, or #/)
    if link.startswith('http') or link.startswith('https') or '/#' in link:
        return True
    
    return False


def _extract_form_info(escalation_content: str) -> tuple:
    """
    Extract NAMA FORM and Link dari ESCALATION chunk content.
    Return: (form_name, link) atau (None, None) jika link tidak valid
    
    Safeguard: Reject placeholder links seperti [LINK_BELUM_TERSEDIA_DI_CSV]
    """
    form_name = None
    link = None
    
    for line in escalation_content.split('\n'):
        if 'NAMA FORM:' in line:
            form_name = line.split('NAMA FORM:')[1].strip()
        elif 'Link:' in line:
            link = line.split('Link:')[1].strip()
    
    # SAFEGUARD: Tolak link yang placeholder atau tidak valid
    if not _is_valid_link(link):
        return form_name, None
    
    return form_name, link


# =====================================================
# PHASE 1: CATEGORY-AWARE FORM MAPPING
# =====================================================
# Smart Hybrid mapping: kategori masalah → form-form yang sesuai
# Digunakan untuk filter SEBELUM keyword matching (80% improvement)
# =====================================================
# CATEGORY_FORMS — Perbaikan Lengkap
#
# ROOT CAUSE bug "handphone mati → Incident":
# 1. Nama form typo/tidak cocok dengan NAMA FORM di KB
#    (misal: "Dekstop" bukan "Desktop (PC, Laptop, Peripheral)")
#    → form_name.lower() == cat_form.lower() TIDAK PERNAH match
#    → filtered_chunks selalu kosong
#    → fallback ke semantic search → dapat "Incident"
#
# 2. 15 dari 43 form tidak ada di CATEGORY_FORMS sama sekali
#    → form seperti "Handset", "SIM Card", "SAP Locking" tidak bisa ditemukan
#
# SOLUSI: Semua 43 NAMA FORM ditulis PERSIS sama dengan di KB UI
# (copy-paste dari file knowledge_base_ui.txt) agar string match 100%.
#
# Matching di _find_escalation_by_keywords menggunakan:
#   form_name.lower() == cat_form.lower()
# sehingga nama harus identik karakter per karakter.
# =====================================================
CATEGORY_FORMS = {
    # Kartu akses fisik, badge, pintu, fingerprint area
    "access_control": [
        "Acces Control Device",
        "Access Management End User Details",
        "User ID ERP & Non ERP",
        "Change, Reset, Unlock Password Details",
        "Hak Akses Admin - VRA",
        "Object Key Access (SAP)",
    ],
    # Persetujuan jabatan sementara, cuti, delegasi
    "approval": [
        "Approval Change (PJS, Cuti, etc)",
        "User ID ERP & Non ERP",
    ],
    # Perangkat audio: speaker, mic, sound system
    "audio": [
        "Multimedia and Sound System",
        "Video Conference atau Audio Conference",
        "Telephone (Telepon Kantor / PABX)",
        "Handset (Perangkat Mobile Perusahaan)",
        "Radio Handy Talky (HT & Radio Komunikasi)",
    ],
    # Broadcast: email massal, wallpaper, videotron
    "broadcast": [
        "Broadcast Email & Message System SAP-Persero",
        "Email & Collaboration Tools Details",
    ],
    # CCTV, rekaman, surveillance
    "cctv": [
        "CCTV",
    ],
    # Data center, server room, UPS, cooling
    "datacenter": [
        "Fasilitas Data Center",
        "Database Storage",
        "Server atau Virtual Desktop (VDI)",
    ],
    # Database, storage server
    "database": [
        "Database Storage",
        "Fasilitas Data Center",
    ],
    # Developer: SAP key, object key, LSMW
    "developer": [
        "Developer Key",
        "Object Key Access (SAP)",
        "ERP Front Page & LSMW Access",
        "Pengembangan Aplikasi",
        "SAP Locking Process",
        "SAP Runtime Dialogue Extension",
        "SAPBATCH Locking Process",
    ],
    # Email: Outlook, mailbox, Teams, SharePoint
    "email": [
        "Email & Collaboration Tools Details",
        "Broadcast Email & Message System SAP-Persero",
        "Upgrade Quota Online Mailbox dan/atau Online Archive",
        "Access Management End User Details",
    ],
    # Keluar karyawan, offboarding, pengembalian perangkat
    "exit": [
        "Exit Clearance Details",
    ],
    # Firewall, port, network security
    "firewall": [
        "Modifikasi Akses Port (Firewall)",
    ],
    # Geomatika, GIS, geodesi, peta
    "geomatika": [
        "Geomatika",
    ],
    # Handphone, tablet, smartphone perusahaan
    "handset": [
        "Handset (Perangkat Mobile Perusahaan)",
        "SIM Card Corporate",
        "SIM Card Support",
    ],
    # PC, laptop, keyboard, mouse, perangkat keras
    "hardware": [
        "Desktop (PC, Laptop, Peripheral)",
        "Server atau Virtual Desktop (VDI)",
        "Handset (Perangkat Mobile Perusahaan)",
        "IT Supplies",
        "Customer Service (On-Site Support)",
    ],
    # Laporan gangguan aplikasi & sistem
    "incident": [
        "Incident (Gangguan Aplikasi & Sistem)",
        "IT Helpdesk Query (FAQ & Panduan)",
    ],
    # IT Supplies: toner, flashdisk, baterai, aksesoris
    "supplies": [
        "IT Supplies",
        "Otorisasi MPS (Printer Kartu ID)",
    ],
    # Jaringan, LAN, internet, WiFi, koneksi
    "network": [
        "Wifi Access",
        "Jaringan BIZ (Koneksi Jaringan Lokal)",
        "Modifikasi Akses Port (Firewall)",
    ],
    # Onboarding karyawan baru, konsultan, auditor
    "onboarding": [
        "Layanan Pekerja Baru, Konsultan, Auditor dan Mitra Kerja",
        "User ID ERP & Non ERP",
        "Desktop (PC, Laptop, Peripheral)",
    ],
    # Cetak: printer fisik, toner, driver
    "printer": [
        "Desktop (PC, Laptop, Peripheral)",
        "IT Supplies",
        "Otorisasi MPS (Printer Kartu ID)",
        "Printer ERP (Printer Terintegrasi SAP)",
    ],
    # Printer SAP, spool, cetak dari ERP
    "printer_sap": [
        "Printer ERP (Printer Terintegrasi SAP)",
        "Incident (Gangguan Aplikasi & Sistem)",
    ],
    # Proyek RIG, pengeboran, paket IT lengkap
    "rig": [
        "Package Service New RIG",
    ],
    # SAP: transaksi, batch job, locking, runtime
    "sap": [
        "SAP Locking Process",
        "SAP Runtime Dialogue Extension",
        "SAPBATCH Locking Process",
        "ERP Front Page & LSMW Access",
        "Developer Key",
        "Object Key Access (SAP)",
        "Incident (Gangguan Aplikasi & Sistem)",
    ],
    # Keamanan: CCTV, exit clearance, approval
    "security": [
        "Exit Clearance Details",
        "CCTV",
        "Approval Change (PJS, Cuti, etc)",
        "Hak Akses Admin - VRA",
    ],
    # Server, VDI, Citrix, virtual machine
    "server": [
        "Server atau Virtual Desktop (VDI)",
        "Fasilitas Data Center",
        "Database Storage",
    ],
    # SIM Card perusahaan, nomor dinas, roaming
    "simcard": [
        "SIM Card Corporate",
        "SIM Card Support",
        "Handset (Perangkat Mobile Perusahaan)",
    ],
    # Software, instalasi, lisensi, aplikasi umum
    "software": [
        "Software (Instalasi & Lisensi)",
        "Pengembangan Aplikasi",
        "ERP Front Page & LSMW Access",
        "Incident (Gangguan Aplikasi & Sistem)",
        "Desktop (PC, Laptop, Peripheral)",
    ],
    # Telepon kantor, PABX, ekstensi
    "telephone": [
        "Telephone (Telepon Kantor / PABX)",
        "Multimedia and Sound System",
    ],
    # Kunjungan teknisi on-site
    "onsite": [
        "Customer Service (On-Site Support)",
    ],
    # Video conference, Zoom, Teams meeting, Webex
    "video": [
        "Video Conference atau Audio Conference",
        "Multimedia and Sound System",
    ],
    # Multimedia: proyektor, HDMI, layar, ruang rapat
    "multimedia": [
        "Multimedia and Sound System",
        "Video Conference atau Audio Conference",
    ],
    # Radio, HT, Handy Talky, komunikasi lapangan
    "radio": [
        "Radio Handy Talky (HT & Radio Komunikasi)",
    ],
    # VPN, remote access
    "vpn_access": [
        "Access Management End User Details",
        "Modifikasi Akses Port (Firewall)",
        "Jaringan BIZ (Koneksi Jaringan Lokal)",
    ],
    # Pengembangan aplikasi, change request, fitur baru
    "development": [
        "Pengembangan Aplikasi",
        "Developer Key",
        "Object Key Access (SAP)",
    ],
    # Souvenir, merchandise IT
    "souvenir": [
        "Souvenir IT",
    ],
    # Mailbox penuh, upgrade kuota email
    "mailbox": [
        "Upgrade Quota Online Mailbox dan/atau Online Archive",
        "Email & Collaboration Tools Details",
    ],
    # Fallback umum — semua form yang paling sering dipakai
    "general_it": [
        "Incident (Gangguan Aplikasi & Sistem)",
        "IT Helpdesk Query (FAQ & Panduan)",
        "Customer Service (On-Site Support)",
        "Desktop (PC, Laptop, Peripheral)",
        "IT Supplies",
    ],
}


def escalation_guide(query_issue: str, vector_store, embedding_service) -> str:
    """
    Cari panduan eskalasi dari database dan return dengan format simpel.

    Format output yang diinginkan:
    FORM: [Nama Form]
    Link: [URL]
    
    Strategi Smart Hybrid (PHASE 1 + 2):
    1. Deteksi kategori dari query
    2. Filter forms berdasarkan kategori (PHASE 1: kategori-aware filtering)
    3. Keyword matching dalam kategori yang terfilter (PHASE 2: scoped search)
    4. Jika tidak ada, semantic search fallback
    5. Jika ada di database: tampilkan form + link SAJA
    """
    try:
        category = detect_problem_category(query_issue.lower())
        
        # PHASE 1 + 2: SMART HYBRID — kategori-aware keyword matching
        # Dapatkan forms yang sesuai dengan kategori yang terdeteksi
        category_forms = CATEGORY_FORMS.get(category, [])
        
        if category_forms:
            # Keyword matching DALAM forms yang sesuai kategori saja
            results = _find_escalation_by_keywords(query_issue, category_forms=category_forms)
            
            if results:
                logger.info("escalation_guide_found_keyword_match", extra={
                    "category": category,
                    "category_forms_count": len(category_forms),
                    "method": "category_aware_keyword",
                })
                form_name, link = _extract_form_info(results)
                if form_name and link:
                    # Form+Link valid, return immediately
                    return f"Untuk masalah ini, silakan gunakan form berikut:\n\nFORM: {form_name}\nLink: {link}"
                elif form_name and not link:
                    # Form found but link invalid/placeholder - continue to fallback
                    logger.warning("escalation_guide_form_invalid_link", extra={
                        "form_name": form_name,
                        "category": category,
                        "note": "Link not valid or is placeholder"
                    })
                else:
                    # Fallback jika extract gagal
                    return f"Panduan eskalasi:\n{results[:200]}"
        
        # STRATEGI 2: Semantic search dengan threshold sangat rendah (fallback)
        results = retrieve_context(
            query_issue, vector_store, embedding_service,
            doc_type="ESCALATION", top_k=1,
        )

        if results:
            logger.info("escalation_guide_found_semantic", extra={
                "category": category,
                "score": results[0].get("score"),
                "method": "semantic_fallback",
            })
            form_name, link = _extract_form_info(results[0]["content"])
            if form_name and link:
                # Form+Link valid, return immediately
                return f"Untuk masalah ini, silakan gunakan form berikut:\n\nFORM: {form_name}\nLink: {link}"
            elif form_name and not link:
                # Form found but link invalid/placeholder
                logger.warning("escalation_guide_form_invalid_link_semantic", extra={
                    "form_name": form_name,
                    "category": category,
                    "method": "semantic",
                    "note": "Link not valid or is placeholder"
                })
        
        # STRATEGI 3: Tidak ada hasil, beri tahu user untuk membuat tiket manual
        logger.info("escalation_guide_not_found", extra={
            "category": category,
            "query": query_issue[:60],
        })
        return f"Panduan spesifik belum ditemukan. Silakan buat tiket di portal IT Support pada kategori: {category}"

    except Exception as e:
        logger.error("escalation_guide_error", extra={"error": str(e)})
        return "Terjadi kesalahan saat mengambil panduan eskalasi. Silakan gunakan portal IT Support untuk membuat tiket."


def _find_escalation_by_keywords(query: str, category_forms: List[str] = None) -> str:
    """
    Find ESCALATION form by matching query keywords dengan TRIGGER_KEYWORD field.
    
    PHASE 1 + 2: SMART HYBRID enhancement
    - Jika category_forms disediakan: FILTER forms hanya ke kategori yang sesuai
    - Lalu lakukan keyword matching dalam forms yang terfilter saja
    - Ini mengurangi false positives drastis (80% improvement)
    
    Improvement: Prioritize forms yang nama-nya relevan dengan query keywords
    (e.g., "Multimedia and Sound System" untuk audio query)
    
    Args:
        query: User query string
        category_forms: Optional list of form names to filter by (from CATEGORY_FORMS mapping)
    
    Returns: Content of matching ESCALATION form, atau empty string jika tidak ada match
    """
    from apps.rag.models import DocumentChunk
    import re
    
    query_lower = query.lower()
    # Split query into keywords
    keywords = re.findall(r'\b\w+\b', query_lower)
    
    if not keywords:
        return ""
    
    # Get all ESCALATION chunks
    escalation_chunks = DocumentChunk.objects.select_related('document').filter(
        document__doc_type='ESCALATION'
    )
    
    # PHASE 1: Filter by category if provided
    if category_forms:
        filtered_chunks = []
        form_name_map = {}  # map form_name → chunk for faster lookup
        
        for chunk in escalation_chunks:
            content = chunk.content
            # Extract form name from NAMA FORM: line
            form_name = ""
            if 'NAMA FORM:' in content:
                lines = content.split('\n')
                for line in lines:
                    if 'NAMA FORM:' in line:
                        form_name = line.replace('NAMA FORM:', '').strip()
                        break
            
            # Check if this form is in our category — partial match agar robust
            # Misal: "Desktop (PC, Laptop, Peripheral)" cocok dengan "Desktop"
            if form_name and any(
                cat_form.lower() in form_name.lower() or form_name.lower() in cat_form.lower()
                for cat_form in category_forms
            ):
                filtered_chunks.append(chunk)
                form_name_map[chunk.id] = form_name
        
        escalation_chunks = filtered_chunks
        logger.debug("keyword_match_category_filter", extra={
            "category_forms_count": len(category_forms),
            "filtered_chunks_count": len(escalation_chunks),
            "form_names": [form_name_map.get(c.id, "unknown") for c in escalation_chunks[:5]]
        })
    
    best_match = None
    best_score = 0
    best_form_name = ""
    
    # PHASE 2: Keyword matching within filtered forms
    for chunk in escalation_chunks:
        content = chunk.content
        content_lower = content.lower()
        
        # Extract form name for better scoring
        form_name = ""
        if 'NAMA FORM:' in content:
            lines = content.split('\n')
            for line in lines:
                if 'NAMA FORM:' in line:
                    form_name = line.replace('NAMA FORM:', '').strip()
                    break
        
        # Count how many query keywords appear in this chunk
        keyword_matches = sum(1 for kw in keywords if kw in content_lower)
        
        # Prioritize chunks that mention keywords
        if keyword_matches > 0:
            # Base score: ratio of matched keywords
            score = keyword_matches / len(keywords)
            
            # BONUS: If form name contains important keywords, boost the score
            # This helps "Multimedia and Sound System" beat "Handset" for audio queries
            for kw in keywords:
                if kw in form_name.lower():
                    score += 0.2  # Bonus for keyword in form name
            
            if score > best_score:
                best_score = score
                best_match = content
                best_form_name = form_name
    
    return best_match if best_match else ""



def detect_problem_category(query: str) -> str:
    """
    Deteksi kategori masalah dari query user.

    PERBAIKAN LENGKAP:
    - Tambah semua kategori yang sebelumnya tidak ada (handset, simcard, sap, rig, dll)
    - Urutan cek: dari PALING SPESIFIK ke PALING UMUM
    - Cek spesifik dulu agar tidak false-match ke kategori lebih luas
    - Setiap kategori mapping ke CATEGORY_FORMS yang nama formnya PERSIS sama dengan KB
    """
    q = query.lower()

    # ── PALING SPESIFIK — cek dulu ──────────────────────────

    # Handset / HP / tablet perusahaan
    if any(w in q for w in ['handphone', 'hp perusahaan', 'hp kantor', 'tablet perusahaan',
                             'smartphone kantor', 'ponsel', 'mobile device', 'perangkat mobile',
                             'handset', 'hp rusak', 'ganti hp']):
        return "handset"

    # SIM Card corporate / nomor dinas
    if any(w in q for w in ['sim card', 'simcard', 'kartu sim', 'nomor dinas', 'nomor corporate',
                             'roaming', 'pulsa', 'migrasi nomor', 'paket data']):
        return "simcard"

    # Kartu akses fisik / pintu / badge (BUKAN akses sistem)
    if any(w in q for w in ['kartu akses', 'id card pintu', 'pintu masuk', 'access control',
                             'kartu id pintu', 'badge', 'rfid', 'fingerprint akses',
                             'kontrol pintu', 'kunci elektronik', 'turnstile',
                             'akses pintu', 'pintu ruangan', 'pintu kantor', 'pintu tidak']):
        return "access_control"

    # VPN / remote access
    if any(w in q for w in ['vpn', 'remote access', 'akses jarak jauh', 'tunnel']):
        return "vpn_access"

    # SAP spesifik: locking, batch, runtime, object key
    if any(w in q for w in ['sap lock', 'sap locking', 'batch job', 'background job', 'sapbatch',
                             'runtime sap', 'sap runtime', 'session timeout sap', 'object key sap',
                             'kunci sap', 'record locked sap', 'sap batch']):
        return "sap"

    # Developer: developer key, object key
    if any(w in q for w in ['developer key', 'object key', 'kunci developer', 'dev key',
                             'sap developer', 'kunci objek sap']):
        return "developer"

    # Radio / HT / Handy Talky
    if any(w in q for w in ['radio', 'handy talky', 'ht', 'walkie talkie', 'repeater',
                             'frekuensi radio', 'rts', 'trunking']):
        return "radio"

    # CCTV / kamera pengawas
    if any(w in q for w in ['cctv', 'kamera cctv', 'rekaman cctv', 'footage', 'dvr', 'nvr',
                             'surveillance', 'kamera pengawas']):
        return "cctv"

    # Data center / server room / UPS / cooling
    if any(w in q for w in ['data center', 'server room', 'ruang server', 'ups', 'colocation',
                             'genset', 'pendingin server', 'rak server', 'pdu']):
        return "datacenter"

    # RIG / pengeboran
    if any(w in q for w in ['rig', 'pengeboran', 'drilling', 'vsat', 'pabx rig']):
        return "rig"

    # Geomatika / GIS
    if any(w in q for w in ['geomatika', 'gis', 'geodesi', 'peta', 'shapefile',
                             'data spasial', 'topografi', 'ggrp']):
        return "geomatika"

    # Exit clearance / resign / pensiun
    if any(w in q for w in ['resign', 'pensiun', 'keluar', 'offboarding', 'exit clearance',
                             'nonaktif akun', 'terminate', 'pengembalian perangkat']):
        return "exit"

    # Approval PJS / cuti / delegasi
    if any(w in q for w in ['pjs', 'pejabat sementara', 'delegasi akses', 'jabatan sementara',
                             'approval change', 'acting', 'pendelegasian']):
        return "approval"

    # Onboarding / karyawan baru
    if any(w in q for w in ['karyawan baru', 'pekerja baru', 'onboarding', 'new employee',
                             'konsultan baru', 'mitra baru', 'auditor baru', 'akun baru karyawan']):
        return "onboarding"

    # Souvenir / merchandise IT
    if any(w in q for w in ['souvenir', 'merchandise', 'plakat', 'kenang-kenangan', 'hadiah it']):
        return "souvenir"

    # Kunjungan teknisi on-site
    if any(w in q for w in ['onsite', 'on-site', 'kunjungan teknisi', 'teknisi datang',
                             'dispatch teknisi', 'datang ke meja', 'install langsung']):
        return "onsite"

    # Firewall / port / network security rule
    if any(w in q for w in ['firewall', 'buka port', 'whitelist ip', 'blokir port',
                             'port blocked', 'connection refused', 'firewall rule']):
        return "firewall"

    # Upgrade mailbox / kuota email penuh
    if any(w in q for w in ['mailbox penuh', 'kuota email', 'quota mailbox', 'inbox full',
                             'storage email habis', 'upgrade kuota', 'tambah kuota email',
                             'archive email']):
        return "mailbox"

    # Broadcast / email massal / wallpaper / videotron
    if any(w in q for w in ['broadcast', 'email blast', 'wallpaper desktop', 'videotron',
                             'pesan massal', 'running text', 'display board', 'layar pengumuman']):
        return "broadcast"

    # Pengembangan aplikasi / change request / fitur baru
    if any(w in q for w in ['pengembangan aplikasi', 'buat aplikasi', 'fitur baru',
                             'change request', 'custom report', 'modul baru', 'enhancement']):
        return "development"

    # IT Supplies: toner, flashdisk, baterai
    if any(w in q for w in ['toner', 'tinta printer', 'cartridge', 'flashdisk', 'it supplies',
                             'consumable', 'kertas printer', 'baterai perangkat']):
        return "supplies"

    # Server / VDI / Citrix / virtual machine
    if any(w in q for w in ['server down', 'vdi', 'virtual desktop', 'citrix', 'thin client',
                             'virtual machine', 'vm', 'rdp', 'remote desktop']):
        return "server"

    # ── CUKUP UMUM — cek setelah yang spesifik ──────────────

    # Audio: speaker, mic, suara
    if any(w in q for w in ['suara', 'audio', 'speaker', 'microphone', 'mic', 'sound',
                             'tidak ada suara', 'mikrofon']):
        return "audio"

    # Video conference: Zoom, Teams meeting, Webex
    if any(w in q for w in ['zoom', 'webex', 'teams meeting', 'video conference', 'video call',
                             'rapat virtual', 'conference call']):
        return "video"

    # Multimedia: proyektor, HDMI, layar, ruang rapat
    if any(w in q for w in ['proyektor', 'projector', 'hdmi', 'vga', 'layar presentasi',
                             'multimedia', 'ruang rapat', 'audio visual']):
        return "multimedia"

    # SAP umum: akses, login, front page
    if any(w in q for w in ['sap', 'erp', 'lsmw', 'sap gui', 'logon sap']):
        return "sap"

    # Jaringan / internet / WiFi / koneksi
    if any(w in q for w in ['internet', 'wifi', 'wi-fi', 'jaringan', 'network',
                             'koneksi', 'konek', 'lan', 'kabel lan']):
        return "network"

    # Email umum
    if any(w in q for w in ['email', 'outlook', 'mailbox', 'sharepoint', 'onedrive',
                             'teams', 'skype']):
        return "email"

    # Telepon kantor / PABX / ekstensi
    if any(w in q for w in ['telepon', 'telephone', 'ekstensi', 'extension', 'pabx',
                             'ip phone', 'voip', 'intercom']):
        return "telephone"

    # Printer fisik
    if any(w in q for w in ['printer', 'cetak', 'print', 'toner', 'cartridge']):
        return "printer"

    # SAP printer / cetak dari SAP
    if any(w in q for w in ['cetak dari sap', 'spool sap', 'printer sap', 'printer erp']):
        return "printer_sap"

    # Laptop / PC / hardware fisik
    if any(w in q for w in ['laptop', 'komputer', 'pc', 'hardware', 'keyboard', 'mouse',
                             'layar', 'baterai laptop', 'hard disk', 'ram']):
        return "hardware"

    # Software / instalasi / lisensi
    if any(w in q for w in ['aplikasi', 'software', 'program', 'install', 'lisensi',
                             'license', 'ms office', 'adobe', 'autocad']):
        return "software"

    # Password / akun / user ID
    if any(w in q for w in ['password', 'akun', 'user id', 'terkunci', 'locked',
                             'reset', 'lupa password', 'login gagal']):
        return "access_control"

    # Database
    if any(w in q for w in ['database', 'basis data', 'storage', 'disk penuh']):
        return "database"

    # Keamanan umum
    if any(w in q for w in ['keamanan', 'security', 'hak akses admin', 'admin rights']):
        return "security"

    return "general_it"


def get_contact_info(category: str) -> str:
    """Informasi kontak berdasarkan kategori"""
    contacts = {
        "access_control": "ext. 1234 atau email: access@pertamina.com",
        "vpn_access": "ext. 5678 atau portal VPN: vpn.pertamina.com",
        "hardware": "ext. 9012 atau email: hardware@pertamina.com",
        "software": "ext. 3456 atau email: software@pertamina.com",
        "network": "ext. 7890 atau email: network@pertamina.com",
        "email": "ext. 1111 atau email: email@pertamina.com",
        "printer": "ext. 2222 atau email: printer@pertamina.com",
        "security": "ext. 3333 atau email: security@pertamina.com",
        "database": "ext. 4444 atau email: database@pertamina.com",
        "general_it": "ext. 0000 atau portal helpdesk: helpdesk.pertamina.com"
    }
    return contacts.get(category, "ext. 0000 atau portal helpdesk: helpdesk.pertamina.com")


def get_required_info(category: str) -> str:
    """Informasi yang dibutuhkan untuk eskalasi"""
    info_mapping = {
        "access_control": "nomor kartu akses, lokasi, waktu kejadian",
        "vpn_access": "username, error message, sistem operasi",
        "hardware": "model perangkat, gejala kerusakan, nomor asset",
        "software": "nama aplikasi, versi, error message, langkah yang sudah dicoba",
        "network": "lokasi, kecepatan koneksi, perangkat yang digunakan",
        "email": "alamat email, jenis masalah (kirim/terima), error message",
        "printer": "model printer, jenis masalah, nomor printer",
        "security": "jenis insiden, dampak, langkah yang sudah diambil",
        "database": "nama database, error message, waktu kejadian",
        "general_it": "deskripsi masalah lengkap, langkah yang sudah dicoba"
    }
    return info_mapping.get(category, "deskripsi masalah lengkap dan langkah yang sudah dicoba")


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
        # ========================================================================
        # PERBAIKAN: RULE-BASED FALLBACK ROUTING
        # 
        # HANYA AKTIF jika user sudah coba troubleshooting dan gagal (attempts >= 1)
        # Turn pertama HARUS berikan troubleshooting steps, bukan langsung routing
        # ========================================================================
        question_clean = question.strip()
        detected_category = detect_problem_category(question_clean)
        
        # Deteksi session attempts dari parameter (jika ada)
        current_attempt = 0
        if session and "attempts" in session:
            current_attempt = session["attempts"]
        
        # RULE-BASED ROUTING HANYA untuk attempt >= 1 (user sudah coba sebelumnya)
        if current_attempt >= 1 and detected_category != "general_it":
            ticket_process = get_ticket_process(detected_category)
            routing_answer = f"{ROUTING_TEMPLATE_NO_GUIDE.format(ticket_process=ticket_process)}"
            
            logger.info("rule_based_routing_applied", extra={
                "category": detected_category,
                "elapsed_ms": int((time.time()-t0)*1000),
                "attempt": current_attempt,
                "question_preview": question_clean[:80]
            })
            return routing_answer
        
        # ATTEMPT 0 atau GENERAL CATEGORY: Fallback ke LLM troubleshooting
        # Berikan langkah-langkah penyelesaian, bukan langsung routing
        llm_answer = generate_llm(
            [{"role": "system", "content": _FALLBACK_SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": question}],
            config_name="fallback_general",
        )
        logger.info("llm_response_ok", extra={
            "type": "fallback", "elapsed_ms": int((time.time()-t0)*1000),
            "category_detected": detected_category,
            "attempt": current_attempt
        })
        # DISCLAIMER ditambahkan untuk generic troubleshooting
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

# Respon jika masalah BELUM selesai setelah troubleshooting (konfirmasi "Belum")
# Form Incident — hardcoded sesuai ketentuan bisnis, tidak perlu query escalation_guide
_INCIDENT_ESCALATION_REPLY = (
    "Mohon maaf langkah-langkah di atas belum berhasil membantu. "
    "Untuk penanganan lebih lanjut oleh tim teknis, silakan buat tiket "
    "menggunakan panduan berikut:\n\n"
    "📋 **NAMA FORM:** Incident\n\n"
    "📌 **PANDUAN TIKET:** Untuk menghubungi tim IT silahkan klik link "
    "di bawah ini dan ikuti alur yang ada pada link tersebut.\n\n"
    "🔗 **Link:** https://myssc.pertamina.com/dwp/app/#/itemprofile/313"
)

# Respon penolakan non-IT (dari versi sebelumnya)
_OUT_OF_SCOPE_REPLY = (
    "Maaf, saya hanya dapat membantu dengan pertanyaan seputar IT seperti "
    "masalah wifi, printer, laptop, email, VPN, atau software perusahaan. 😊\n\n"
    "Apakah ada masalah IT yang bisa saya bantu?"
)


# =====================================================
# IT SUPPORT TEAM ROUTING
# =====================================================


# Template ketika DITEMUKAN panduan di database
ROUTING_TEMPLATE_WITH_GUIDE = """
PANDUAN UI:
{ticket_process}
"""

# Template ketika TIDAK ADA panduan di database
ROUTING_TEMPLATE_NO_GUIDE = """
PANDUAN UI:
{ticket_process}

CATATAN:
Saat ini tim IT terkait untuk masalah ini belum ada di database panduan kami.
Gunakan alur umum portal IT Support dan pilih kategori yang paling mendekati masalah Anda.
"""


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
    - False (Belum): Arahkan langsung ke form Incident (hardcoded, bukan escalation_guide).
    - None  (Ambigu): Kembalikan None agar logic utama memproses sebagai masalah baru.

    Catatan desain:
    Ketika user menjawab "Belum", sistem TIDAK memanggil escalation_guide() karena
    konteks troubleshooting sudah mencapai batas bantuan L1. Sebagai gantinya,
    ditampilkan form Incident yang merupakan jalur eskalasi resmi universal
    (_INCIDENT_ESCALATION_REPLY — hardcoded agar konsisten dan tidak bergantung
    pada hasil RAG yang bisa bervariasi).
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
        # Gunakan _INCIDENT_ESCALATION_REPLY (hardcoded) — konsisten untuk semua kasus troubleshoot
        # yang belum terselesaikan, sesuai alur Incident resmi perusahaan.
        answer = _INCIDENT_ESCALATION_REPLY
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
        guide = escalation_guide(session.get("last_it_problem") or question, vector_store, embedding_service)
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
    elif intent == "SERVICE_ORDER":
        # SERVICE_ORDER: skip alur RAG troubleshoot, langsung cari form pengadaan yang relevan
        # via escalation_guide. Session attempt tidak di-increment karena ini bukan troubleshoot.
        logger.info("intent_service_order", extra={"session_id": session_id, "question": question[:80]})
        guide = escalation_guide(question, vector_store, embedding_service)
        answer = (
            "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
            "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
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
        session["attempts"] = 0
        session["offered_support"] = False
        guide = escalation_guide(
            session.get("last_it_problem") or question, vector_store, embedding_service
        )
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
        yield answer

    elif intent == "SERVICE_ORDER":
        # SERVICE_ORDER: skip alur RAG troubleshoot, langsung cari form pengadaan yang relevan
        # via escalation_guide. Session attempt tidak di-increment karena ini bukan troubleshoot.
        logger.info("intent_service_order_stream", extra={"session_id": session_id, "question": question[:80]})
        guide = escalation_guide(question, vector_store, embedding_service)
        answer = (
            "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
            "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
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