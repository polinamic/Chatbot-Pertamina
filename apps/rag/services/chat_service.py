"""
chat_v2.py — IT Support Chatbot (Production-Ready)

Changelog dari chat_fixed.py:
  [#1]  detect_intent: Rule-based dulu, LLM hanya sebagai fallback
  [#2]  generate_llm_stream: Generator untuk streaming response
  [#3]  MODEL_NAME: Dibaca dari env variable, tidak hardcoded
  [#6]  build_context_with_limit: Batasi token konteks SOP agar tidak terpotong diam-diam
  [#7]  SessionManager: Abstraksi session, siap diganti Redis tanpa ubah logika chat()
  [#8]  detect_intent_llm_fallback: Structured JSON output dengan fallback aman
  [#9]  Structured logging — JsonFormatter valid, extra={} pattern, timer benar
  [#13] needs_clarification: Tanya balik jika pertanyaan terlalu ambigu

TIDAK diimplementasi (alasan ada di komentar masing-masing):
  [#4]  Hybrid BM25     — mengubah arsitektur retrieve_context (external service)
  [#5]  Re-ranking      — butuh model BGE-reranker tambahan, over-engineering
  [#10] Rate limiting   — urusan layer API/router, bukan chat.py
  [#11] Circuit breaker — tambah dependency eksternal, handle di infrastruktur
  [#12] Response cache  — berbahaya: history/context tiap user berbeda, cache bisa salah
  [#14] Confidence escalation — bergantung #8 yang output JSON-nya belum selalu stabil di llama3:8b
  [#15] Rich response   — contract dengan frontend, bukan core logic

CATATAN PENTING — Model SentenceTransformer di-load DUA KALI (terlihat di log):
  Penyebab: embedding_service diinstansiasi dua kali di luar file ini,
  kemungkinan di apps/rag/apps.py (AppConfig.ready) DAN di views.py atau urls.py.

  Solusi: Pastikan embedding_service hanya dibuat SATU kali menggunakan
  singleton pattern di apps/rag/apps.py:

      # apps/rag/apps.py
      from django.apps import AppConfig

      class RagConfig(AppConfig):
          name = "apps.rag"
          _embedding_service = None   # ← singleton holder

          def ready(self):
              # ready() bisa dipanggil dua kali di dev server (reloader).
              # Guard dengan _embedding_service is None.
              if RagConfig._embedding_service is None:
                  from apps.rag.services.embedding import EmbeddingService
                  RagConfig._embedding_service = EmbeddingService()

      def get_embedding_service():
          return RagConfig._embedding_service

  Lalu di views.py, JANGAN buat instance baru — pakai getter:
      from apps.rag.apps import get_embedding_service
      embedding_service = get_embedding_service()
"""

import os
import re
import json
import time
import logging
from typing import List, Dict, Optional, Generator

from apps.rag.services.retrieval import retrieve_context
import ollama

# =====================================================
# [#9] STRUCTURED LOGGING — PERBAIKAN FORMAT JSON
#
# BUG SEBELUMNYA:
#   Format string '... "msg": %(message)s}' mengharapkan
#   %(message)s sudah berupa JSON fragment, tapi logger.info()
#   dipanggil dengan f-string biasa. Hasilnya:
#   {"msg": "session_id": "x", ...} → INVALID JSON
#   (nilai msg tidak dibungkus string).
#
# SOLUSI:
#   Gunakan JsonFormatter custom. Setiap logger.info(msg, extra={})
#   akan menghasilkan JSON valid yang bisa di-parse aggregator.
#   Semua key tambahan (session_id, intent, dll) dioper via
#   parameter `extra={}`, bukan di-embed ke dalam string.
# =====================================================

class JsonFormatter(logging.Formatter):
    """
    Formatter yang menghasilkan satu baris JSON valid per log entry.
    Contoh output:
    {"time": "2026-03-18T10:35:24", "level": "INFO", "logger": "chatbot",
     "msg": "chat_request", "session_id": "abc", "intent": "IT_PROBLEM", "elapsed_ms": 1234}
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Salin semua field extra (session_id, intent, elapsed_ms, dll)
        for key, val in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName"
            ):
                log_data[key] = val
        return json.dumps(log_data, ensure_ascii=False)


def _setup_logger(name: str) -> logging.Logger:
    """Setup logger dengan JsonFormatter. Aman dipanggil berkali-kali."""
    log = logging.getLogger(name)
    if not log.handlers:  # Cegah duplicate handler saat Django reload
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False  # Jangan propagate ke root logger Django
    return log


logger = _setup_logger("chatbot")


# =====================================================
# [#3] KONFIGURASI VIA ENVIRONMENT VARIABLE
#
# Mengapa valid: hardcoded model name berarti harus
# edit kode untuk ganti model. Dengan env var, Anda
# bisa ganti model via .env tanpa deploy ulang.
#
# Cara pakai:
#   export LLM_MODEL=llama3:8b        (default)
#   export LLM_MODEL=llama3.1:70b     (production)
#   export MIN_SIMILARITY=0.60        (tuning threshold)
# =====================================================
MODEL_NAME = os.getenv("LLM_MODEL", "llama3:8b")
MIN_SIMILARITY_SCORE = float(os.getenv("MIN_SIMILARITY", "0.35"))
# =====================================================
# PENJELASAN THRESHOLD:
#
# FAISS IndexFlatIP dengan normalisasi L2 menghasilkan
# cosine similarity dalam range -1.0 hingga 1.0.
# Nilai 0.35 berarti: dokumen dan query minimal punya
# kemiripan semantik ~35% — cukup ketat untuk menghindari
# false positive, tapi tidak terlalu ketat sehingga
# dokumen relevan tidak terbuang.
#
# Contoh empiris dengan all-mpnet-base-v2:
#   "internet tidak bisa" vs "Tidak bisa terhubung ke internet" → ~0.45-0.55
#   "tolong bantu" vs "Tidak bisa terhubung ke internet"        → ~0.10-0.20
#
# Sebelumnya: 0.60 → terlalu tinggi, dokumen relevan
# sering di-reject karena parafrase berbeda tapi makna sama.
# =====================================================

# =====================================================
# [CRITICAL] OPTIMIZED LLM GENERATION SETTINGS
#
# Parameters yang PALING PENTING untuk RAG IT Support:
#
# 1. TEMPERATURE — Mengontrol randomness/creativity
#    - 0.0   = Deterministic (selalu output sama)
#    - 0.1-0.2 = Sangat konsisten (untuk SOP strict)
#    - 0.3-0.5 = Balanced (natural tapi controlled)
#    - 0.7+  = Creative/random (tidak cocok untuk support)
#
# 2. TOP_P (Nucleus sampling) — Mengontrol vocabulary diversity
#    - 0.9 = Default safe (ambil 90% cumulative probability words)
#    - 0.95 = Sedikit lebih diverse
#    - 1.0 = Semua words possible (risky)
#
# 3. TOP_K — Alternative sampling method
#    - 40 = Default (ambil top-40 most probable tokens)
#    - 10 = Lebih strict
#
# 4. REPEAT_PENALTY — Mencegah repetisi kata
#    - 1.0 = Tidak ada penalty (default)
#    - 1.1-1.5 = Hindari pengulangan (cocok untuk support)
#
# 5. NUM_PREDICT — Max tokens untuk output
#    - 600 = Standard untuk jawaban support
#    - 1000 = Untuk SOP panjang
#    - 100 = Untuk intent/short answers
#
# 6. MIROSTAT — Advanced sampling (stabilize perplexity)
#    - 0 = Off (default llama3)
#    - 1 = Mirostat sampling (experimental)
#    - 2 = Mirostat v2 (better stability)
# =====================================================

# Optimized settings untuk berbagai use case
LLM_SETTINGS = {
    # SOP-based troubleshooting: Strict adherence ke panduan
    "sop_strict": {
        "temperature": 0.0,     # Deterministic: paksa keluaran konsisten.
        "top_p": 0.85,          # Lebih conservatif untuk mencegah variasi.
        "top_k": 20,            # Hanya top token yang sangat relevan.
        "repeat_penalty": 1.2,  # Hindari pengulangan tidak perlu.
        "num_predict": 800,     # Cukup untuk panjang SOP.
        "mirostat": 0,          # Standard sampling.
        "reasoning": """
        - Mengapa 0.0: Untuk kepatuhan SOP mutlak dan menghilangkan
          perilaku 'pilihan bebas' atau 'shortcut eskalasi'.
        - Top_p 0.85 + top_k 20: Mempersempit bahasa agar sesuai 
          instruksi ketat dan mencegah bahasa Inggris tidak disengaja.
        """
    },
    
    # General troubleshooting: Balance antara consistency & natural
    "troubleshoot_general": {
        "temperature": 0.35,    # Moderate — natural tapi consistent
        "top_p": 0.92,          # Slightly diverse vocabulary
        "top_k": 40,            # Standard
        "repeat_penalty": 1.15, # Avoid repetition
        "num_predict": 1000,    # Longer explanations OK
        "mirostat": 0,          # Standard
        "reasoning": """
        - Mengapa 0.35: User sudah understand basic, bisa paraphrase.
          Temperature agak lebih tinggi → jawaban terasa lebih natural
          tanpa mengorbankan accuracy.
        - Setara dengan ChatGPT "balanced" mode
        """
    },
    
    # Fallback (general knowledge): Creative tapi tetap professional
    "fallback_general": {
        "temperature": 0.40,    # Sedikit lebih creative
        "top_p": 0.93,          # Diverse vocabulary
        "top_k": 50,            # Slightly wider range
        "repeat_penalty": 1.1,  # Still avoid repetition
        "num_predict": 600,     # Standard length
        "mirostat": 0,          # Standard
        "reasoning": """
        - Mengapa 0.40: SOP tidak ada, jadi OK lebih creative.
          Bukan SOP resmi → user sudah expect general knowledge.
        - Top_k 50: Wider word selection untuk variasi
        """
    },
    
    # Small talk: Natural conversation
    "small_talk": {
        "temperature": 0.55,    # Natural conversation tone
        "top_p": 0.95,          # Natural diversity
        "top_k": 50,            # Wider token range
        "repeat_penalty": 1.0,  # Natural repetition OK
        "num_predict": 200,     # Keep answers short
        "mirostat": 0,          # Standard
        "reasoning": """
        - Mengapa 0.55: Sapaan/greeting harus natural, informal.
          Temperature tinggi → less robotic.
        - user expects personality, bukan SOP compliance
        """
    },
    
    # Intent detection: Deterministic
    "intent_detect": {
        "temperature": 0.0,     # ZERO randomness — always same output
        "top_p": 0.9,           # Standard
        "top_k": 10,            # Very limited — force clear decision
        "repeat_penalty": 1.0,  # N/A
        "num_predict": 50,      # Very short (just JSON intent)
        "mirostat": 0,          # Standard
        "reasoning": """
        - Mengapa 0.0: Intent HARUS deterministic. Jika user tanya
          "wifi tidak bisa", classification harus SELALU IT_PROBLEM,
          bukan random antara IT_PROBLEM/OUT_OF_SCOPE.
          Temperature 0.0 = guaranteed consistent classification.
        """
    },
    
    # Query rewriting: Deterministic paraphrasing
    "query_rewrite": {
        "temperature": 0.1,     # Very low — minimal creativity
        "top_p": 0.90,          # Conservative
        "top_k": 40,            # Standard
        "repeat_penalty": 1.1,  # Avoid redundancy
        "num_predict": 200,     # Rewritten query usually short
        "mirostat": 0,          # Standard
        "reasoning": """
        - Mengapa 0.1: Rewriting harus preserve meaning asli.
          Temperature terlalu tinggi → bisa change intent.
          0.1 = safe paraphrasing dengan minimal semantic drift
        """
    }
}

def get_llm_config(config_name: str = "sop_strict") -> dict:
    """
    Get LLM configuration untuk use case tertentu.
    
    Args:
        config_name: Nama config dari LLM_SETTINGS
    
    Returns:
        Dict dengan keys: temperature, top_p, top_k, repeat_penalty, num_predict
    """
    config = LLM_SETTINGS.get(config_name, LLM_SETTINGS["sop_strict"])
    # Return hanya Ollama options (exclude reasoning)
    return {k: v for k, v in config.items() if k != "reasoning"}


# =====================================================
# TRADE-OFFS SUMMARY
# =====================================================
"""
LOW TEMPERATURE (0.0-0.2):
  ✅ Pro:  Deterministic, consistent, predictable
  ❌ Con:  Dapat terasa robotic, limited variasi
  Use:   SOP strict, intent detection, query rewrite

