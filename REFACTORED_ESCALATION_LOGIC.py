"""
REFACTORED ESCALATION ROUTING LOGIC
Menggantikan semua hardcoded logic dengan dynamic LLM-based routing

File ini berisi:
1. System prompt baru untuk LLM
2. Fungsi escalation_guide_dynamic() - MENGGANTIKAN escalation_guide()
3. Helper functions untuk parsing respons LLM
4. Exception handling untuk Incident form
"""

import json
import re
import logging
from typing import Optional, Tuple, List, Dict

logger = logging.getLogger(__name__)

# =====================================================================
# SYSTEM PROMPT BARU: LLM sebagai Intelligent Form Router
# =====================================================================

_ESCALATION_ROUTER_SYSTEM_PROMPT = """\
Anda adalah AI Routing Expert untuk IT Support. Tugas Anda adalah membaca pertanyaan user 
dan memilih FORM yang paling sesuai dari daftar form yang tersedia di knowledge base kami.

INSTRUKSI KRITIS:
1. Baca dengan TELITI kolom "TRIGGER KEYWORD" dari setiap form yang disediakan.
   Kolom ini berisi daftar kata kunci yang menandakan form mana yang cocok.

2. Bandingkan kata-kata di dalam pertanyaan user dengan TRIGGER KEYWORD setiap form.
   Hitung berapa banyak kata di pertanyaan user yang muncul di TRIGGER KEYWORD.

3. Pilih form dengan jumlah keyword match tertinggi.

4. JIKA tidak ada form yang cocok (keyword match < 2 keywords), kembalikan JSON:
   {
     "form_name": "Incident",
     "link": "https://myssc.pertamina.com/dwp/app/#/itemprofile/313",
     "confidence": 0.3,
     "reasoning": "Tidak ada form yang cocok dengan pertanyaan user"
   }

5. JANGAN PERNAH ASAL PILIH. Pastikan form yang dipilih benar-benar match dengan 
   pertanyaan user berdasarkan TRIGGER KEYWORD.

OUTPUT FORMAT (WAJIB JSON yang valid):
{
  "form_name": "<nama exact form dari KB>",
  "link": "<URL dari field Link, harus dimulai dengan https://>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<penjelasan singkat mengapa form ini dipilih>"
}

CONTOH PROSES:
─────────────
User: "saya ingin melakukan peminjaman notebook untuk mitra kerja, saya harus menghubungi siapa?"

Available Forms:
1. NAMA FORM: Layanan Pekerja Baru, Konsultan, Auditor dan Mitra Kerja
   TRIGGER KEYWORD: pekerja, baru, konsultan, mitra, kerja, auditor, user, notebook, laptop
   Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/311

2. NAMA FORM: Incident (Gangguan Aplikasi & Sistem)
   TRIGGER KEYWORD: error, crash, hang, tidak bisa, error aplikasi
   Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/313

─ ANALISIS:
Kata di pertanyaan user: ["saya", "ingin", "melakukan", "peminjaman", "notebook", "untuk", "mitra", "kerja", "saya", "harus", "menghubungi", "siapa"]

Form 1 keyword matches: 
  - "notebook" ✓ (ada di TRIGGER KEYWORD)
  - "mitra" ✓ (ada di TRIGGER KEYWORD)
  - "kerja" ✓ (ada di TRIGGER KEYWORD)
  Total: 3 matches

Form 2 keyword matches:
  - Tidak ada yang match
  Total: 0 matches

─ KEPUTUSAN: Pilih Form 1 karena 3 > 0

RESPONS YANG BENAR:
{
  "form_name": "Layanan Pekerja Baru, Konsultan, Auditor dan Mitra Kerja",
  "link": "https://myssc.pertamina.com/dwp/app/#/itemprofile/311",
  "confidence": 0.95,
  "reasoning": "User mention 'peminjaman', 'notebook', 'mitra', 'kerja' - semua ada di TRIGGER KEYWORD form ini"
}

JANGAN OUTPUT TEXT SELAIN JSON. HANYA JSON.
"""

# =====================================================================
# FALLBACK: Hardcoded Incident Form (EXCEPTION SAJA)
# =====================================================================

