# 📊 REFACTORING VISUAL OVERVIEW

## ARCHITECTURE TRANSFORMATION

### SEBELUM: Hardcoded Architecture ❌

```
┌─────────────────────────────────────────────────────────────────┐
│                   CHAT_SERVICE.PY (MONOLITHIC)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  USER QUERY                                                       │
│    ↓                                                              │
│  Intent Detection (simple regex)                                 │
│    ↓                                                              │
│  ┌─────────────────────────────────────────────────┐             │
│  │  detect_problem_category() [200+ lines]        │             │
│  │  ❌ MASSIVE if-else chain:                      │             │
│  │    - handphone → "handset"                      │             │
│  │    - simcard → "simcard"                        │             │
│  │    - laptop → "hardware"                        │             │
│  │    - ... 40+ more categories                    │             │
│  └─────────────────────────────────────────────────┘             │
│    ↓                                                              │
│  ┌─────────────────────────────────────────────────┐             │
│  │  CATEGORY_FORMS = {...} [MASSIVE DICT]         │             │
│  │  ❌ Maps category → form names:                 │             │
│  │    "hardware": ["Laptop", "Desktop", ...]      │             │
│  │    "network": ["WiFi", "Firewall", ...]        │             │
│  │    ... 40+ categories × 5-10 forms each = 300+ │             │
│  │    hardcoded form names                         │             │
│  └─────────────────────────────────────────────────┘             │
│    ↓                                                              │
│  ┌─────────────────────────────────────────────────┐             │
│  │  get_ticket_process(category) [150+ lines]     │             │
│  │  ❌ Hardcoded ticket creation steps per cat    │             │
│  │     (10+ categories × 10-15 steps each)        │             │
│  └─────────────────────────────────────────────────┘             │
│    ↓                                                              │
│  ┌─────────────────────────────────────────────────┐             │
│  │  get_contact_info(category)                     │             │
│  │  get_required_info(category)                    │             │
│  │  ❌ More hardcoded dicts                        │             │
│  └─────────────────────────────────────────────────┘             │
│    ↓                                                              │
│  Response to User (using hardcoded data)                         │
│                                                                   │
│  ❌ PROBLEMS:                                                    │
│  - 800+ baris hardcoded logic                                    │
│  - Sulit scale (tambah kategori = edit code)                     │
│  - Sulit maintain (logic tersebar di 6+ fungsi)                  │
│  - Sulit test (massive if-else chains)                           │
│  - Sulit update link (hardcoded URL, perlu deploy)              │
│  - False-match kategori sering terjadi                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### SESUDAH: Database-Driven Architecture ✅

```
┌─────────────────────────────────────────────────────────────────┐
│                 CHAT_SERVICE.PY (CLEAN & SIMPLE)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  USER QUERY                                                       │
│    ↓                                                              │
│  Intent Detection (simple regex) ← SAME AS BEFORE                │
│    ↓                                                              │
│  ┌─────────────────────────────────────────────────┐             │
│  │  escalation_guide(query, vector_store,          │             │
│  │                   embedding_service,            │             │
│  │                   doc_type="ORDER_LINK" |       │             │
│  │                            "INCIDENT_LINK")     │             │
│  │                                                  │             │
│  │  ✅ NEW: Single, clean function (50 lines)      │             │
│  │    1. Vector search filtered by doc_type        │             │
│  │    2. Extract NAMA FORM & Link from DB          │             │
│  │    3. Return form + link to user                │             │
│  │    4. Fallback to IT Portal if no match         │             │
│  └─────────────────────────────────────────────────┘             │
│         ↓                       ↓                                 │
│    ┌────────────────┐    ┌──────────────────┐                   │
│    │ Vector Store   │    │  Embedding       │                   │
│    │ (index vectors │    │  Service         │                   │
│    │  of chunks)    │    │  (encode query)  │                   │
│    └────────────────┘    └──────────────────┘                   │
│         ↑                       ↑                                 │
│    ┌─────────────────────────────────────────────┐               │
│    │         DATABASE (Django ORM)                │               │
│    ├─────────────────────────────────────────────┤               │
│    │  Document.objects.filter(                   │               │
│    │    doc_type="ORDER_LINK" |                  │               │
│    │            "INCIDENT_LINK"                  │               │
│    │  )                                           │               │
│    ├─────────────────────────────────────────────┤               │
│    │  Chunks:                                    │               │
│    │  - NAMA FORM: Handset...                   │               │
│    │    TRIGGER KEYWORD: hp, mobile, order...   │               │
│    │    PANDUAN TIKET: ...                       │               │
│    │    Link: https://.../#/itemprofile/101      │               │
│    │                                              │               │
│    │  - NAMA FORM: Incident...                  │               │
│    │    TRIGGER KEYWORD: error, crash...        │               │
│    │    PANDUAN TIKET: ...                       │               │
│    │    Link: https://.../#/itemprofile/200      │               │
│    └─────────────────────────────────────────────┘               │
│    ↑                                                              │
│    └────── Can be updated via Dashboard (NO CODE CHANGE!)        │
│                                                                   │
│  Response to User (using dynamic DB data)                        │
│                                                                   │
│  ✅ ADVANTAGES:                                                  │
│  - Hanya ~100 baris new code (50 lines escalation_guide)        │
│  - Easy scale (tambah KB via dashboard)                         │
│  - Easy maintain (single clean function)                        │
│  - Easy test (data-driven, mockable)                            │
│  - Easy update link (edit in DB, instant)                       │
│  - Smart semantic matching (vector search)                      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## FLOW DIAGRAM: USER JOURNEY

