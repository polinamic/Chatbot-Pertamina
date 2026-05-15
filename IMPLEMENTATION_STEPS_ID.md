# 📋 PANDUAN IMPLEMENTATION: REFACTORING HARDCODED KE DYNAMIC

## 🎯 TUJUAN
Menghapus semua hardcoded logic dari `chat_service.py` dan menggantikannya dengan dynamic LLM-based routing.

---

## 🗑️ STEP 1: HAPUS KODE HARDCODED (SECTION-BY-SECTION)

### A. Hapus Dictionary `CATEGORY_FORMS` (Lines ~1200-1420)

**Lokasi:** Cari bagian komentar `# PHASE 1: CATEGORY-AWARE FORM MAPPING` hingga sebelum `def escalation_guide()`

**Kode yang dihapus (SEMUA):**
```python
# =====================================================================
# PHASE 1: CATEGORY-AWARE FORM MAPPING
# =====================================================================
# ... (komentar panjang tentang CATEGORY_FORMS)

CATEGORY_FORMS = {
    "access_control": [...],
    "approval": [...],
    "audio": [...],
    # ... (semua kategori + form lists)
}
```

**Alasan:** Mapping ini 100% hardcoded. Dengan dynamic LLM routing, LLM akan langsung pilih form dari retrieval results tanpa perlu kategori intermediate.

---

### B. Hapus Fungsi `_find_escalation_by_keywords()` (Lines ~1475-1650)

**Kode yang dihapus (SEMUA):**
```python
def _find_escalation_by_keywords(query: str, category_forms: List[str] = None) -> str:
    """
    Find ESCALATION form by matching query keywords dengan TRIGGER_KEYWORD field.
    
    PERBAIKAN LENGKAP (v3):
    ...
    """
    # ~175 baris kode keyword matching manual
    from apps.rag.models import DocumentChunk
    import re
    
    query_lower = query.lower()
    keywords = re.findall(r'\b\w+\b', query_lower)
    
    # ... (semua logika keyword matching)
    
    return best_match if best_match else ""
```

**Alasan:** Fungsi ini melakukan keyword matching manual yang bisa fail. LLM sekarang akan handle ini dengan semantik yang lebih baik.

---

### C. Hapus Fungsi `detect_problem_category()` (Lines ~1660-1830+)

**Kode yang dihapus (SEMUA):**
```python
def detect_problem_category(query: str) -> str:
    """
    Deteksi kategori masalah dari query user.
    
    PERBAIKAN LENGKAP:
    ...
    """
    q = query.lower()
    
    # ── PALING SPESIFIK — cek dulu ──────────────────────────
    
    if any(w in q for w in ['handphone', 'hp perusahaan', ...]):
        return "handset"
    
    # ... (~150+ baris if-elif-else checks)
    
    return "general_it"
```

**Alasan:** Seluruh fungsi adalah hardcoded keyword matching. Dynamic routing tidak butuh kategori intermediate — langsung ke LLM.

---

### D. Hapus Helper Functions untuk Kategori (Lines ~1770-1880)

**Fungsi yang dihapus:**
1. `get_ticket_process()` - Hardcoded tiket process per kategori
2. `get_contact_info()` - Hardcoded kontak per kategori
3. `get_required_info()` - Hardcoded required info per kategori

**Contoh (hapus semua):**
```python
def get_ticket_process(category: str) -> str:
    """
    Dapatkan informasi cara membuat tiket melalui portal IT Support.
    Jika tidak ada detil kategori, gunakan alur umum.
    """
    ticket_processes = {
        "access_control": "1. Masuk ke portal IT Support...",
        "vpn_access": "1. Masuk ke portal IT Support...",
        # ... (30+ kategori hardcoded)
    }
    return ticket_processes.get(category, ticket_processes["general_it"])

def get_contact_info(category: str) -> str:
    """Informasi kontak berdasarkan kategori"""
    contacts = {
        "access_control": "ext. 1234 atau email: access@pertamina.com",
        # ... (hardcoded per kategori)
    }
    return contacts.get(category, "ext. 0000 atau portal helpdesk...")

def get_required_info(category: str) -> str:
    """Informasi yang dibutuhkan untuk eskalasi"""
    info_mapping = {
        "access_control": "nomor kartu akses, lokasi, waktu kejadian",
        # ... (hardcoded per kategori)
    }
    return info_mapping.get(category, "...")
```

**Alasan:** Ini semua metadata yang LLM bisa extract dari KB chunks jika diperlukan. Tidak perlu hardcode.

---

### E. SIMPLIFIKASI: Intent Detection Patterns (Optional, tapi recommended)