def _get_incident_escalation_reply() -> str:
    """
    SATU-SATUNYA hardcoded form yang tetap di sistem.
    
    Alasan tetap hardcoded:
    1. Incident adalah fallback terakhir untuk SEMUA masalah IT yang tidak cocok
    2. Tidak berubah-ubah seperti form lainnya (stable)
    3. Perlu dijamin selalu available tanpa tergantung retrieval
    4. Universal untuk semua kasus "tidak ada form yang cocok"
    
    Return: Formatted escalation message dengan Incident form + link
    """
    return (
        "Mohon maaf, tidak ada panduan khusus yang cocok untuk masalah Anda. "
        "Silakan buat tiket menggunakan form berikut:\n\n"
        "📋 **NAMA FORM:** Incident (Gangguan Aplikasi & Sistem)\n\n"
        "📌 **PANDUAN TIKET:** Untuk menghubungi tim IT silahkan klik link "
        "di bawah ini dan ikuti alur yang ada pada link tersebut.\n\n"
        "🔗 **Link:** https://myssc.pertamina.com/dwp/app/#/itemprofile/313"
    )

# =====================================================================
# HELPER: Parse Respons LLM (JSON)
# =====================================================================

def _extract_form_info_from_llm_response(llm_response: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse respons JSON dari LLM untuk mengekstrak form_name dan link.
    
    Return:
        (form_name, link) - tuple dengan form name dan URL
        (None, None) - jika parsing gagal atau link tidak valid
    """
    try:
        # Bersihkan response (bisa ada leading/trailing whitespace atau markdown)
        response_clean = llm_response.strip()
        
        # Coba parse JSON
        parsed = json.loads(response_clean)
        
        form_name = parsed.get("form_name", "").strip()
        link = parsed.get("link", "").strip()
        confidence = parsed.get("confidence", 0.0)
        
        # Validasi
        if not form_name or not link:
            logger.warning("llm_response_incomplete", extra={
                "form_name": form_name,
                "link": link
            })
            return (None, None)
        
        # Validasi link (harus real URL, bukan placeholder)
        if not _is_valid_link(link):
            logger.warning("llm_response_invalid_link", extra={
                "link": link,
                "form_name": form_name
            })
            return (None, None)
        
        # Jika form adalah "Incident", gunakan fallback hardcoded
        if form_name.lower() == "incident" or "incident" in form_name.lower():
            logger.info("llm_selected_incident_fallback", extra={
                "confidence": confidence
            })
            return (None, None)  # Trigger fallback ke hardcoded Incident
        
        logger.info("llm_form_selected", extra={
            "form_name": form_name,
            "confidence": confidence,
            "link_preview": link[:50]
        })
        
        return (form_name, link)
        
    except json.JSONDecodeError as e:
        logger.error("llm_response_json_parse_failed", extra={
            "error": str(e),
            "response_preview": llm_response[:100]
        })
        return (None, None)
    except Exception as e:
        logger.error("llm_response_parse_error", extra={"error": str(e)})
        return (None, None)


def _is_valid_link(link: str) -> bool:
    """
    Check if link adalah valid URL (bukan placeholder atau invalid).
    
    Valid patterns:
    - https://...
    - http://...
    - .../.../#/...  (URL dengan hash routing)
    
    Invalid patterns:
    - [LINK_BELUM_TERSEDIA_DI_CSV]
    - [LINK_BELUM_TERSEDIA]
    - n/a, null, TBD, dll
    """
    if not link:
        return False
    
    link_lower = link.lower()
    
    # Check for placeholder patterns (invalid)
    invalid_patterns = [
        '[link_belum_tersedia',
        'not available',
        'tbd',
        'null',
        'n/a',
        'belum tersedia',
        'placeholder',
    ]
    
    for pattern in invalid_patterns:
        if pattern in link_lower:
            return False
    
    # Check if it's a real URL
    if link.startswith('http://') or link.startswith('https://') or '/#/' in link:
        return True
    
    return False

# =====================================================================
# MAIN FUNCTION: DYNAMIC ESCALATION ROUTING VIA LLM
# =====================================================================

def escalation_guide_dynamic(
    query_issue: str,
    vector_store,
    embedding_service,
) -> str:
    """
    FULLY DYNAMIC escalation guide routing menggunakan LLM.
    
    Flow:
    1. Retrieve top-K ESCALATION chunks dari vector store
    2. Pass chunks + query ke LLM dengan system prompt "route form terbaik"
    3. LLM returns JSON dengan form_name + link pilihan
    4. Extract dan validate
    5. Jika gagal, fallback ke hardcoded Incident form
    
    Args:
        query_issue: User's IT support request
        vector_store: Vector store untuk retrieval
        embedding_service: Embedding service untuk query encoding
    
    Returns:
        Formatted escalation guide dengan FORM + Link, atau Incident fallback
    """
    if not query_issue.strip():
        return _get_incident_escalation_reply()
    
    try:
        t0 = time.time()
        
        # STEP 1: Retrieve top-K ESCALATION chunks dari vector store
        # Ambil lebih banyak (top_k=15) agar LLM punya pilihan yang beragam
        all_escalation_chunks = retrieve_context(
            query_issue, vector_store, embedding_service,
            doc_type="ESCALATION", top_k=15
        )
        
        if not all_escalation_chunks:
            logger.warning("escalation_retrieve_no_results", extra={
                "query": query_issue[:60]
            })
            return _get_incident_escalation_reply()
        
        logger.debug("escalation_chunks_retrieved", extra={
            "count": len(all_escalation_chunks),
            "top_score": round(all_escalation_chunks[0].get("score", 0), 3)
        })
        
        # STEP 2: Prepare available forms untuk LLM
        # Format: gabungkan semua chunks dengan penanda yang jelas
        available_forms_text = "\n\n" + "="*60 + "\n\n".join(
            [f["content"] for f in all_escalation_chunks]
        )
        
        # STEP 3: Buat prompt untuk LLM (user message)
        user_message = (
            f"Berikut adalah pertanyaan dari user IT Support:\n"
            f"\n---\n"
            f"{query_issue}\n"
            f"---\n\n"
            f"Berikut adalah daftar form yang tersedia di knowledge base kami:\n"
            f"{available_forms_text}\n\n"
            f"Pilih form yang paling cocok berdasarkan TRIGGER KEYWORD. "
            f"Output hanya JSON, tanpa penjelasan lain."
        )
        
        # STEP 4: Call LLM dengan system prompt router
        llm_response = generate_llm(
            messages=[
                {"role": "system", "content": _ESCALATION_ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            config_name="escalation_routing",  # Low temp untuk deterministic
        )
        
        logger.debug("llm_escalation_response", extra={
            "response_preview": llm_response[:150]
        })
        
        # STEP 5: Extract form_name + link dari respons LLM
        form_name, link = _extract_form_info_from_llm_response(llm_response)
        
        if form_name and link:
            # SUCCESS: LLM found a matching form
            elapsed = int((time.time() - t0) * 1000)
            logger.info("escalation_guide_dynamic_success", extra={
                "form_name": form_name,
                "elapsed_ms": elapsed,
                "method": "llm_routing"
            })
            
            return (
                f"Untuk masalah ini, silakan gunakan form berikut:\n\n"
                f"📋 **NAMA FORM:** {form_name}\n\n"
                f"🔗 **Link:** {link}"
            )
        else:
            # FALLBACK: LLM pilih Incident atau tidak bisa parse
            logger.warning("escalation_guide_llm_no_match", extra={
                "query": query_issue[:80],
                "form_name": form_name,
                "link": link
            })
            return _get_incident_escalation_reply()
        
    except Exception as e:
        logger.error("escalation_guide_dynamic_error", extra={
            "error": str(e),
            "query": query_issue[:60]
        })
        # Safety fallback
        return _get_incident_escalation_reply()

# =====================================================================
# UPDATE: LLM CONFIG
# =====================================================================

# Tambahkan ke LLM_SETTINGS dictionary yang sudah ada di chat_service.py:

LLM_SETTINGS_UPDATE = {
    # Untuk escalation routing: deterministic, fokus pada extraction
    "escalation_routing": {
        "temperature": 0.0,  # Zero randomness - harus consistent
        "top_p": 0.85,
        "top_k": 10,
        "repeat_penalty": 1.2,
        "num_predict": 500,  # JSON response tidak terlalu panjang
        "mirostat": 0,
    },
}

# =====================================================================
# IMPORTS YANG DIPERLUKAN DI CHAT_SERVICE.PY
# =====================================================================

"""
Tambahkan ke bagian imports di chat_service.py:

import time
from apps.rag.services.retrieval import retrieve_context
"""

