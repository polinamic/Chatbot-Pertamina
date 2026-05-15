# ✅ QUICK REFERENCE: IMPLEMENTATION CHECKLIST

## 📋 PRE-IMPLEMENTATION CHECKLIST

- [ ] Backup file `chat_service.py` → `chat_service.py.backup`
- [ ] Buka file `chat_service.py` dalam editor
- [ ] Siapkan file `REFACTORED_ESCALATION_LOGIC.py` untuk copy-paste
- [ ] Pastikan sudah understand alur baru (baca REFACTORING_GUIDE_ID.md)

---

## 🗑️ DELETION CHECKLIST

### Delete Section 1: `CATEGORY_FORMS` Dictionary
- [ ] Find: `# PHASE 1: CATEGORY-AWARE FORM MAPPING` (around line 1200)
- [ ] Find end: Before `def escalation_guide()`
- [ ] **Select all lines** (approximately 200-250 lines)
- [ ] **Press DELETE or CTRL+X**
- [ ] Verify: File should jump from line ~1200 directly to next function

```
✓ Deleted lines like:
  CATEGORY_FORMS = {
      "access_control": [...],
      "audio": [...],
      ... (30+ categories)
  }
```

---

### Delete Section 2: `_find_escalation_by_keywords()` Function
- [ ] Find: `def _find_escalation_by_keywords(query: str, category_forms: List[str] = None) -> str:`
- [ ] Find end: `return best_match if best_match else ""`
- [ ] **Select entire function** (~175 lines)
- [ ] **Press DELETE or CTRL+X**
- [ ] Verify: No leftover function definition

```
✓ Deleted:
  def _find_escalation_by_keywords(query: str, ...):
      ...
      return best_match if best_match else ""
```

---

### Delete Section 3: `detect_problem_category()` Function
- [ ] Find: `def detect_problem_category(query: str) -> str:` (around line 1660)
- [ ] Find end: `return "general_it"`
- [ ] **Select entire function** (~150+ lines)
- [ ] **Press DELETE or CTRL+X**
- [ ] Verify: File structure intact

```
✓ Deleted:
  def detect_problem_category(query: str) -> str:
      q = query.lower()
      if any(w in q for w in ['handphone', ...]):
          return "handset"
      ...
      return "general_it"
```

---

### Delete Section 4: Helper Functions (Optional tapi Recommended)
- [ ] Find: `def get_ticket_process(category: str) -> str:` (around line 1000)
- [ ] Delete entire function (~20 lines)
- [ ] Find: `def get_contact_info(category: str) -> str:`
- [ ] Delete entire function (~15 lines)
- [ ] Find: `def get_required_info(category: str) -> str:`
- [ ] Delete entire function (~15 lines)
- [ ] Find: `def get_required_info(category: str) -> str:`

```
✓ Deleted:
  get_ticket_process()
  get_contact_info()
  get_required_info()
```

---

## ➕ ADDITION CHECKLIST

### Add Section 1: LLM Config untuk Escalation Routing
- [ ] Find: `LLM_SETTINGS: Dict[str, Dict] = {` (around line 140)
- [ ] Go to end of dictionary (before closing `}`)
- [ ] Add comma ke last entry jika belum ada
- [ ] **PASTE kode dibawah:**

```python
    # NEW: Untuk escalation routing - deterministic + focused
    "escalation_routing": {
        "temperature": 0.0,  # Zero randomness untuk form selection
        "top_p": 0.85,
        "top_k": 10,
        "repeat_penalty": 1.2,
        "num_predict": 500,  # JSON response tidak terlalu panjang
        "mirostat": 0,
    },
```

- [ ] Verify: Syntax valid (comma di tempat yang benar)

---

### Add Section 2: System Prompt Baru
- [ ] Find: Bagian "LLM RESPONSE" atau "SYSTEM PROMPTS" (around line 1800+)
- [ ] Find tempat yang cocok (sebelum system prompts lainnya)
- [ ] **PASTE FULL dari file REFACTORED_ESCALATION_LOGIC.py:**

```python
_ESCALATION_ROUTER_SYSTEM_PROMPT = """\
Anda adalah AI Routing Expert untuk IT Support. ...
[FULL TEXT dari REFACTORED_ESCALATION_LOGIC.py]
"""
```

- [ ] Verify: String lengkap (mulai `"""` sampai `"""`)

---

### Add Section 3: Helper Functions
- [ ] Find: Lokasi di sekitar utility functions (bisa sebelum `escalation_guide()`)
- [ ] **PASTE ke-3 function dari REFACTORED_ESCALATION_LOGIC.py:**

```python
def _get_incident_escalation_reply() -> str:
    """SATU-SATUNYA hardcoded form..."""
    # ... (copy full function)

def _extract_form_info_from_llm_response(llm_response: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse respons JSON dari LLM..."""
    # ... (copy full function)

def _is_valid_link(link: str) -> bool:
    """Check if link adalah valid URL..."""
    # ... (copy full function)
```

- [ ] Verify: Semua 3 functions ada

---

### Add Section 4: Fungsi Utama `escalation_guide_dynamic()`
- [ ] Find: `def escalation_guide(query_issue: str, vector_store, embedding_service) -> str:` (original old function)
- [ ] **HAPUS ATAU RENAME** fungsi lama ke `escalation_guide_old()` (untuk backup)
- [ ] **PASTE** fungsi baru dari REFACTORED_ESCALATION_LOGIC.py:

```python
def escalation_guide_dynamic(
    query_issue: str,
    vector_store,
    embedding_service,
) -> str:
    """
    FULLY DYNAMIC escalation guide routing menggunakan LLM.
    ...
    """
    # ... (copy full function dari REFACTORED_ESCALATION_LOGIC.py)
```