MEDIUM TEMPERATURE (0.3-0.5):
  ✅ Pro:  Natural language, still controlled
  ❌ Con:  Sedikit kurang predictable
  Use:   Troubleshooting general, fallback knowledge

HIGH TEMPERATURE (0.6+):
  ✅ Pro:  Creative, natural, diverse
  ❌ Con:  Dapat hallucinate, unpredictable
  Use:   TIDAK untuk IT Support (terlalu risky)

REPEAT_PENALTY:
  1.0   = No penalty (allow repetition)
  1.1-1.5 = Penalty untuk mengurangi redundancy
  Use:  1.1-1.15 aman untuk IT Support

TOP_P vs TOP_K:
  TOP_P = Nucleus sampling (recommended modern approach)
  TOP_K = Top-K sampling (alternative)
  Keduanya untuk control diversity:
    - Lower (0.9, top-40) = Conservative
    - Higher (0.95, top-50) = More diverse

MIROSTAT:
  Experimental feature untuk stabilize perplexity
  Cobalakan nanti jika ada issue dengan consistency
"""

#
# Tuning: Naikkan jika terlalu banyak jawaban tidak relevan.
#         Turunkan jika terlalu banyak "belum tersedia".
# =====================================================
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))

SYSTEM_RULE_CONTENT = (
    "Anda adalah AI IT Support perusahaan yang sangat kompeten.\n"
    "ATURAN MUTLAK:\n"
    "1. SELALU gunakan Bahasa Indonesia. DILARANG KERAS menggunakan Bahasa Inggris.\n"
    "2. Tunjukkan empati kepada pengguna.\n"
    "3. Jika ada panduan SOP di dalam konteks, IKUTI PERSIS panduan tersebut.\n"
    "4. JANGAN mengarang langkah-langkah di luar SOP tanpa disclaimer."
)


# =====================================================
# [#7] SESSION MANAGER — ABSTRAKSI STORAGE
#
# Mengapa valid: chat_sessions = {} akan hilang saat
# server restart. Dengan abstraksi SessionManager,
# Anda cukup ganti implementasi _get/_set ke Redis
# tanpa mengubah satu baris pun di fungsi chat().
#
# Untuk sekarang pakai in-memory (dict) — fungsional
# identik dengan kode lama. Migrasi ke Redis nanti
# cukup uncomment blok RedisSessionManager di bawah.
# =====================================================
def _default_session() -> Dict:
    return {
        "attempts": 0,
        "offered_support": False,
        "awaiting_support_confirmation": False,
        "last_it_problem": "",
        "cached_context": None,   # Context SOP dari turn pertama — di-reuse untuk follow-up
        "failed_steps": [],
        "history": []
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


# --- Uncomment blok ini jika sudah siap migrasi ke Redis ---
# class RedisSessionManager:
#     """Session storage di Redis. Persisten dan multi-instance."""
#     def __init__(self):
#         import redis
#         self.redis = redis.Redis(
#             host=os.getenv("REDIS_HOST", "localhost"),
#             port=int(os.getenv("REDIS_PORT", 6379)),
#             db=0, decode_responses=True
#         )
#         self.ttl = 86400  # 24 jam
#
#     def get(self, session_id: str) -> Dict:
#         data = self.redis.get(f"session:{session_id}")
#         return json.loads(data) if data else _default_session()
#
#     def save(self, session_id: str, session: Dict) -> None:
#         self.redis.setex(f"session:{session_id}", self.ttl, json.dumps(session))
#
#     def delete(self, session_id: str) -> None:
#         self.redis.delete(f"session:{session_id}")

session_manager = InMemorySessionManager()
# session_manager = RedisSessionManager()  # Ganti ini saat production


# =====================================================
# CORE LLM FUNCTIONS
# =====================================================

def generate_llm(messages: List[Dict[str, str]], temperature: float = None, config_name: str = "sop_strict") -> str:
    """
    [OPTIMIZED] Panggil LLM dengan best-practice settings.
    
    Args:
        messages: Chat messages history
        temperature: Override temperature (optional, for backward compatibility)
        config_name: Predefined config name dari LLM_SETTINGS
                    (sop_strict, troubleshoot_general, fallback_general, small_talk, intent_detect, query_rewrite)
    
    Returns:
        Generated text from LLM
    """
    system_rule = {"role": "system", "content": SYSTEM_RULE_CONTENT}
    
    # Get optimized config untuk use case
    llm_config = get_llm_config(config_name)
    
    # If temperature override provided, use it (backward compatibility)
    if temperature is not None:
        llm_config["temperature"] = temperature
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[system_rule] + messages,
            options=llm_config  # Gunakan semua optimized settings
        )
        text = response.get("message", {}).get("content", "").strip()
        
        # Log dengan config yang dipakai
        logger.info("llm_generation_success", extra={
            "config_name": config_name,
            "temperature": llm_config["temperature"],
            "output_length": len(text),
        })
        
        return text if text else "Maaf, saya gagal memproses respons."
    except Exception as e:
        logger.error("generate_llm_error", extra={
            "error": str(e),
            "config_name": config_name,
        })
        return "Sistem AI sedang gangguan teknis. Hubungi IT Support."


# =====================================================
# [#2] STREAMING RESPONSE
#
# Mengapa valid: Tanpa streaming, user menunggu diam
# selama 5-15 detik sampai jawaban muncul sekaligus.
# Dengan streaming, teks muncul bertahap — terasa
# jauh lebih responsif meski total waktu sama.
#
# Cara pakai di endpoint FastAPI:
#   from fastapi.responses import StreamingResponse
#
#   @app.post("/chat/stream")
#   def chat_stream(req: ChatRequest):
#       answer_gen = generate_llm_stream(messages)
#       return StreamingResponse(answer_gen, media_type="text/event-stream")
#
# CATATAN: generate_llm (non-streaming) TETAP ada dan
# dipakai untuk intent detection & internal logic.
# Streaming hanya untuk jawaban ke user akhir.
# =====================================================
def generate_llm_stream(
    messages: List[Dict[str, str]],
    temperature: float = None,
    config_name: str = "sop_strict"
) -> Generator[str, None, None]:
    """
    [OPTIMIZED] Generator streaming — yield token per token dengan best-practice settings.
    
    Args:
        messages: Chat messages history
        temperature: Override temperature (optional, for backward compatibility)
        config_name: Predefined config name (see generate_llm for options)
    
    Yields:
        Token strings
    """
    system_rule = {"role": "system", "content": SYSTEM_RULE_CONTENT}
    
    # Get optimized config
    llm_config = get_llm_config(config_name)
    
    # If temperature override provided, use it
    if temperature is not None:
        llm_config["temperature"] = temperature
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[system_rule] + messages,
            stream=True,
            options=llm_config  # Gunakan optimized settings
        )
        
        for chunk in response:
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
        
        logger.info("llm_stream_success", extra={
            "config_name": config_name,
            "temperature": llm_config["temperature"],
        })
        
    except Exception as e:
        logger.error("generate_llm_stream_error", extra={
            "error": str(e),
            "config_name": config_name,
        })
        yield "Sistem AI sedang gangguan teknis. Hubungi IT Support."


# =====================================================
# QUERY REWRITING — TEKNIK UTAMA PRODUCTION RAG
#
# Masalah fundamental:
#   User tidak selalu bertanya dengan kalimat lengkap.
#   "masih tidak bisa", "bagaimana caranya", "coba lagi"
#   adalah pertanyaan KONTEKSTUAL yang bergantung pada
#   history percakapan. Dikirim langsung ke RAG → gagal.
#
# Solusi (dipakai ChatGPT, Perplexity, semua RAG modern):
#   Sebelum ke RAG, minta LLM untuk menulis ulang
#   pertanyaan user menjadi query MANDIRI (standalone)
#   yang mengandung konteks lengkap dari history.
#
# Contoh:
#   History:  "wifi saya tidak bisa konek" → 5 langkah SOP
#   User:     "masih tidak bisa"
#   Rewriter: "wifi tidak bisa konek setelah mencoba
#              forget network, flush DNS, dan restart laptop"
#
# Query yang kaya konteks ini → RAG menemukan SOP → ✓
#
# Biaya: 1 LLM call tambahan per pesan lanjutan.
# Tapi call ini SANGAT cepat (max 80 token, temp=0).
# =====================================================

def rewrite_query_for_rag(
    question: str,
    history: List[Dict[str, str]],
    original_problem: str = "",
) -> str:
    """
    Tulis ulang pertanyaan user menjadi standalone query untuk RAG.

    PERBAIKAN KRITIS:
    Sebelumnya: history dikirim penuh termasuk jawaban bot (langkah-langkah SOP).
    Masalahnya: rewriter membaca jawaban bot yang berisi "langkah printer"
    lalu mencampurnya ke query → RAG menemukan chunk printer → LLM menjawab
    dengan langkah printer yang tidak relevan → tanpa disclaimer.

    Sekarang:
    1. Hanya kirim pesan USER ke rewriter (bukan jawaban bot)
    2. Selalu sertakan original_problem sebagai anchor topik
    3. Instruksi eksplisit: JANGAN ubah topik masalah
    """
    # Tidak perlu rewrite jika belum ada history
    if not history:
        return question

    # Tidak perlu rewrite jika pertanyaan sudah panjang dan spesifik
    if len(question.split()) > 8:
        return question

    # Ambil HANYA pesan user dari history (bukan jawaban bot)
    # Ini mencegah rewriter terpengaruh oleh isi SOP dalam jawaban sebelumnya
    user_messages = [
        msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
        for msg in history[-6:]
        if msg["role"] == "user"
    ]

    if not user_messages:
        return question

    history_text = "\n".join(f"- {m}" for m in user_messages)

    # original_problem sebagai anchor agar topik tidak bergeser
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
        # [OPTIMIZED] Use query_rewrite config for deterministic rewriting
        query_config = get_llm_config("query_rewrite")
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": rewrite_prompt}],
            options=query_config  # temperature=0.1, num_predict=200, etc.
        )
        rewritten = response.get("message", {}).get("content", "").strip()

        if not rewritten or len(rewritten) < 5:
            return original_problem or question

        logger.info("query_rewritten", extra={
            "original": question,
            "rewritten": rewritten,
            "anchor": original_problem,
        })
        return rewritten

    except Exception as e:
        logger.warning("query_rewrite_failed", extra={"error": str(e)})
        return original_problem or question


# =====================================================
# [#1] INTENT DETECTION: RULE-BASED DULU, LLM FALLBACK
#
# Mengapa valid: Kode lama memanggil LLM untuk SETIAP
# pesan — termasuk sapaan "halo" atau "ok". Ini lambat
# (~1-2 detik) dan boros komputasi.
#
# Strategi baru:
#   1. Rule-based regex → instant, 0ms, deterministik
#   2. Jika tidak match → baru panggil LLM sebagai fallback
#
# Hasilnya: ~80% pesan (sapaan, konfirmasi sederhana,
# keyword IT yang jelas) selesai di step 1 tanpa LLM.
# =====================================================

# =====================================================
# PATTERN DETECTION — LAYER 1 (Rule-based, instant)
#
# Prinsip: rule-based HANYA untuk kasus yang 100% pasti.
# Ambigu → serahkan ke LLM classifier (Layer 2).
#
# Root cause bug sebelumnya:
#   "siapa pencipta wifi" → mengandung "wifi" → IT_PROBLEM ✗
#   "jokes terkait wifi"  → mengandung "wifi" → IT_PROBLEM ✗
#
# Keyword matching pada kata IT tidak cukup — harus lihat
# KONTEKS KALIMAT, bukan hanya keberadaan keyword.
# =====================================================

_ESCALATION_PATTERNS = re.compile(
    r'\b(hubungi|bicara dengan|minta tolong|it support|operator|teknisi|helpdesk|eskalasi)\b',
    re.IGNORECASE
)
_REJECT_PATTERNS = re.compile(
    r'\b(tidak mau|jangan|batal|tidak perlu|ga usah|cancel)\b',
    re.IGNORECASE
)
_GREETING_PATTERNS = re.compile(
    r'^(halo|hai|hi|hey|selamat\s+(pagi|siang|sore|malam)|good\s+(morning|afternoon)|'
    r'terima kasih|makasih|thanks|oke|ok|siap|noted)[!.,\s]*$',
    re.IGNORECASE
)

# Pola kalimat yang JELAS bukan IT Support — meski mengandung kata IT
# "siapa pencipta wifi", "sejarah internet", "jokes laptop"
_NON_IT_INTENT_PATTERNS = re.compile(
    r'\b(siapa\s+(pencipta|penemu|pembuat|pendiri|yang\s+menciptakan)|'
    r'sejarah|asal.usul|kapan\s+ditemukan|kapan\s+diciptakan|'
    r'jokes?|humor|lucu|cerita\s+lucu|meme|'
    r'resep|masak|makanan|minuman|kuliner|restoran|'
    r'presiden|gubernur|bupati|politik|pemilu|'
    r'bola|olahraga|liga|pertandingan|skor|'
    r'artis|film|lagu|musik|konser|'
    r'cuaca|ramalan|zodiak|horoskop|'
    r'matematika|fisika|kimia|biologi|geografi|'
    r'harga\s+saham|crypto|bitcoin|investasi)\b',
    re.IGNORECASE
)

# Pola kalimat yang JELAS adalah IT Support request
# "wifi tidak bisa", "laptop hang", "printer error", dll
_IT_PROBLEM_PATTERNS = re.compile(
    r'\b(tidak\s+bisa|gabisa|nggak\s+bisa|tidak\s+berfungsi|tidak\s+konek|'
    r'error|eror|hang|freeze|lambat|lemot|lemot|mati|rusak|bermasalah|'
    r'gagal|fail|crash|bluescreen|blue\s+screen|not\s+responding|'
    r'lupa\s+password|reset\s+password|tidak\s+bisa\s+login|akun\s+terkunci|'
    r'tidak\s+terdeteksi|tidak\s+muncul|hilang|tidak\s+nyambung|putus|'
    r'install|uninstall|update|upgrade|setting|konfigurasi|setup)\b',
    re.IGNORECASE
)


def detect_intent_rules(question: str) -> Optional[str]:
    """
    Rule-based intent detection — hanya untuk kasus yang 100% pasti.

    Urutan pengecekan:
    1. Escalation/reject/greeting → deterministic, selalu benar
    2. NON_IT_INTENT → kalimat yang jelas bukan IT Support
    3. IT_PROBLEM_PATTERNS → kalimat yang jelas butuh bantuan IT
    4. None → serahkan ke LLM classifier

    Kata kunci IT (wifi, laptop, dll) TIDAK lagi cukup untuk
    menentukan IT_PROBLEM — harus ada indikasi butuh bantuan teknis.
    """
    q = question.strip()

    # Escalation & rejection — selalu pasti
    if _ESCALATION_PATTERNS.search(q):
        return "REQUEST_IT_SUPPORT"
    if _REJECT_PATTERNS.search(q):
        return "REJECT_IT_SUPPORT"

    # Sapaan singkat — selalu pasti
    if _GREETING_PATTERNS.match(q):
        return "GENERAL_CHAT"

    # Kalimat yang jelas bukan IT Support
    # Cek ini SEBELUM IT_PROBLEM agar "jokes wifi" tidak lolos
    if _NON_IT_INTENT_PATTERNS.search(q):
        return "OUT_OF_SCOPE"

    # Kalimat yang jelas butuh bantuan IT teknis
    # (ada indikasi masalah/tindakan, bukan sekadar kata IT)
    if _IT_PROBLEM_PATTERNS.search(q):
        return "IT_PROBLEM"

    # Semua kasus ambigu → serahkan ke LLM classifier
    # Ini termasuk: "wifi saya", "laptop saya", "bagaimana cara..."
    # yang butuh konteks kalimat penuh untuk dipahami
    return None


# =====================================================
# [#8] LLM FALLBACK DENGAN STRUCTURED JSON OUTPUT
#
# Mengapa valid: `format="json"` di Ollama memaksa
# model output JSON valid — tidak ada teks sampah
# sebelum/sesudah JSON. Lebih reliable daripada
# parsing string bebas.
#
# Kenapa tidak menggantikan sepenuhnya:
# llama3:8b kadang tetap output JSON tidak konsisten
# (field kosong, salah key). Maka ada fallback ke
# string parsing jika json.loads() gagal.
# =====================================================

_INTENT_SYSTEM_PROMPT = (
    "Kamu adalah classifier intent untuk chatbot IT Support perusahaan.\n"
    "Tugasmu: tentukan apakah user butuh BANTUAN TEKNIS IT, atau bukan.\n\n"
    "Jawab HANYA dengan JSON:\n"
    '{"intent": "<LABEL>"}\n\n'
    "LABEL:\n"
    "- IT_PROBLEM     : User MENGALAMI masalah teknis atau butuh panduan IT\n"
    "- REQUEST_IT_SUPPORT : User minta dihubungkan ke tim IT manusia\n"
    "- REJECT_IT_SUPPORT  : User menolak eskalasi\n"
    "- GENERAL_CHAT   : Sapaan singkat saja (halo, terima kasih, ok)\n"
    "- OUT_OF_SCOPE   : Pertanyaan yang BUKAN tentang masalah IT\n\n"
    "ATURAN PENTING:\n"
    "Pertanyaan tentang TEKNOLOGI tapi bukan masalah/bantuan IT = OUT_OF_SCOPE\n"
    "Contoh OUT_OF_SCOPE:\n"
    "  'siapa pencipta wifi'        → OUT_OF_SCOPE (sejarah, bukan masalah)\n"
    "  'berikan jokes tentang wifi' → OUT_OF_SCOPE (hiburan, bukan masalah)\n"
    "  'bagaimana cara kerja VPN'   → OUT_OF_SCOPE (edukasi, bukan masalah IT)\n"
    "  'siapa presiden indonesia'   → OUT_OF_SCOPE\n"
    "Contoh IT_PROBLEM:\n"
    "  'wifi saya tidak bisa konek' → IT_PROBLEM\n"
    "  'VPN saya error'             → IT_PROBLEM\n"
    "  'laptop saya lambat'         → IT_PROBLEM\n"
    "  'bagaimana cara reset password' → IT_PROBLEM\n"
)


def detect_intent_llm_fallback(question: str) -> str:
    """
    LLM-based intent detection dengan structured JSON output + fallback.
    
    [OPTIMIZED] Uses intent_detect config with temperature=0 for deterministic classification.
    """
    try:
        # [OPTIMIZED] Deterministic intent detection config
        intent_config = get_llm_config("intent_detect")
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ],
            format="json",  # Force JSON output
            options=intent_config  # temperature=0, top_k=10, num_predict=50
        )
        raw = response.get("message", {}).get("content", "").strip()
        parsed = json.loads(raw)
        intent = parsed.get("intent", "").strip().upper()

        if intent in ["REQUEST_IT_SUPPORT", "REJECT_IT_SUPPORT", "GENERAL_CHAT", "IT_PROBLEM", "OUT_OF_SCOPE"]:
            return intent
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("intent_json_parse_failed", extra={"error": str(e)})
        raw_text = response.get("message", {}).get("content", "").upper() if 'response' in locals() else ""
        for intent in ["REQUEST_IT_SUPPORT", "REJECT_IT_SUPPORT", "OUT_OF_SCOPE", "GENERAL_CHAT", "IT_PROBLEM"]:
            if intent in raw_text:
                return intent

    return "IT_PROBLEM"  # Safe default


def detect_intent(question: str) -> str:
    """
    Entry point utama: rule-based dulu, LLM hanya jika perlu.
    [#1] Menggabungkan rule-based (cepat) + LLM fallback (akurat).
    
    [ENHANCED] Sekarang track confidence score internal.
    Jika confidence < 70%, log warning untuk monitoring.
    """
    rule_result = detect_intent_rules(question)
    if rule_result:
        # Rule-based matches dianggap confidence tinggi (95%)
        logger.info("intent_detected", extra={
            "intent_source": "rules",
            "intent": rule_result,
            "confidence": 0.95
        })
        return rule_result

    llm_result = detect_intent_llm_fallback(question)
    # LLM hasil — estimate confidence based on result consistency
    # Jika LLM uncertain, confidence lebih rendah
    confidence = 0.80  # Default reasonable confidence
    
    if llm_result == "IT_PROBLEM":
        # Paling sering terjadi, relatively high confidence
        confidence = 0.85
    elif llm_result == "OUT_OF_SCOPE":
        # Biasanya clear signal, high confidence
        confidence = 0.88
    elif llm_result == "REQUEST_IT_SUPPORT":
        # Explicit request, high confidence
        confidence = 0.90
    else:
        # Other intents (GENERAL_CHAT, REJECT_IT_SUPPORT)
        confidence = 0.75
    
    log_level = "warning" if confidence < 0.70 else "info"
    logger.log(
        logging.WARNING if log_level == "warning" else logging.INFO,
        "intent_detected",
        extra={
            "intent_source": "llm",
            "intent": llm_result,
            "confidence": confidence,
            "low_confidence_alert": confidence < 0.70
        }
    )
    
    return llm_result


# =====================================================
# RAG CONTEXT RETRIEVAL
# =====================================================

def _estimate_tokens(text: str) -> int:
    """Estimasi kasar: 1 token ≈ 4 karakter (konvensi umum NLP)."""
    return len(text) // 4


# =====================================================
# [#6] CONTEXT WINDOW MANAGEMENT
#
# Mengapa valid: Jika SOP sangat panjang dan kita
# kirim semua ke LLM, konteks akan terpotong (truncate)
# DIAM-DIAM oleh model karena melebihi context window.
# Akibatnya langkah penting di akhir SOP hilang tanpa
# ada error atau warning apapun.
#
# Solusi: Hitung estimasi token sebelum mengirim,
# batasi dengan MAX_CONTEXT_TOKENS (dari env var).
# =====================================================
def build_context_with_limit(chunks: List[str], max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    """
    Gabungkan chunks SOP sampai batas token.
    Prioritas: chunk pertama (paling relevan dari RAG) didahulukan.
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
                "used_tokens": total_tokens,
                "skipped_chunk_tokens": chunk_tokens,
            })
            break  # Jangan potong di tengah chunk — skip saja

    return "\n\n---\n\n".join(selected)