**Kode yang bisa disederhanakan:**
```python
# SEBELUM: _SERVICE_ORDER_PATTERNS sangat kompleks
_SERVICE_ORDER_PATTERNS = re.compile(
    r'(?:'
    r'(?:mau\s+|ingin\s+|minta\s+|butuh\s+|perlu\s+)?(?:pesan|order|pinjam|peminjaman)\s+\w+'
    r'|pasang\s+(?:wifi|wi-fi|cctv|...)'
    r'|\bpengadaan\b'
    r'|\b(?:ajukan|pengajuan)\s+(?:perangkat|layanan|akses|...)'
    r')',
    re.IGNORECASE,
)

# SESUDAH: Simpel saja
_SERVICE_ORDER_PATTERNS = re.compile(
    r'\b(pesan|order|pinjam|peminjaman|pasang|pengadaan|ajukan|pengajuan)\b',
    re.IGNORECASE,
)
```

**Alasan:** Intent detection masih perlu regex (Layer 1 untuk kecepatan), tapi tidak perlu sedetail sebelumnya. Dynamic routing handle edge cases.

---

## ✅ STEP 2: TAMBAHKAN KODE BARU

### A. Tambahkan LLM Config `escalation_routing` 

**Lokasi:** Di dalam `LLM_SETTINGS` dictionary (around line 150-200)

**Kode yang ditambahkan:**
```python
LLM_SETTINGS: Dict[str, Dict] = {
    # ... (existing configs)
    
    # NEW: Untuk escalation routing - deterministic + focused
    "escalation_routing": {
        "temperature": 0.0,  # Zero randomness untuk form selection
        "top_p": 0.85,
        "top_k": 10,
        "repeat_penalty": 1.2,
        "num_predict": 500,  # JSON response tidak terlalu panjang
        "mirostat": 0,
    },
}
```

---

### B. Tambahkan System Prompt Baru

**Lokasi:** Di bagian "LLM RESPONSE" atau "SYSTEM PROMPTS" (around line 1800+)

**Kode yang ditambahkan (paste dari REFACTORED_ESCALATION_LOGIC.py):**
```python
_ESCALATION_ROUTER_SYSTEM_PROMPT = """\
Anda adalah AI Routing Expert untuk IT Support. Tugas Anda adalah membaca pertanyaan user 
dan memilih FORM yang paling sesuai dari daftar form yang tersedia di knowledge base kami.

INSTRUKSI KRITIS:
1. Baca dengan TELITI kolom "TRIGGER KEYWORD" dari setiap form yang disediakan.
...
[FULL PROMPT dari REFACTORED_ESCALATION_LOGIC.py]
"""
```

---

### C. Tambahkan Helper Functions

**Lokasi:** Sebelum `def escalation_guide_dynamic()` (bisa di tempat fungsi utility lainnya)

**Kode yang ditambahkan (copy-paste dari REFACTORED_ESCALATION_LOGIC.py):**
```python
def _get_incident_escalation_reply() -> str:
    """SATU-SATUNYA hardcoded form yang tetap..."""
    return (
        "Mohon maaf, tidak ada panduan khusus yang cocok untuk masalah Anda. "
        "Silakan buat tiket menggunakan form berikut:\n\n"
        "📋 **NAMA FORM:** Incident (Gangguan Aplikasi & Sistem)\n\n"
        "🔗 **Link:** https://myssc.pertamina.com/dwp/app/#/itemprofile/313"
    )

def _extract_form_info_from_llm_response(llm_response: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse respons JSON dari LLM untuk mengekstrak form_name dan link..."""
    # ... (full function dari REFACTORED_ESCALATION_LOGIC.py)

def _is_valid_link(link: str) -> bool:
    """Check if link adalah valid URL..."""
    # ... (full function dari REFACTORED_ESCALATION_LOGIC.py)
```

---

### D. Tambahkan Fungsi Utama: `escalation_guide_dynamic()`

**Lokasi:** Menggantikan posisi `escalation_guide()` (around line 1363)

**Kode yang ditambahkan (copy-paste dari REFACTORED_ESCALATION_LOGIC.py):**
```python
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
    ...
    """
    # ... (full function dari REFACTORED_ESCALATION_LOGIC.py)
```

---

## 🔄 STEP 3: UPDATE FUNCTION CALLS

### A. Di `_process_chat_sync()` dan `_process_chat_stream()`

**Cari:**
```python
elif intent == "SERVICE_ORDER":
    # SERVICE_ORDER: skip alur RAG troubleshoot, langsung cari form pengadaan yang relevan
    # via escalation_guide. 
    logger.info("intent_service_order", extra={"session_id": session_id, "question": question[:80]})
    guide = escalation_guide(question, vector_store, embedding_service)  # ← GANTI INI
    answer = (
        "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
        "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
        f"{guide}"
    )
```