- [ ] Verify: Fungsi lengkap dengan `try-except` dan logging

---

## 🔄 FUNCTION CALL UPDATE CHECKLIST

### Update 1: Di `_process_chat_sync()` function
- [ ] Find: `elif intent == "SERVICE_ORDER":`
- [ ] Find line: `guide = escalation_guide(question, vector_store, embedding_service)`
- [ ] **GANTI dengan:** `guide = escalation_guide_dynamic(question, vector_store, embedding_service)`
- [ ] Find: `elif intent == "REQUEST_IT_SUPPORT":`
- [ ] Find line: `guide = escalation_guide(...)`
- [ ] **GANTI dengan:** `guide = escalation_guide_dynamic(...)`

```diff
- guide = escalation_guide(question, vector_store, embedding_service)
+ guide = escalation_guide_dynamic(question, vector_store, embedding_service)
```

- [ ] Verify: Kedua tempat sudah di-update

---

### Update 2: Di `_process_chat_stream()` function
- [ ] Find: `elif intent == "SERVICE_ORDER":`
- [ ] Find line: `guide = escalation_guide(question, vector_store, embedding_service)`
- [ ] **GANTI dengan:** `guide = escalation_guide_dynamic(question, vector_store, embedding_service)`
- [ ] Find: `elif intent == "REQUEST_IT_SUPPORT":`
- [ ] Find line: `guide = escalation_guide(...)`
- [ ] **GANTI dengan:** `guide = escalation_guide_dynamic(...)`

```diff
- guide = escalation_guide(question, vector_store, embedding_service)
+ guide = escalation_guide_dynamic(question, vector_store, embedding_service)
```

- [ ] Verify: Kedua tempat sudah di-update

---

### Update 3: Di `_handle_escalation_confirmation()` function
- [ ] Find: `elif confirmation is False:  # User menjawab "Belum/Tidak/Gagal"`
- [ ] Find line: `answer = _INCIDENT_ESCALATION_REPLY`
- [ ] **GANTI dengan:** `answer = _get_incident_escalation_reply()`

```diff
- answer = _INCIDENT_ESCALATION_REPLY
+ answer = _get_incident_escalation_reply()
```

- [ ] Verify: Updated

---

## 🧪 TESTING CHECKLIST

### Syntax Check
- [ ] Save file: `CTRL+S`
- [ ] Run: `python manage.py check` (di terminal)
- [ ] Verify: No syntax errors

```bash
# Expected output:
# System check identified no issues (0 silenced).
```

---

### Unit Testing
- [ ] Run: `python manage.py test` (jika ada test suite)
- [ ] Verify: Tidak ada test yang break

---

### Manual Functional Testing

#### Test 1: Service Order Query
- [ ] Start server: `python manage.py runserver`
- [ ] Open browser: `http://127.0.0.1:8000`
- [ ] Send query: **"peminjaman notebook untuk mitra kerja"**
- [ ] Expected response: Form "Layanan Pekerja Baru..." dengan link `/311`
- [ ] ✓ Pass / ❌ Fail

#### Test 2: Generic/Unknown Query
- [ ] Send query: **"ada error aneh di sistem"**
- [ ] Expected response: Incident form dengan link `/313`
- [ ] ✓ Pass / ❌ Fail

#### Test 3: Specific Technical Query
- [ ] Send query: **"wifi tidak bisa konek"**
- [ ] Expected response: Network-related form (bisa "Wifi Access" atau similar)
- [ ] ✓ Pass / ❌ Fail

#### Test 4: Printer Query
- [ ] Send query: **"printer tidak bisa print"**
- [ ] Expected response: Printer-related form
- [ ] ✓ Pass / ❌ Fail

---

## 🐛 DEBUGGING CHECKLIST (Jika Ada Error)

### Error: `NameError: name 'escalation_guide' is not defined`
- [ ] Check: Apakah fungsi `escalation_guide_dynamic()` sudah ditambahkan?
- [ ] Check: Apakah function name di call site sudah di-update?

### Error: `KeyError: 'escalation_routing'` di `get_llm_config()`
- [ ] Check: Apakah LLM config "escalation_routing" sudah ditambahkan ke `LLM_SETTINGS`?

### Error: JSON parse error di LLM response
- [ ] Check: Apakah system prompt sudah ditambahkan?
- [ ] Check: Apakah LLM temperature = 0.0 (untuk deterministic)?
- [ ] Fix: Tambah timeout & error handling di `_extract_form_info_from_llm_response()`

### Error: Always returning Incident form
- [ ] Check: Apakah retrieval bekerja? (Test `retrieve_context()` directly)
- [ ] Check: Apakah LLM response is valid JSON?
- [ ] Debug: Add logging di LLM call untuk lihat response apa yang diterima

---

## 📝 COMPLETION CHECKLIST

- [ ] Semua kode hardcoded sudah dihapus
- [ ] Semua kode baru sudah ditambahkan
- [ ] Semua function calls sudah di-update
- [ ] Syntax check passed
- [ ] Unit tests passed
- [ ] Manual testing passed semua 4 test cases
- [ ] Logging berfungsi (check server logs)
- [ ] Ready untuk production deployment ✅

---

## 📞 QUICK HELP

### Jika mau rollback:
```bash
cp chat_service.py.backup chat_service.py
# atau gunakan git revert
```

### Jika mau lihat differences:
```bash
diff -u chat_service.py.backup chat_service.py | less
```

### Jika perlu debug LLM response:
```python
# Add temporary logging di escalation_guide_dynamic():
logger.info("llm_response_raw", extra={"response": llm_response})
```

---