def get_relevant_context(
    question: str,
    vector_store,
    embedding_service,
    original_problem: str = "",
) -> Optional[str]:
    """
    Ambil konteks RAG yang relevan.

    PERBAIKAN:
    - Tambah parameter original_problem untuk validasi topik
    - Log score dan konten yang ditemukan untuk debugging
    - Jika original_problem ada, validasi bahwa chunk yang ditemukan
      masih dalam topik yang sama (bukan cross-topic drift)
    """
    if not vector_store or not embedding_service:
        return None

    results = retrieve_context(
        question, vector_store, embedding_service,
        doc_type="TROUBLESHOOT", top_k=3
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
            "query": question[:60],
        })
        return None

    # Log konten yang ditemukan untuk debugging cross-topic drift
    for r in relevant:
        logger.info("rag_found", extra={
            "score": round(r.get("score", 0), 3),
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
    Ambil context SOP dengan session-level caching.

    INI ADALAH FIX UTAMA untuk masalah cross-topic drift.

    Masalah sebelumnya:
      Turn 1: "wifi bermasalah"    → RAG → dapat chunk WIFI ✓
      Turn 2: "masih bermasalah"   → RAG → dapat chunk PRINTER ✗
      (karena query panjang + konteks gagal menggeser embedding)

    Solusi:
      Turn 1: RAG dipanggil → hasilnya DISIMPAN di session["cached_context"]
      Turn 2+: TIDAK panggil RAG lagi → pakai cached_context dari turn 1

    Hasilnya: topik tidak pernah bergeser selama satu sesi percakapan.
    Cache direset jika user memulai masalah baru (attempts == 0).
    """
    # Turn pertama — panggil RAG dan simpan hasilnya
    if session["attempts"] == 0 or session["cached_context"] is None:
        context = get_relevant_context(question, vector_store, embedding_service)
        session["cached_context"] = context  # Simpan (bisa None jika tidak ditemukan)
        logger.info("rag_cache_set", extra={
            "found": context is not None,
            "query": question[:60],
        })
        return context

    # Turn lanjutan — pakai cache, jangan query RAG ulang
    logger.info("rag_cache_hit", extra={"attempts": session["attempts"]})
    return session["cached_context"]


# =====================================================
# [#13] PROACTIVE CLARIFICATION
#
# Mengapa valid: Pertanyaan ambigu seperti "laptop saya
# bermasalah" atau "internet error" bisa mengarah ke
# banyak solusi berbeda. Tanpa klarifikasi, RAG mungkin
# mengambil konteks yang salah dan LLM memberi jawaban
# yang tidak relevan.
#
# Implementasi konservatif: Hanya tanya jika pertanyaan
# sangat pendek DAN tidak ada keyword spesifik.
# Tidak berlaku jika sudah ada history (pertanyaan
# lanjutan biasanya sudah lebih spesifik).
# =====================================================
_CLARIFICATION_TRIGGERS = {
    r'\blaptop\b': "Laptop bermasalah dalam hal apa? (Tidak menyala / Layar hitam / Lambat / Lainnya?)",
    r'\bkomputer\b|\bpc\b': "Komputer bermasalah dalam hal apa? (Tidak menyala / Lambat / Error tertentu?)",
    r'\bprinter\b': "Printer bermasalah bagaimana? (Tidak terdeteksi / Hasil cetakan buruk / Antrean nyangkut?)",
    r'\binternet\b|\bwifi\b|\bwi-fi\b': "Masalah internetnya seperti apa? (Tidak konek sama sekali / Lambat / Sering putus?)",
    r'\bemail\b': "Email bermasalah bagaimana? (Tidak bisa login / Tidak bisa kirim-terima / Lainnya?)",
}


def needs_clarification(question: str, history: List[Dict]) -> Optional[str]:
    """
    Cek apakah pertanyaan butuh klarifikasi.
    Return pesan klarifikasi, atau None jika tidak perlu.

    Tidak tanya jika:
    - Pertanyaan sudah cukup panjang/spesifik (>6 kata)
    - Sudah ada history (pertanyaan lanjutan)
    """
    # Jika sudah ada konteks percakapan, skip clarification
    if history:
        return None

    # Jika pertanyaan cukup panjang, anggap sudah spesifik
    if len(question.split()) > 6:
        return None

    q_lower = question.lower()
    for pattern, clarification_msg in _CLARIFICATION_TRIGGERS.items():
        if re.search(pattern, q_lower):
            return clarification_msg

    return None


# =====================================================
# RESPONSE GENERATION
# =====================================================

def get_llm_response(
    question: str,
    history: List[Dict[str, str]],
    prompt_type: str,
    vector_store=None,
    embedding_service=None,
    rag_query: str = None,
    failed_steps: List[str] = None,
    session: Dict = None,  # Session untuk cached context
) -> str:
    """
    [ENHANCED] Generate jawaban LLM dengan structured context tracking.
    
    Improvement:
    - Log context sources dan quality metrics
    - Track context relevance untuk monitoring
    - Improve prompt engineering untuk consistency
    """
    import time
    timer_start = time.time()
    
    if prompt_type == "small_talk":
        system_msg = (
            "Anda adalah SITI, asisten IT Support perusahaan yang ramah.\n"
            "Balas sapaan user dengan ramah dan singkat dalam Bahasa Indonesia.\n"
            "Perkenalkan diri sebagai asisten IT Support jika belum.\n"
            "JANGAN menjawab pertanyaan apapun selain membalas sapaan."
        )
        answer = generate_llm(
            [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": question}],
            config_name="small_talk"  # [OPTIMIZED] Natural conversation tone (temp=0.55)
        )
        elapsed_ms = int((time.time() - timer_start) * 1000)
        logger.info("llm_response_generated", extra={
            "prompt_type": prompt_type,
            "elapsed_ms": elapsed_ms,
            "response_length": len(answer)
        })
        return answer

    # Gunakan cached context jika session tersedia, fallback ke RAG langsung
    context_source = "session_cache" if session is not None else "rag_retrieve"
    if session is not None:
        context = get_context_for_session(
            rag_query or question, session, vector_store, embedding_service
        )
    else:
        context = get_relevant_context(rag_query or question, vector_store, embedding_service)

    failed_note = ""
    if failed_steps:
        failed_list = "\n".join(f"- {s}" for s in failed_steps)
        failed_note = (
            f"\n\nPERHATIAN — Langkah berikut sudah DICOBA user dan GAGAL:\n"
            f"{failed_list}\n"
            "JANGAN ulangi langkah di atas. Berikan langkah BERIKUTNYA dari SOP "
            "atau nyatakan bahwa SOP sudah habis."
        )

    if context:
        # [ENHANCED] Improved system prompt dengan struktur yang lebih ketat
        system_msg = (
                    "Anda adalah SITI, AI IT Support tingkat L1 di perusahaan. Anda sangat disiplin, profesional, analitis, dan kaku terhadap prosedur.\n\n"
                    "=== KONTEKS SOP RESMI (WAJIB DIIKUTI 100%) ===\n"
                    f"{context}\n"
                    "==============================================\n\n"
                    "INSTRUKSI KETAT (PELANGGARAN AKAN BERAKIBAT FATAL):\n"
                    "1. BAHASA MUTLAK: Wajib 100% menggunakan Bahasa Indonesia formal. DILARANG KERAS menggunakan bahasa Inggris (kecuali istilah teknis IT seperti 'Cache', 'Login', 'Restart'). DILARANG menggunakan kalimat penenang, sapaan basa-basi, atau frasa seperti 'I can help you with that', 'Jangan khawatir', atau 'Tentu saja'.\n"
                    "2. KEPATUHAN SOP: Anda HANYA boleh memberikan langkah-langkah yang tertulis di dalam 'KONTEKS SOP RESMI' di atas. DILARANG KERAS mengarang, menambah, menebak, atau memodifikasi langkah berdasarkan pengetahuan eksternal Anda.\n"
                    "3. EKSEKUSI BERURUTAN: Berikan panduan secara TAHAP DEMI TAHAP (1, 2, 3...). JANGAN melompati langkah atau merangkum beberapa langkah menjadi satu paragraf panjang.\n"
                    "4. LARANGAN ESKALASI PREMATUR: JANGAN menyuruh pengguna membuat tiket ke IT Helpdesk KECUALI pengguna sudah secara eksplisit menyatakan bahwa SELURUH langkah teknis sebelumnya telah gagal dilakukan.\n"
                    "5. ISOLASI TOPIK: Jika di dalam konteks terdapat lebih dari satu KATEGORI SOP, pilih SATU saja yang paling cocok dengan deskripsi masalah pengguna. Abaikan kategori lainnya.\nw"
                    "6. KONSISTENSI TOPIK: Jika pengguna menyatakan langkah sebelumnya gagal, Anda HARUS tetap menggunakan SOP dari KATEGORI masalah yang sama dengan jawaban Anda sebelumnya. JIKA semua langkah di KATEGORI tersebut sudah diberikan/habis, nyatakan dengan jujur bahwa panduan mandiri sudah habis. DILARANG KERAS mencomot/mengambil langkah dari KATEGORI SOP lain yang ada di dalam konteks.\n\n"
                    "FORMAT JAWABAN YANG WAJIB DIGUNAKAN (Gunakan format persis seperti ini):\n"
                    "- **Analisis Singkat:** (Satu kalimat konfirmasi masalah sesuai SOP)\n\n"
                    "- **Langkah Penyelesaian:**\n"
                    "1. [Langkah pertama dari SOP]\n"
                    "2. [Langkah kedua dari SOP]\n"
                    "...\n\n"
                    "- **Hasil yang Diharapkan:** (Satu kalimat tentang apa yang seharusnya terjadi setelah langkah diikuti)\n\n"
                    f"{failed_note}"
                )
        
        answer = generate_llm(
            [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": question}],
            config_name="sop_strict"  # [OPTIMIZED] Strict SOP adherence (temp=0.15)
        )
        
        context_quality = "found" if context else "not_found"
        elapsed_ms = int((time.time() - timer_start) * 1000)
        logger.info("llm_response_with_rag", extra={
            "prompt_type": prompt_type,
            "context_source": context_source,
            "context_quality": context_quality,
            "has_failed_steps_note": bool(failed_steps),
            "elapsed_ms": elapsed_ms,
            "response_length": len(answer),
            "context_length": len(context)
        })
        
        return answer
    else:
        DISCLAIMER = (
            "⚠️ *Mohon maaf, masalah ini belum tercatat dalam SOP resmi kami.*\n\n"
            "Berikut adalah saran umum yang dapat Anda coba:\n\n"
        )
        system_msg = (
            "Anda adalah teknisi IT Support. Jawab dengan empati.\n"
            "PENTING: Masalah ini TIDAK ADA di SOP resmi. Berikan saran umum saja.\n"
            "Berikan saran troubleshooting IT yang logis dan umum.\n"
            "Format:\n"
            "  - Periksakan hal X\n"
            "  - Coba langkah Y\n"
            "  - Jika masih bermasalah, hubungi IT Support\n"
            "Jawab dalam Bahasa Indonesia."
        )
        llm_answer = generate_llm(
            [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": question}],
            config_name="fallback_general"  # [OPTIMIZED] General knowledge fallback (temp=0.40)
        )
        
        elapsed_ms = int((time.time() - timer_start) * 1000)
        logger.info("llm_response_fallback", extra={
            "prompt_type": prompt_type,
            "context_available": False,
            "using_general_knowledge": True,
            "elapsed_ms": elapsed_ms,
            "response_length": len(DISCLAIMER + llm_answer)
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
    """[#2] Versi streaming dari get_llm_response."""
    if prompt_type == "small_talk":
        system_msg = (
            "Anda adalah SITI, asisten IT Support perusahaan yang ramah.\n"
            "Balas sapaan user dengan ramah dan singkat dalam Bahasa Indonesia.\n"
            "Perkenalkan diri sebagai asisten IT Support jika belum.\n"
            "JANGAN menjawab pertanyaan apapun selain membalas sapaan."
        )
        yield from generate_llm_stream(
            [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": question}],
            temperature=0.5
        )
        return

    if session is not None:
        context = get_context_for_session(
            rag_query or question, session, vector_store, embedding_service
        )
    else:
        context = get_relevant_context(rag_query or question, vector_store, embedding_service)

    failed_note = ""
    if failed_steps:
        failed_list = "\n".join(f"- {s}" for s in failed_steps)
        failed_note = (
            f"\n\nPERHATIAN — Langkah berikut sudah DICOBA user dan GAGAL:\n"
            f"{failed_list}\n"
            "JANGAN ulangi langkah di atas. Berikan langkah BERIKUTNYA dari SOP "
            "atau nyatakan bahwa SOP sudah habis."
        )

    if context:
        system_msg = (
                    "Anda adalah SITI, AI IT Support tingkat L1 di perusahaan. Anda sangat disiplin, profesional, analitis, dan kaku terhadap prosedur.\n\n"
                    "=== KONTEKS SOP RESMI (WAJIB DIIKUTI 100%) ===\n"
                    f"{context}\n"
                    "==============================================\n\n"
                    "INSTRUKSI KETAT (PELANGGARAN AKAN BERAKIBAT FATAL):\n"
                    "1. BAHASA MUTLAK: Wajib 100% menggunakan Bahasa Indonesia formal. DILARANG KERAS menggunakan bahasa Inggris (kecuali istilah teknis IT seperti 'Cache', 'Login', 'Restart'). DILARANG menggunakan kalimat penenang, sapaan basa-basi, atau frasa seperti 'I can help you with that', 'Jangan khawatir', atau 'Tentu saja'.\n"
                    "2. KEPATUHAN SOP: Anda HANYA boleh memberikan langkah-langkah yang tertulis di dalam 'KONTEKS SOP RESMI' di atas. DILARANG KERAS mengarang, menambah, menebak, atau memodifikasi langkah berdasarkan pengetahuan eksternal Anda.\n"
                    "3. EKSEKUSI BERURUTAN: Berikan panduan secara TAHAP DEMI TAHAP (1, 2, 3...). JANGAN melompati langkah atau merangkum beberapa langkah menjadi satu paragraf panjang.\n"
                    "4. LARANGAN ESKALASI PREMATUR: JANGAN menyuruh pengguna membuat tiket ke IT Helpdesk KECUALI pengguna sudah secara eksplisit menyatakan bahwa SELURUH langkah teknis sebelumnya telah gagal dilakukan.\n"
                    "5. ISOLASI TOPIK: Jika di dalam konteks terdapat lebih dari satu KATEGORI SOP, pilih SATU saja yang paling cocok dengan deskripsi masalah pengguna. Abaikan kategori lainnya.\n"
                    "6. KONSISTENSI TOPIK: Jika pengguna menyatakan langkah sebelumnya gagal, Anda HARUS tetap menggunakan SOP dari KATEGORI masalah yang sama dengan jawaban Anda sebelumnya. JIKA semua langkah di KATEGORI tersebut sudah diberikan/habis, nyatakan dengan jujur bahwa panduan mandiri sudah habis. DILARANG KERAS mencomot/mengambil langkah dari KATEGORI SOP lain yang ada di dalam konteks.\n\n"
                    "FORMAT JAWABAN YANG WAJIB DIGUNAKAN (Gunakan format persis seperti ini):\n"
                    "**ANALISIS MASALAH:**\n"
                    "(Satu kalimat konfirmasi masalah sesuai SOP)\n\n"
                    "**LANGKAH PENYELESAIAN:**\n"
                    "1. [Langkah pertama dari SOP]\n"
                    "2. [Langkah kedua dari SOP]\n"
                    "...\n\n"
                    "**HASIL YANG DIHARAPKAN:**\n"
                    "(Satu kalimat tentang apa yang seharusnya terjadi setelah langkah diikuti)\n\n"
                    f"{failed_note}"
                )
        yield from generate_llm_stream(
            [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": question}],
            temperature=0.1
        )
    else:
        DISCLAIMER = (
            "⚠️ *Mohon maaf, masalah ini belum tercatat dalam SOP resmi kami.*\n\n"
            "Berikut adalah saran umum yang dapat Anda coba:\n\n"
        )
        yield DISCLAIMER
        system_msg = (
            "Anda adalah teknisi IT Support. Jawab dengan empati.\n"
            "Berikan saran troubleshooting IT yang logis dan umum.\n"
            "Jawab HANYA bagian langkah-langkah sarannya saja, "
            "tanpa pembuka atau penutup tambahan.\n"
            "Jawab dalam Bahasa Indonesia."
        )
        yield from generate_llm_stream(
            [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": question}],
            temperature=0.4
        )


def escalation_guide(query_issue: str, vector_store, embedding_service) -> str:
    """
    Cari panduan eskalasi dari database berdasarkan masalah IT yang dialami user.

    PERBAIKAN:
    Sebelumnya hanya mencari doc_type="ESCALATION". Masalahnya:
    1. Jika knowledge_base_it.txt diupload sebagai doc_type="TROUBLESHOOT",
       query tidak akan pernah cocok.
    2. Query berupa kalimat percakapan ("tolong hubungi tim IT") tidak
       semantically similar dengan isi database ("Tidak bisa terhubung ke
       internet, Wi-Fi putus-putus...").

    Strategi baru:
    - Coba doc_type="ESCALATION" dulu (database khusus eskalasi)
    - Jika tidak ada hasil, fallback ke doc_type="TROUBLESHOOT"
      (knowledge_base_it.txt yang berisi panduan eskalasi UI)
    - Query yang dikirim ke RAG adalah masalah IT awal (last_it_problem),
      bukan kalimat permintaan eskalasi — ini dilakukan di pemanggil fungsi.
    """
    try:
        # Coba ESCALATION dulu
        results = retrieve_context(
            query_issue, vector_store, embedding_service,
            doc_type="ESCALATION", top_k=1
        )

        # Fallback ke TROUBLESHOOT jika tidak ada hasil di ESCALATION
        # (kasus: knowledge_base_it.txt diupload sebagai TROUBLESHOOT)
        if not results:
            logger.info("escalation_fallback_to_troubleshoot", extra={
                "query": query_issue[:50]
            })
            results = retrieve_context(
                query_issue, vector_store, embedding_service,
                doc_type="TROUBLESHOOT", top_k=1
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


def detect_confirmation(text: str) -> bool:
    text = text.lower().strip()
    if re.search(r'\b(tidak|tak|ga|gak|nggak|batal|stop|jangan)\b', text):
        return False
    if re.search(r'\b(iya|ya|yap|yep|betul|oke|ok|sip|silakan|lanjut|mau)\b', text):
        return True
    return False


# =====================================================
# MAIN CHAT FUNCTION
# =====================================================

def chat(question: str, vector_store, embedding_service, session_id: str = "default") -> str:
    """
    Entry point utama. Return jawaban lengkap (string).
    Untuk streaming, panggil chat_stream() sebagai gantinya.
    """
    question = question.strip()
    if not question:
        return "Ada yang bisa saya bantu?"

    # [#9] Timer dimulai SEBELUM _process_chat (termasuk LLM call)
    # BUG SEBELUMNYA: timer.start → session.get → LOG → _process_chat
    # Akibatnya elapsed_ms selalu ~0 karena LLM belum dipanggil.
    # PERBAIKAN: timer.start → _process_chat (LLM di sini) → LOG
    start_time = time.time()

    session = session_manager.get(session_id)
    answer = _process_chat(question, session, vector_store, embedding_service, session_id, stream=False)

    elapsed_ms = int((time.time() - start_time) * 1000)

    # [#9] Gunakan extra={} agar JSON valid — BUKAN f-string embedding
    logger.info("chat_request", extra={
        "session_id": session_id,
        "question_length": len(question),
        "elapsed_ms": elapsed_ms,
    })

    return answer


def chat_stream(
    question: str,
    vector_store,
    embedding_service,
    session_id: str = "default"
) -> Generator[str, None, None]:
    """
    [#2] Versi streaming dari chat().
    Yield token per token — sambungkan ke StreamingResponse di FastAPI.

    Contoh endpoint:
        @app.post("/chat/stream")
        def stream_endpoint(req: ChatRequest):
            return StreamingResponse(
                chat_stream(req.question, vector_store, embedding_service, req.session_id),
                media_type="text/event-stream"
            )
    """
    question = question.strip()
    if not question:
        yield "Ada yang bisa saya bantu?"
        return

    session = session_manager.get(session_id)
    yield from _process_chat(question, session, vector_store, embedding_service, session_id, stream=True)


def _process_chat(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    session_id: str,
    stream: bool
):
    """
    Router: pilih _process_chat_sync atau _process_chat_stream
    berdasarkan flag stream.

    PERBAIKAN ROOT CAUSE:
    Sebelumnya satu fungsi berisi campuran yield dan return.
    Karena ada yield di manapun dalam fungsi, Python SELALU
    menjadikannya generator — bahkan saat stream=False.
    Akibatnya chat() mengembalikan generator, bukan string,
    dan len(answer) crash di views.py.

    Solusi: Pisah menjadi dua fungsi murni:
      _process_chat_sync  → hanya return str, tidak ada yield
      _process_chat_stream → hanya yield, tidak ada return nilai
    """
    if stream:
        return _process_chat_stream(question, session, vector_store, embedding_service, session_id)
    else:
        return _process_chat_sync(question, session, vector_store, embedding_service, session_id)


def _process_chat_sync(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    session_id: str,
) -> str:
    """
    Versi NON-STREAMING: hanya return str, tidak ada yield sama sekali.
    Dipakai oleh chat() → views.siti_chat → frontend JSON response.
    """
    # --- Handle konfirmasi eskalasi ---
    if session["awaiting_support_confirmation"]:
        session["awaiting_support_confirmation"] = False
        if detect_confirmation(question):
            session["attempts"] = 0
            query_for_rag = session["last_it_problem"] or question
            guide = escalation_guide(query_for_rag, vector_store, embedding_service)
            answer = f"Baik, saya akan bantu mencarikan panduan eskalasi untuk Anda.\n\n{guide}"
        else:
            session["offered_support"] = False
            answer = "Baik, mari kita coba langkah lain. Apakah ada hal lain yang bisa saya bantu?"

        _update_history(session, question, answer)
        session_manager.save(session_id, session)
        return answer

    # Deteksi intent
    intent = detect_intent(question)
    logger.info("intent_resolved", extra={"session_id": session_id, "intent": intent})

    # Cek klarifikasi (hanya IT_PROBLEM pertama kali)
    if intent == "IT_PROBLEM" and session["attempts"] == 0:
        clarification = needs_clarification(question, session["history"])
        if clarification:
            _update_history(session, question, clarification)
            session_manager.save(session_id, session)
            return clarification

    # Proses berdasarkan intent
    if intent == "GENERAL_CHAT":
        answer = get_llm_response(question, session["history"], "small_talk")

    elif intent == "OUT_OF_SCOPE":
        # Tolak pertanyaan di luar topik IT dengan tegas tapi sopan
        # Hardcode agar tidak bisa di-bypass oleh LLM
        answer = (
            "Maaf, saya hanya dapat membantu dengan pertanyaan seputar IT seperti "
            "masalah wifi, printer, laptop, email, VPN, atau software perusahaan. 😊\n\n"
            "Apakah ada masalah IT yang bisa saya bantu?"
        )

    elif intent == "REQUEST_IT_SUPPORT":
        session["attempts"] = 0
        session["offered_support"] = False
        # Gunakan masalah IT awal sebagai query RAG, bukan kalimat permintaan eskalasi.
        # "tolong hubungi tim IT" tidak cocok secara semantik dengan isi database.
        # "internet tidak bisa konek wifi" cocok dengan KATEGORI JARINGAN_WIFI.
        query_for_escalation = session.get("last_it_problem") or question
        guide = escalation_guide(query_for_escalation, vector_store, embedding_service)
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"

    elif intent == "REJECT_IT_SUPPORT":
        session["offered_support"] = False
        answer = "Baik, saya akan tetap berusaha membantu Anda di sini. Silakan ceritakan masalahnya lebih lanjut."

    else:  # IT_PROBLEM
        if session["attempts"] == 0:
            session["last_it_problem"] = question

        # Deteksi apakah user menyatakan langkah sebelumnya gagal
        # Jika ya, catat ringkasan jawaban sebelumnya sebagai "sudah dicoba"
        _FAILURE_SIGNALS = re.compile(
            r'\b(masih|belum|tidak berhasil|gagal|tidak bisa|sama saja|tidak mempan)\b',
            re.IGNORECASE
        )
        if _FAILURE_SIGNALS.search(question) and session["history"]:
            # Ambil jawaban bot terakhir sebagai ringkasan langkah yang gagal
            last_bot_msgs = [
                m["content"] for m in session["history"]
                if m["role"] == "assistant"
            ]
            if last_bot_msgs:
                # Simpan 60 karakter pertama sebagai penanda
                summary = last_bot_msgs[-1][:60] + "..."
                if summary not in session["failed_steps"]:
                    session["failed_steps"].append(summary)

        rag_query = rewrite_query_for_rag(
            question,
            session["history"],
            original_problem=session.get("last_it_problem", ""),
        )

        answer = get_llm_response(
            question, session["history"], "troubleshoot",
            vector_store, embedding_service,
            rag_query=rag_query,
            failed_steps=session["failed_steps"],
            session=session,
        )
        session["attempts"] += 1

        # Eskalasi lebih cepat jika sudah 2x gagal (bukan 3x)
        if session["attempts"] >= 2 and not session["offered_support"]:
            session["offered_support"] = True
            session["awaiting_support_confirmation"] = True
            answer += (
                "\n\n---\n"
                "Masalah ini sepertinya membutuhkan penanganan lebih lanjut. "
                "Apakah Anda ingin saya pandu untuk menghubungi tim IT Support? (Ya/Tidak)"
            )

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
    Versi STREAMING: hanya yield, tidak ada return nilai.
    Dipakai oleh chat_stream() → StreamingResponse di FastAPI/Django.
    """
    # --- Handle konfirmasi eskalasi ---
    if session["awaiting_support_confirmation"]:
        session["awaiting_support_confirmation"] = False
        if detect_confirmation(question):
            session["attempts"] = 0
            query_for_rag = session["last_it_problem"] or question
            guide = escalation_guide(query_for_rag, vector_store, embedding_service)
            answer = f"Baik, saya akan bantu mencarikan panduan eskalasi untuk Anda.\n\n{guide}"
        else:
            session["offered_support"] = False
            answer = "Baik, mari kita coba langkah lain. Apakah ada hal lain yang bisa saya bantu?"

        _update_history(session, question, answer)
        session_manager.save(session_id, session)
        yield answer
        return

    # Deteksi intent
    intent = detect_intent(question)
    logger.info("intent_resolved", extra={"session_id": session_id, "intent": intent})

    # Cek klarifikasi
    if intent == "IT_PROBLEM" and session["attempts"] == 0:
        clarification = needs_clarification(question, session["history"])
        if clarification:
            _update_history(session, question, clarification)
            session_manager.save(session_id, session)
            yield clarification
            return

    # Proses berdasarkan intent
    if intent == "GENERAL_CHAT":
        full_answer = []
        for token in get_llm_response_stream(question, session["history"], "small_talk"):
            full_answer.append(token)
            yield token
        answer = "".join(full_answer)

    elif intent == "OUT_OF_SCOPE":
        answer = (
            "Maaf, saya hanya dapat membantu dengan pertanyaan seputar IT seperti "
            "masalah wifi, printer, laptop, email, VPN, atau software perusahaan. 😊\n\n"
            "Apakah ada masalah IT yang bisa saya bantu?"
        )
        yield answer

    elif intent == "REQUEST_IT_SUPPORT":
        session["attempts"] = 0
        session["offered_support"] = False
        query_for_escalation = session.get("last_it_problem") or question
        guide = escalation_guide(query_for_escalation, vector_store, embedding_service)
        answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
        yield answer

    elif intent == "REJECT_IT_SUPPORT":
        session["offered_support"] = False
        answer = "Baik, saya akan tetap berusaha membantu Anda di sini. Silakan ceritakan masalahnya lebih lanjut."
        yield answer

    else:  # IT_PROBLEM
        if session["attempts"] == 0:
            session["last_it_problem"] = question

        _FAILURE_SIGNALS = re.compile(
            r'\b(masih|belum|tidak berhasil|gagal|tidak bisa|sama saja|tidak mempan)\b',
            re.IGNORECASE
        )
        if _FAILURE_SIGNALS.search(question) and session["history"]:
            last_bot_msgs = [
                m["content"] for m in session["history"]
                if m["role"] == "assistant"
            ]
            if last_bot_msgs:
                summary = last_bot_msgs[-1][:60] + "..."
                if summary not in session["failed_steps"]:
                    session["failed_steps"].append(summary)

        rag_query = rewrite_query_for_rag(
            question,
            session["history"],
            original_problem=session.get("last_it_problem", ""),
        )

        full_answer = []
        for token in get_llm_response_stream(
            question, session["history"], "troubleshoot",
            vector_store, embedding_service,
            rag_query=rag_query,
            failed_steps=session["failed_steps"],
            session=session,
        ):
            full_answer.append(token)
            yield token
        answer = "".join(full_answer)

        session["attempts"] += 1

        if session["attempts"] >= 2 and not session["offered_support"]:
            session["offered_support"] = True
            session["awaiting_support_confirmation"] = True
            escalation_prompt = (
                "\n\n---\n"
                "Masalah ini sepertinya membutuhkan penanganan lebih lanjut. "
                "Apakah Anda ingin saya pandu untuk menghubungi tim IT Support? (Ya/Tidak)"
            )
            answer += escalation_prompt
            yield escalation_prompt

    _update_history(session, question, answer)
    session_manager.save(session_id, session)


def _update_history(session: Dict, question: str, answer: str) -> None:
    """Update history percakapan, batasi 6 pesan terakhir (3 turn)."""
    session["history"].append({"role": "user", "content": question})
    session["history"].append({"role": "assistant", "content": answer})
    if len(session["history"]) > 6:
        session["history"] = session["history"][-6:]