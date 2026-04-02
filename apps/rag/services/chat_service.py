"""
chat_service.py — IT Support Chatbot SITI (Production-Ready)
apps/rag/services/chat_service.py

Arsitektur Intent Detection (3 Layer):
  Layer 1: Rule-based regex   → instant, 0ms, deterministik (~80% kasus)
  Layer 2: Semantic Routing   → embedding cosine similarity (~10% kasus)
  Layer 3: LLM JSON fallback  → akurat tapi lambat (~10% kasus ambigu)

Fitur utama:
  - OutOfScopeSemanticsDetector: tolak pertanyaan non-IT sebelum LLM dipanggil
  - rewrite_query_for_rag: contextual query rewriting untuk follow-up
  - get_context_for_session: session-level RAG caching, cegah cross-topic drift
  - failed_steps tracking: ingat langkah yang sudah gagal, tidak mengulang
  - Hardcoded DISCLAIMER: 100% muncul saat SOP tidak ditemukan
  - _process_chat router: pisah sync/stream agar tidak ada campur yield+return
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
    "Anda adalah AI IT Support perusahaan yang sangat kompeten.\n"
    "ATURAN MUTLAK:\n"
    "1. SELALU gunakan Bahasa Indonesia. DILARANG KERAS menggunakan Bahasa Inggris.\n"
    "2. Tunjukkan empati kepada pengguna.\n"
    "3. Jika ada panduan SOP di dalam konteks, IKUTI PERSIS panduan tersebut.\n"
    "4. JANGAN mengarang langkah-langkah di luar SOP tanpa disclaimer."
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
        "repeat_penalty": 1.1, "num_predict": 600, "mirostat": 0,
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
    system_rule = {"role": "system", "content": SYSTEM_RULE_CONTENT}
    llm_config = get_llm_config(config_name)
    if temperature is not None:
        llm_config["temperature"] = temperature

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[system_rule] + messages,
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
    system_rule = {"role": "system", "content": SYSTEM_RULE_CONTENT}
    llm_config = get_llm_config(config_name)
    if temperature is not None:
        llm_config["temperature"] = temperature

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[system_rule] + messages,
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
    """
    # Tidak perlu rewrite jika belum ada history atau pertanyaan sudah panjang
    if not history or len(question.split()) > 8:
        return question

    # Ambil HANYA pesan user (bukan jawaban bot) untuk mencegah topic drift
    user_messages = [
        msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
        for msg in history[-6:]
        if msg["role"] == "user"
    ]

    if not user_messages:
        return question

    history_text = "\n".join(f"- {m}" for m in user_messages)
    anchor = f"Topik masalah: {original_problem}\n" if original_problem else ""

    rewrite_prompt = (
        f"{anchor}"
        f"Pesan-pesan user sebelumnya:\n{history_text}\n"
        f"Pesan terbaru: {question}\n\n"
        "Tugas: Tulis ulang pesan terbaru menjadi satu kalimat pencarian mandiri "
        "dalam Bahasa Indonesia.\n"
        "WAJIB: Pertahankan topik masalah yang sama, sertakan apa yang sudah dicoba.\n"
        "DILARANG: Mengubah topik atau menambahkan masalah baru.\n"
        "Jawab HANYA dengan kalimat pencariannya saja."
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
    r'helpdesk|eskalasi|bantuan manusia)\b',
    re.IGNORECASE,
)
_REJECT_PATTERNS = re.compile(
    r'\b(tidak mau|jangan|batal|tidak perlu|ga usah|gak usah|cancel)\b',
    re.IGNORECASE,
)
# Sapaan singkat — diambil dari versi lama (lebih lengkap)
_GREETING_PATTERNS = re.compile(
    r'^(halo|hai|hi|hey|selamat\s+(pagi|siang|sore|malam)|good\s+(morning|afternoon)|'
    r'terima kasih|makasih|thanks|thank\s+you|oke|ok|sip|siap|noted|'
    r'permisi|saya ada pertanyaan.*|mau tanya.*|bisa bantu.*)[!.,\s]*$',
    re.IGNORECASE,
)
# Kalimat yang JELAS bukan IT Support — meski ada kata IT di dalamnya
# "siapa pencipta wifi", "jokes laptop", "tutorial origami", "laptop lecet fisik"
_NON_IT_INTENT_PATTERNS = re.compile(
    r'\b(siapa\s+(pencipta|penemu|pembuat|pendiri|yang\s+menciptakan)|'
    r'sejarah|asal[.\s-]?usul|kapan\s+ditemukan|kapan\s+diciptakan|'
    r'jokes?|humor|lucu|cerita\s+lucu|meme|'
    r'resep|masak|makanan|minuman|kuliner|restoran|'
    r'presiden|gubernur|bupati|politik|pemilu|'
    r'bola|olahraga|liga|pertandingan|skor|'
    r'artis|film|lagu|musik|konser|'
    r'cuaca|ramalan|zodiak|horoskop|'
    r'matematika|fisika|kimia|biologi|geografi|'
    r'harga\s+saham|crypto|bitcoin|investasi|'
    r'origami|kerajinan|craft|diy|mainan|permainan|'
    r'tutorial\s+(membuat|membentuk|menghias)|'
    r'cara\s+membuat\s+(boneka|mainan|hiasan)|'
    r'panduan\s+(seni|melukis|menyanyi|menari)|'
    r'pelajaran\s+(matematika|bahasa|seni|musik)|'
    r'berikanlah.*(tutorial|panduan|cara\s+membuat)|'
    r'coret|baret|lecet|goresan|cacat\s+fisik|rusak\s+fisik|pecah|penyok|kotor|'
    r'membersihkan|merawat|memoles|poles|lap|gosok|cuci|'
    r'cara\s+(membersihkan|merawat|memoles)\s+'
    r'(laptop|komputer|perangkat|monitor|keyboard|printer|mouse|debu))\b',
    re.IGNORECASE,
)
# Kalimat yang JELAS butuh bantuan IT teknis
_IT_PROBLEM_PATTERNS = re.compile(
    r'\b(tidak\s+bisa|gabisa|nggak\s+bisa|tidak\s+berfungsi|tidak\s+konek|'
    r'error|eror|hang|freeze|lambat|lemot|mati|rusak|bermasalah|'
    r'gagal|fail|crash|bluescreen|blue\s+screen|not\s+responding|'
    r'lupa\s+password|reset\s+password|tidak\s+bisa\s+login|akun\s+terkunci|'
    r'tidak\s+terdeteksi|tidak\s+muncul|hilang|tidak\s+nyambung|putus|'
    r'install|uninstall|update|upgrade|setting|konfigurasi|setup)\b',
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
    "- REQUEST_IT_SUPPORT : User minta dihubungkan ke tim IT manusia\n"
    "- REJECT_IT_SUPPORT  : User menolak eskalasi\n"
    "- GENERAL_CHAT       : Sapaan singkat saja (halo, terima kasih, ok)\n"
    "- OUT_OF_SCOPE       : Pertanyaan yang BUKAN tentang masalah IT\n\n"
    "ATURAN PENTING:\n"
    "Pertanyaan tentang TEKNOLOGI tapi bukan masalah/bantuan IT = OUT_OF_SCOPE\n"
    "Pertanyaan tentang PEMBERSIHAN/PERAWATAN FISIK perangkat = OUT_OF_SCOPE\n"
    "Tutorial/Panduan/Cara membuat sesuatu (selain IT) = OUT_OF_SCOPE\n\n"
    "Contoh OUT_OF_SCOPE:\n"
    "  'siapa pencipta wifi'                    → OUT_OF_SCOPE\n"
    "  'berikan jokes tentang wifi'             → OUT_OF_SCOPE\n"
    "  'tutorial membuat mainan kertas origami' → OUT_OF_SCOPE\n"
    "  'bagaimana cara kerja VPN'               → OUT_OF_SCOPE (edukasi, bukan masalah)\n"
    "  'cara membuat hiasan gantungan kunci'    → OUT_OF_SCOPE\n"
    "  'laptop saya lecet dan rusak fisik'      → OUT_OF_SCOPE (physical damage)\n"
    "  'cara membersihkan keyboard laptop'      → OUT_OF_SCOPE (physical cleaning)\n"
    "  'siapa presiden indonesia'               → OUT_OF_SCOPE\n\n"
    "Contoh IT_PROBLEM:\n"
    "  'wifi saya tidak bisa konek'             → IT_PROBLEM\n"
    "  'VPN saya error'                         → IT_PROBLEM\n"
    "  'laptop saya lambat'                     → IT_PROBLEM\n"
    "  'bagaimana cara reset password'          → IT_PROBLEM\n"
    "  'tidak bisa login email perusahaan'      → IT_PROBLEM\n"
    "  'keyboard saya tidak berfungsi'          → IT_PROBLEM (malfunction, bukan fisik)\n"
)