### Journey 1: Service Order (Pengadaan Laptop)

```
╔════════════════════════════════════════════════════════════════════╗
║  User: "Saya butuh laptop baru untuk tim saya"                    ║
╚════════════════════════════════════════════════════════════════════╝
           ↓
        Intent Detection
           ↓
    ┌──────────────────┐
    │ Is it SERVICE_   │
    │ ORDER pattern?   │
    │ (pesan, order,   │
    │  pengadaan, dll) │
    └────────┬─────────┘
             ↓ YES
    ╔═════════════════════════════════════════════════════════════════╗
    ║  routing: elif intent == "SERVICE_ORDER"                       ║
    ╚═════════════════════════════════════════════════════════════════╝
             ↓
    ╔═════════════════════════════════════════════════════════════════╗
    ║  escalation_guide(query,                                       ║
    ║      vector_store,                                             ║
    ║      embedding_service,                                        ║
    ║      doc_type="ORDER_LINK")  ← NEW PARAMETER                   ║
    ╚═════════════════════════════════════════════════════════════════╝
             ↓
    ┌────────────────────────────────────────────────────────────────┐
    │  Vector Search:                                                 │
    │  1. Encode "Saya butuh laptop..." into embedding vector        │
    │  2. Find nearest chunks WHERE document.doc_type == "ORDER_LINK"│
    │  3. Get top_k=1 result (best match)                            │
    └────────────┬──────────────────────────────────────────────────┘
                 ↓
    ┌────────────────────────────────────────────────────────────────┐
    │  Database Hit:                                                  │
    │  Found chunk with:                                             │
    │  - NAMA FORM: "Desktop (PC, Laptop, Peripheral)"              │
    │  - Link: "https://myssc.pertamina.com/.../#/itemprofile/102"   │
    └────────────┬──────────────────────────────────────────────────┘
                 ↓
    ┌────────────────────────────────────────────────────────────────┐
    │  Validation:                                                    │
    │  _is_valid_link(link) → TRUE (valid URL)                       │
    └────────────┬──────────────────────────────────────────────────┘
                 ↓
╔════════════════════════════════════════════════════════════════════╗
║  Bot Response:                                                    ║
║  "Baik! Permintaan Anda terdeteksi sebagai **Service Order**.     ║
║                                                                    ║
║  Untuk menangani masalah ini, silakan gunakan form berikut:       ║
║                                                                    ║
║  📋 **NAMA FORM:** Desktop (PC, Laptop, Peripheral)               ║
║                                                                    ║
║  🔗 **Link:** https://myssc.pertamina.com/.../#/itemprofile/102"  ║
╚════════════════════════════════════════════════════════════════════╝
             ↓
    ┌────────────────────────┐
    │  User clicks link ✅   │
    │  Langsung ke form      │
    │  (NO MORE HARDCODED!)  │
    └────────────────────────┘
```