**Ubah menjadi:**
```python
elif intent == "SERVICE_ORDER":
    logger.info("intent_service_order", extra={"session_id": session_id, "question": question[:80]})
    guide = escalation_guide_dynamic(question, vector_store, embedding_service)  # ← GANTI
    answer = (
        "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
        "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
        f"{guide}"
    )
```

### B. Di `_handle_escalation_confirmation()`

**Cari:**
```python
elif confirmation is False:  # User menjawab "Belum/Tidak/Gagal"
    session["awaiting_support_confirmation"] = False
    # Gunakan _INCIDENT_ESCALATION_REPLY (hardcoded) — konsisten untuk semua kasus troubleshoot
    # yang belum terselesaikan, sesuai alur Incident resmi perusahaan.
    answer = _INCIDENT_ESCALATION_REPLY
```

**Ubah menjadi:**
```python
elif confirmation is False:  # User menjawab "Belum/Tidak/Gagal"
    session["awaiting_support_confirmation"] = False
    # Gunakan _get_incident_escalation_reply() - hardcoded exception untuk Incident
    answer = _get_incident_escalation_reply()  # ← GANTI INI
```

### C. Di `REQUEST_IT_SUPPORT` intent

**Cari:**
```python
elif intent == "REQUEST_IT_SUPPORT":
    guide = escalation_guide(session.get("last_it_problem") or question, vector_store, embedding_service)  # ← GANTI
    answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
```

**Ubah menjadi:**
```python
elif intent == "REQUEST_IT_SUPPORT":
    guide = escalation_guide_dynamic(session.get("last_it_problem") or question, vector_store, embedding_service)  # ← GANTI
    answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
```

---

## 🧪 STEP 4: TESTING

### Test Case 1: Service Order Query (Seperti user Anda sebelumnya)
```
Query: "saya ingin melakukan peminjaman notebook untuk mitra kerja"
Expected Flow:
  1. detect_intent() → SERVICE_ORDER (regex catch "peminjaman")
  2. escalation_guide_dynamic() → retrieve top-K ESCALATION chunks
  3. LLM read chunks + TRIGGER KEYWORD
  4. LLM match "notebook", "mitra", "kerja" ke form "Layanan Pekerja Baru..."
  5. Extract link → https://myssc.pertamina.com/dwp/app/#/itemprofile/311
  6. Return: FORM + Link ✅
```

### Test Case 2: Unknown/Generic Query
```
Query: "ada masalah yang aneh di sistem saya"
Expected Flow:
  1. detect_intent() → IT_PROBLEM
  2. escalation_guide_dynamic() → retrieve chunks
  3. LLM tidak bisa match ke form specific
  4. Return Incident form fallback ✅
```

---

## ⚠️ IMPORTANT NOTES

### 1. **Jangan Hapus:**
- `_INCIDENT_ESCALATION_REPLY` variable (ganti dengan `_get_incident_escalation_reply()`)
- `_OUT_OF_SCOPE_REPLY` 
- `_HAPPY_TO_HELP_REPLY`
- `_SOLVED_CONFIRMATION_PROMPT`

### 2. **Pastikan Tetap Ada:**
- Import statements di atas
- Session manager
- Intent detection logic (Layer 1-3)
- RAG retrieval functions
- LLM generation functions

### 3. **Tes Sebelum Deploy:**
```bash
# 1. Check syntax errors
python manage.py check

# 2. Run existing tests
python manage.py test

# 3. Manual test queries di browser
# - "peminjaman notebook untuk mitra kerja"
# - "wifi tidak bisa" 
# - "printer error"
```

---

## 📊 Summary: Lines of Code Changes

| Action | Lines | Dari | Ke |
|--------|-------|------|-----|
| Delete | ~600 | `CATEGORY_FORMS` + `detect_problem_category()` + `_find_escalation_by_keywords()` | - |
| Delete | ~150 | `get_ticket_process()` + `get_contact_info()` + `get_required_info()` | - |
| Add | ~350 | - | New `escalation_guide_dynamic()` + helpers + system prompt |
| Update | ~10 | Function calls | Replace `escalation_guide()` → `escalation_guide_dynamic()` |
| **Net** | **~-400** | Hardcoded logic | Dynamic LLM logic ✅ |

---

## 🎉 Hasil Akhir

**Sebelum (Hardcoded):**
- 600+ lines kategori + keyword matching
- Perlu edit code setiap ada query pattern baru
- Brittle & error-prone
- Maintenance tinggi

**Sesudah (Dynamic):**
- ~350 lines pure routing logic
- Auto-pick form dari KB
- Robust & scalable
- Maintenance rendah
- LLM reasoning handles edge cases ✅