def detect_intent_rules(question: str) -> Optional[str]:
    """
    Layer 1: Rule-based — hanya untuk kasus yang 100% pasti.
    Return None jika tidak yakin → lanjut ke Layer 2/3.
    """
    q = question.strip()

    if _ESCALATION_PATTERNS.search(q): return "REQUEST_IT_SUPPORT"
    if _REJECT_PATTERNS.search(q):     return "REJECT_IT_SUPPORT"
    if _GREETING_PATTERNS.match(q):    return "GENERAL_CHAT"

    # Cek NON_IT SEBELUM IT_PROBLEM agar "jokes wifi" tidak lolos sebagai IT_PROBLEM
    if _NON_IT_INTENT_PATTERNS.search(q): return "OUT_OF_SCOPE"
    if _IT_PROBLEM_PATTERNS.search(q):    return "IT_PROBLEM"

    return None  # Ambigu → lanjut ke Layer 2/3


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

        valid = {"REQUEST_IT_SUPPORT","REJECT_IT_SUPPORT","GENERAL_CHAT","IT_PROBLEM","OUT_OF_SCOPE"}
        if intent in valid:
            return intent

    except (json.JSONDecodeError, Exception) as e:
        logger.warning("intent_json_parse_failed", extra={"error": str(e)})
        # Fallback: string matching pada raw output
        raw_text = response.get("message", {}).get("content", "").upper() \
                   if 'response' in locals() else ""
        for intent in ["REQUEST_IT_SUPPORT","REJECT_IT_SUPPORT","OUT_OF_SCOPE","GENERAL_CHAT","IT_PROBLEM"]:
            if intent in raw_text:
                return intent

    logger.warning("intent_detection_fallback_used", extra={"question": question[:80]})
    return "IT_PROBLEM"  # Safe default