---

### Journey 2: Troubleshooting Failed → Escalation

```
╔════════════════════════════════════════════════════════════════════╗
║  User Turn 1: "WiFi saya tidak bisa konek"                        ║
╚════════════════════════════════════════════════════════════════════╝
           ↓
    Intent: IT_PROBLEM
           ↓
    ┌──────────────────┐
    │  RAG Retrieval   │
    │  (TROUBLESHOOT   │
    │   doc_type)      │
    └────────┬─────────┘
             ↓
╔════════════════════════════════════════════════════════════════════╗
║  Bot: "Langkah 1: Restart router...                               ║
║        Langkah 2: Check WiFi connection...                        ║
║        ...                                                         ║
║                                                                    ║
║  **Apakah masalah Anda sudah terselesaikan?** (Sudah / Belum)     ║
╚════════════════════════════════════════════════════════════════════╝
           ↓
╔════════════════════════════════════════════════════════════════════╗
║  User Turn 2: "Belum juga, masih not working"                     ║
╚════════════════════════════════════════════════════════════════════╝
           ↓
    detect_confirmation("Belum") → FALSE
           ↓
    ┌──────────────────────────────────┐
    │  _handle_escalation_confirmation  │
    │  elif confirmation is False       │
    └────────┬─────────────────────────┘
             ↓
    ╔═════════════════════════════════════════════════════════════════╗
    ║  preamble = "Mohon maaf langkah-langkah..."                     ║
    ║                                                                  ║
    ║  incident_guide = escalation_guide(                             ║
    ║      question,                                                  ║
    ║      vector_store,                                              ║
    ║      embedding_service,                                         ║
    ║      doc_type="INCIDENT_LINK")  ← NEW PARAMETER                ║
    ╚═════════════════════════════════════════════════════════════════╝
             ↓
    ┌────────────────────────────────────────────────────────────────┐
    │  Vector Search:                                                 │
    │  1. Encode "Belum juga, WiFi masih..." into embedding          │
    │  2. Find nearest chunks WHERE document.doc_type == "INCIDENT_  │
    │     LINK" (ONLY incident forms, not order forms!)              │
    │  3. Get top_k=1 result (best match)                            │
    └────────────┬──────────────────────────────────────────────────┘
                 ↓
    ┌────────────────────────────────────────────────────────────────┐
    │  Database Hit:                                                  │
    │  Found chunk with:                                             │
    │  - NAMA FORM: "Incident (Gangguan Aplikasi & Sistem)"         │
    │  - Link: "https://myssc.pertamina.com/.../#/itemprofile/200"   │
    └────────────┬──────────────────────────────────────────────────┘
                 ↓
╔════════════════════════════════════════════════════════════════════╗
║  Bot Response:                                                    ║
║  "Mohon maaf langkah-langkah di atas belum berhasil membantu.     ║
║                                                                    ║
║  Untuk menangani masalah ini, silakan gunakan form berikut:       ║
║                                                                    ║
║  📋 **NAMA FORM:** Incident (Gangguan Aplikasi & Sistem)          ║
║                                                                    ║
║  🔗 **Link:** https://myssc.pertamina.com/.../#/itemprofile/200"  ║
╚════════════════════════════════════════════════════════════════════╝
             ↓
    ┌────────────────────────────────────┐
    │  User makes incident ticket ✅     │
    │  (NO MORE HARDCODED INCIDENT FORM!)│
    └────────────────────────────────────┘
```

---

## DELETED vs CREATED: LINE COUNT BREAKDOWN