def detect_intent(question: str, embedding_service=None) -> str:
    """
    Entry point intent detection: 3-layer pipeline.

    Layer 1 → Rule-based regex (instant, ~80% kasus)
    Layer 2 → Semantic Routing via embedding cosine similarity (~10% kasus)
    Layer 3 → LLM JSON classifier (~10% kasus ambigu)
    """
    # Layer 1: Rule-based
    rule_result = detect_intent_rules(question)
    if rule_result:
        logger.info("intent_detected", extra={
            "intent_source": "rules",
            "intent": rule_result,
            "confidence": 0.95,
        })
        return rule_result

    # Layer 2: Semantic Routing
    if embedding_service:
        try:
            detector = get_semantic_detector(embedding_service)
            semantic_category, similarity = detector.detect(question)
            if semantic_category:
                logger.info("intent_detected", extra={
                    "intent_source": "semantic_routing",
                    "intent"       : "OUT_OF_SCOPE",
                    "category"     : semantic_category,
                    "confidence"   : round(similarity, 3),
                })
                return "OUT_OF_SCOPE"
        except Exception as e:
            # Semantic layer gagal → lanjut ke LLM, jangan crash
            logger.warning("semantic_layer_skipped", extra={"error": str(e)})

    # Layer 3: LLM fallback
    llm_result = detect_intent_llm_fallback(question)
    logger.info("intent_detected", extra={
        "intent_source": "llm_fallback",
        "intent"       : llm_result,
        "confidence"   : 0.80,
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

def escalation_guide(query_issue: str, vector_store, embedding_service) -> str:
    """
    Cari panduan eskalasi dari database.

    Strategi:
    1. Cari di doc_type="ESCALATION" dulu (database khusus eskalasi)
    2. Fallback ke doc_type="TROUBLESHOOT" jika tidak ada
       (kb_troubleshoot.txt sering diupload sebagai TROUBLESHOOT)

    PENTING: query_issue harus berisi masalah IT awal (last_it_problem),
    bukan kalimat "tolong hubungi IT Support" — karena kalimat itu
    tidak semantically similar dengan isi database.
    """
    try:
        results = retrieve_context(
            query_issue, vector_store, embedding_service,
            doc_type="ESCALATION", top_k=1,
        )

        if not results:
            logger.info("escalation_fallback_troubleshoot", extra={"query": query_issue[:50]})
            results = retrieve_context(
                query_issue, vector_store, embedding_service,
                doc_type="TROUBLESHOOT", top_k=1,
            )

        if not results:
            return (
                "Panduan eskalasi spesifik belum tersedia di database kami.\n"
                "Silakan hubungi IT Support melalui portal helpdesk."
            )
        return results[0]["content"]

    except Exception as e:
        logger.error("escalation_guide_error", extra={"error": str(e)})
        return "Terjadi kesalahan saat mengambil panduan eskalasi. Hubungi IT Support secara langsung."


def detect_confirmation(text: str) -> Optional[bool]:
    """Return True/False/None (None = bukan ya maupun tidak)."""
    text = text.lower().strip()
    if re.search(r'\b(tidak|tak|ga|gak|nggak|batal|stop|jangan)\b', text): return False
    if re.search(r'\b(iya|ya|yap|yep|betul|oke|ok|sip|silakan|lanjut|mau)\b', text): return True
    return None


# =====================================================
# LLM RESPONSE — System prompt lengkap dari versi lama
# =====================================================

# Disclaimer hardcoded (bukan instruksi ke LLM) → 100% muncul saat SOP tidak ada
DISCLAIMER = (
    "⚠️ *Mohon maaf, masalah ini belum tercatat dalam SOP resmi kami.*\n\n"
    "Berikut adalah saran umum yang dapat Anda coba:\n\n"
)

_SOP_SYSTEM_PROMPT_TEMPLATE = """\
Anda adalah SITI, AI IT Support tingkat L1 di perusahaan. \
Anda sangat disiplin, profesional, dan kaku terhadap prosedur.

=== KONTEKS SOP RESMI (WAJIB DIIKUTI 100%) ===
{context}
==============================================

INSTRUKSI KETAT:
1. BAHASA MUTLAK: Wajib 100% menggunakan Bahasa Indonesia formal. \
DILARANG menggunakan Bahasa Inggris kecuali istilah teknis (Cache, Login, Restart).
2. KEPATUHAN SOP: Anda HANYA boleh memberikan langkah yang tertulis di KONTEKS SOP di atas. \
DILARANG mengarang, menambah, atau memodifikasi berdasarkan pengetahuan eksternal.
3. EKSEKUSI BERURUTAN: Berikan panduan TAHAP DEMI TAHAP (1, 2, 3...). \
JANGAN melompati atau merangkum beberapa langkah.
4. LARANGAN ESKALASI PREMATUR: JANGAN suruh user buat tiket ke IT Helpdesk \
KECUALI user sudah menyatakan SELURUH langkah teknis telah gagal.
5. ISOLASI TOPIK: Jika ada >1 KATEGORI SOP di konteks, pilih SATU yang paling cocok. \
Abaikan kategori lainnya.
6. KONSISTENSI TOPIK: Jika user bilang langkah gagal, tetap gunakan SOP dari KATEGORI \
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
PENTING: Masalah ini TIDAK ADA di SOP resmi. Berikan saran umum saja.
Format:
  - Periksakan hal X
  - Coba langkah Y
  - Jika masih bermasalah, hubungi IT Support
Jawab dalam Bahasa Indonesia.\
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
        llm_answer = generate_llm(
            [{"role": "system", "content": _FALLBACK_SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": question}],
            config_name="fallback_general",
        )
        logger.info("llm_response_ok", extra={
            "type": "fallback", "elapsed_ms": int((time.time()-t0)*1000)
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
    r'\b(masih|belum|tidak berhasil|gagal|tidak bisa|sama saja|tidak mempan)\b',
    re.IGNORECASE,
)


def _track_failed_steps(question: str, session: Dict) -> None:
    """Catat ringkasan jawaban bot terakhir sebagai 'langkah yang sudah dicoba'."""
    if _FAILURE_SIGNALS.search(question) and session["history"]:
        last_bot_msgs = [m["content"] for m in session["history"] if m["role"] == "assistant"]
        if last_bot_msgs:
            summary = last_bot_msgs[-1][:60] + "..."
            if summary not in session["failed_steps"]:
                session["failed_steps"].append(summary)


def _update_history(session: Dict, question: str, answer: str) -> None:
    """Simpan percakapan, batasi 6 pesan terakhir (3 turn)."""
    session["history"].append({"role": "user",      "content": question})
    session["history"].append({"role": "assistant", "content": answer})
    if len(session["history"]) > 6:
        session["history"] = session["history"][-6:]


# =====================================================
# ESCALATION PROMPT
# =====================================================

_ESCALATION_OFFER = (
    "\n\n---\n"
    "Masalah ini sepertinya membutuhkan penanganan lebih lanjut. "
    "Apakah Anda ingin saya pandu untuk menghubungi tim IT Support? (Ya/Tidak)"
)

_OUT_OF_SCOPE_REPLY = (
    "Maaf, saya hanya dapat membantu dengan pertanyaan seputar IT seperti "
    "masalah wifi, printer, laptop, email, VPN, atau software perusahaan. 😊\n\n"
    "Apakah ada masalah IT yang bisa saya bantu?"
)


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
    Proses konfirmasi eskalasi.
    Return string jawaban jika konfirmasi ditangani, None jika tidak.
    """
    confirmation = detect_confirmation(question)

    if confirmation is True:
        session["awaiting_support_confirmation"] = False
        session["attempts"] = 0
        guide  = escalation_guide(
            session["last_it_problem"] or question, vector_store, embedding_service
        )
        answer = f"Baik, saya akan bantu mencarikan panduan eskalasi untuk Anda.\n\n{guide}"
        _update_history(session, question, answer)
        session_manager.save(session_id, session)
        return answer

    elif confirmation is False:
        session["awaiting_support_confirmation"] = False
        session["offered_support"] = False
        answer = "Baik, mari kita coba langkah lain. Apakah ada hal lain yang bisa saya bantu?"
        _update_history(session, question, answer)
        session_manager.save(session_id, session)
        return answer

    else:
        # User bertanya hal baru (bukan Ya/Tidak) → reset state eskalasi
        session["awaiting_support_confirmation"] = False
        session["offered_support"]   = False
        session["attempts"]          = 0
        session["cached_context"]    = None
        return None  # Lanjut proses question sebagai request baru


def _process_chat_sync(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    session_id: str,
) -> str:
    """NON-STREAMING logic — hanya return str, tidak ada yield."""

    # ── Handle konfirmasi eskalasi ─────────────────────────
    if session["awaiting_support_confirmation"]:
        result = _handle_escalation_confirmation(
            question, session, vector_store, embedding_service, session_id
        )
        if result is not None:
            return result
        # result=None → question baru, lanjut ke bawah

    # ── Deteksi intent (3 layer) ───────────────────────────
    intent = detect_intent(question, embedding_service)
    logger.info("intent_resolved", extra={"session_id": session_id, "intent": intent})

    # ── Klarifikasi (hanya IT_PROBLEM turn pertama) ────────
    if intent == "IT_PROBLEM" and session["attempts"] == 0:
        clarification = needs_clarification(question, session["history"])
        if clarification:
            _update_history(session, question, clarification)
            session_manager.save(session_id, session)
            return clarification

    # ── Route berdasarkan intent ───────────────────────────
    if intent == "GENERAL_CHAT":
        answer = get_llm_response(question, session["history"], "small_talk")

    elif intent == "OUT_OF_SCOPE":
        answer = _OUT_OF_SCOPE_REPLY

    elif intent == "REQUEST_IT_SUPPORT":
        session["attempts"]       = 0
        session["offered_support"] = False
        guide  = escalation_guide(
            session.get("last_it_problem") or question, vector_store, embedding_service
        )
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"

    elif intent == "REJECT_IT_SUPPORT":
        session["offered_support"] = False
        answer = "Baik, saya akan tetap berusaha membantu Anda di sini. Silakan ceritakan masalahnya lebih lanjut."

    else:  # IT_PROBLEM
        if session["attempts"] == 0:
            session["last_it_problem"] = question

        _track_failed_steps(question, session)

        rag_query = rewrite_query_for_rag(
            question, session["history"],
            original_problem=session.get("last_it_problem", ""),
        )

        answer = get_llm_response(
            question, session["history"], "troubleshoot",
            vector_store, embedding_service,
            rag_query   = rag_query,
            failed_steps= session["failed_steps"],
            session     = session,
        )
        session["attempts"] += 1

        if session["attempts"] >= 2 and not session["offered_support"]:
            session["offered_support"]              = True
            session["awaiting_support_confirmation"] = True
            answer += _ESCALATION_OFFER

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
    """STREAMING logic — hanya yield, tidak ada return nilai."""

    # ── Handle konfirmasi eskalasi ─────────────────────────
    if session["awaiting_support_confirmation"]:
        result = _handle_escalation_confirmation(
            question, session, vector_store, embedding_service, session_id
        )
        if result is not None:
            yield result
            return
        # result=None → question baru, lanjut ke bawah

    # ── Deteksi intent ─────────────────────────────────────
    intent = detect_intent(question, embedding_service)
    logger.info("intent_resolved", extra={"session_id": session_id, "intent": intent})

    # ── Klarifikasi ────────────────────────────────────────
    if intent == "IT_PROBLEM" and session["attempts"] == 0:
        clarification = needs_clarification(question, session["history"])
        if clarification:
            _update_history(session, question, clarification)
            session_manager.save(session_id, session)
            yield clarification
            return

    # ── Route berdasarkan intent ───────────────────────────
    if intent == "GENERAL_CHAT":
        full_answer = []
        for token in get_llm_response_stream(question, session["history"], "small_talk"):
            full_answer.append(token)
            yield token
        answer = "".join(full_answer)

    elif intent == "OUT_OF_SCOPE":
        answer = _OUT_OF_SCOPE_REPLY
        yield answer

    elif intent == "REQUEST_IT_SUPPORT":
        session["attempts"]       = 0
        session["offered_support"] = False
        guide  = escalation_guide(
            session.get("last_it_problem") or question, vector_store, embedding_service
        )
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
        yield answer

    elif intent == "REJECT_IT_SUPPORT":
        session["offered_support"] = False
        answer = "Baik, saya akan tetap berusaha membantu Anda di sini. Silakan ceritakan masalahnya lebih lanjut."
        yield answer

    else:  # IT_PROBLEM
        if session["attempts"] == 0:
            session["last_it_problem"] = question

        _track_failed_steps(question, session)

        rag_query = rewrite_query_for_rag(
            question, session["history"],
            original_problem=session.get("last_it_problem", ""),
        )

        full_answer = []
        for token in get_llm_response_stream(
            question, session["history"], "troubleshoot",
            vector_store, embedding_service,
            rag_query   = rag_query,
            failed_steps= session["failed_steps"],
            session     = session,
        ):
            full_answer.append(token)
            yield token
        answer = "".join(full_answer)

        session["attempts"] += 1

        if session["attempts"] >= 2 and not session["offered_support"]:
            session["offered_support"]              = True
            session["awaiting_support_confirmation"] = True
            answer += _ESCALATION_OFFER
            yield _ESCALATION_OFFER

    _update_history(session, question, answer)
    session_manager.save(session_id, session)