```
DELETED (~800 lines):
├─ detect_problem_category()      [200 lines] ❌
├─ CATEGORY_FORMS dict             [100 lines] ❌
├─ get_ticket_process()            [150 lines] ❌
├─ _find_escalation_by_keywords()  [150 lines] ❌
├─ get_contact_info()               [20 lines] ❌
├─ get_required_info()              [20 lines] ❌
├─ _extract_form_info()             [40 lines] ❌
└─ _INCIDENT_ESCALATION_REPLY var  [15 lines] ❌

CREATED (~100 lines):
├─ escalation_guide() rewritten    [55 lines] ✅
├─ _is_valid_link() simplified     [25 lines] ✅
├─ Routing updates (2 places)      [10 lines] ✅
└─ Escalation confirmation update  [10 lines] ✅

NET RESULT: -700 baris kode! 🎉
```

---

## UPDATED FILES SUMMARY

### 1. models.py ✅
```
Changes: 1 change
Lines Modified: 3 (DOC_TYPES tuple)
Impact: Database now supports 3 distinct document types
```

### 2. knowledge_base.html ✅
```
Changes: 4 changes
- Stat cards: 1 card → 2 cards (Order + Incident)
- Table badges: 2 options → 3 options
- Upload dropdown: 2 options → 3 options
- Format examples: 2 examples → 3 examples
Impact: UI now matches new 3-way document classification
```

### 3. chat_service.py ✅
```
Changes: 7 major changes + 2 function rewrites + 3 routing updates
Deletions: ~800 lines
Additions: ~100 lines
Net: -700 lines
Impact: 100% database-driven, zero hardcoded logic
```

---

## TESTING POINTS

```
✅ TEST CHECKLIST:

□ Upload new KB with doc_type="ORDER_LINK"
  → Dashboard shows in "Order Links" stat

□ Upload new KB with doc_type="INCIDENT_LINK"
  → Dashboard shows in "Incident Links" stat

□ User says "pesan laptop"
  → Intent = SERVICE_ORDER ✓
  → escalation_guide(..., doc_type="ORDER_LINK") ✓
  → Correct laptop form returned ✓

□ User troubleshoots, says "Belum"
  → _handle_escalation_confirmation() triggered ✓
  → escalation_guide(..., doc_type="INCIDENT_LINK") ✓
  → Incident form returned (not order form!) ✓

□ No match found for query
  → Fallback message shown ✓
  → Points to IT Portal ✓

□ Link validation
  → Placeholder links rejected ✓
  → Real URLs accepted ✓

□ Logging
  → All escalation_guide calls logged ✓
  → Form names and doc_types tracked ✓
```

---

## DEPLOYMENT NOTES

1. **No Database Migration Needed:** Already have `doc_type` field in Document model
   - Just update DOC_TYPES choices (model field definition only)

2. **Update Existing Documents:** Admin should update old "ESCALATION" docs to "ORDER_LINK" or "INCIDENT_LINK"
   - Migration script optional (manual update via admin is fine)

3. **No Settings/Config Changes:** Routing logic entirely within Python code

4. **Cache Invalidation:** If using caching, clear after deployment

5. **Backward Compatibility:** If old code references `doc_type="ESCALATION"`, it won't break but won't match new filter
   - Update all references to new doc_type values

---

## BENEFITS SUMMARY

| Aspect | BEFORE | AFTER |
|--------|--------|-------|
| **Code Size** | 800+ hardcoded lines | 100 data-driven lines |
| **Add Form** | Edit code + redeploy | Upload KB + instant |
| **Update Link** | Change Python dict + redeploy | Edit in dashboard + instant |
| **Scalability** | Limited by code | Unlimited by DB size |
| **Maintainability** | Hard (massive dicts) | Easy (single function) |
| **Testing** | Difficult (mocking dicts) | Easy (mockable DB) |
| **Admin UX** | Restricted (code-only) | Empowered (web UI) |
| **Response Quality** | Keyword matching | Vector semantic search |

🎉 **MISSION ACCOMPLISHED: 100% DATABASE-DRIVEN ARCHITECTURE!**
