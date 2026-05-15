# 💻 QUICK REFERENCE: KODE YANG BERUBAH

## File 1: `apps/rag/models.py`

### Change: Update DOC_TYPES Choices

```python
# BEFORE
DOC_TYPES = (
    ('TROUBLESHOOT', 'Troubleshooting Umum'),
    ('ESCALATION', 'Panduan UI Eskalasi'),
)

# AFTER
DOC_TYPES = (
    ('TROUBLESHOOT', 'Langkah Troubleshooting (Solusi Mandiri)'),
    ('ORDER_LINK', 'Link Pemesanan/Pengadaan Item IT Baru'),
    ('INCIDENT_LINK', 'Link Pelaporan Error/Kerusakan'),
)
```

---

## File 2: `apps/dashboard/templates/dashboard/knowledge_base.html`

### Change 1: Update Stat Cards

```html
<!-- BEFORE -->
<div class="stat-card">
    <div class="stat-card-header">
        <span class="stat-card-title">Eskalasi Links</span>
        <div class="stat-card-icon" style="background-color: rgba(245, 158, 11, 0.1); color: var(--warning);">
            <i class="bi bi-link-45deg"></i>
        </div>
    </div>
    <div class="stat-card-value">{{ stats.escalation }}</div>
</div>

<!-- AFTER: Added two new stat cards -->
<div class="stat-card">
    <div class="stat-card-header">
        <span class="stat-card-title">Order Links</span>
        <div class="stat-card-icon" style="background-color: rgba(59, 130, 246, 0.1); color: var(--info, #3b82f6);">
            <i class="bi bi-bag-plus"></i>
        </div>
    </div>
    <div class="stat-card-value">{{ stats.order_link }}</div>
</div>

<div class="stat-card">
    <div class="stat-card-header">
        <span class="stat-card-title">Incident Links</span>
        <div class="stat-card-icon" style="background-color: rgba(245, 158, 11, 0.1); color: var(--warning);">
            <i class="bi bi-exclamation-circle"></i>
        </div>
    </div>
    <div class="stat-card-value">{{ stats.incident_link }}</div>
</div>
```

### Change 2: Update Document Type Badge in Table

```html
<!-- BEFORE -->
{% if doc.doc_type == 'ESCALATION' %}
    <span class="badge" style="background-color: rgba(245, 158, 11, 0.2); color: #b45309;">🔗 Eskalasi</span>
{% else %}
    <span class="badge" style="background-color: rgba(16, 185, 129, 0.2); color: #047857;">🔧 Troubleshoot</span>
{% endif %}

<!-- AFTER -->
{% if doc.doc_type == 'INCIDENT_LINK' %}
    <span class="badge" style="background-color: rgba(245, 158, 11, 0.2); color: #b45309;">⚠️ Incident</span>
{% elif doc.doc_type == 'ORDER_LINK' %}
    <span class="badge" style="background-color: rgba(59, 130, 246, 0.2); color: #1e40af;">📦 Order</span>
{% else %}
    <span class="badge" style="background-color: rgba(16, 185, 129, 0.2); color: #047857;">🔧 Troubleshoot</span>
{% endif %}
```

### Change 3: Update Upload Modal Dropdown

```html
<!-- BEFORE -->
<select id="docType" ...>
    <option value="TROUBLESHOOT">🔧 Langkah Troubleshooting (Solusi Mandiri)</option>
    <option value="ESCALATION">🔗 Panduan Direct Link (Eskalasi ke Tim IT)</option>
</select>

<!-- AFTER -->
<select id="docType" ...>
    <option value="TROUBLESHOOT">🔧 Langkah Troubleshooting (Solusi Mandiri)</option>
    <option value="ORDER_LINK">📦 Link Pemesanan/Pengadaan Item IT Baru (SERVICE_ORDER)</option>
    <option value="INCIDENT_LINK">⚠️ Link Pelaporan Error/Kerusakan (INCIDENT_LINK)</option>
</select>
```

### Change 4: Update Format Examples

```html
<!-- BEFORE: 2 format examples -->
<!-- AFTER: 3 format examples -->

<!-- New example added for ORDER_LINK -->
<div style="margin-bottom: 1rem;">
    <strong style="color: #3b82f6;">✓ Format Order Link (Pengadaan Item):</strong>
    <pre style="...">---
NAMA FORM: Handset (Perangkat Mobile Perusahaan)
TRIGGER KEYWORD: handphone, hp, mobile, perangkat, order handset
PANDUAN TIKET: Untuk memesan handset baru, silahkan klik link dibawah
Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/101
---
NAMA FORM: Desktop (PC, Laptop, Peripheral)
TRIGGER KEYWORD: laptop baru, pc, pesan laptop, komputer baru
PANDUAN TIKET: Untuk mengajukan pengadaan perangkat baru
Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/102</pre>
</div>

<!-- Updated INCIDENT_LINK example -->
<div>
    <strong style="color: var(--warning);">✓ Format Incident Link (Error/Kerusakan):</strong>
    <pre style="...">---
NAMA FORM: Incident (Gangguan Aplikasi & Sistem)
TRIGGER KEYWORD: error, crash, tidak bisa, aplikasi tidak berfungsi, sistem down
PANDUAN TIKET: Untuk melaporkan gangguan sistem, silahkan klik link dibawah
Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/200
---
NAMA FORM: Email & Collaboration Tools Details
TRIGGER KEYWORD: email error, outlook tidak bisa, teams error, mailbox
PANDUAN TIKET: Untuk melaporkan masalah email, silahkan buat tiket
Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/201</pre>
</div>
```

---

## File 3: `apps/rag/services/chat_service.py`

### ❌ DELETIONS (Section Headers Menandai Tempat Penghapusan)

**1. DELETED: `get_ticket_process()` function** (lines ~959-1120)
```python
# ===== DELETED: get_ticket_process() function =====
# Reason: Now using database-driven escalation links via new escalation_guide()
# with dynamic doc_type parameter (ORDER_LINK or INCIDENT_LINK)
```

**2. DELETED: `_is_valid_link()` and `_extract_form_info()` helpers** (lines ~1122-1175)
```python
# ===== DELETED: _is_valid_link() and _extract_form_info() =====
# These were helper functions for old category-based escalation routing
# New dynamic approach handles validation within escalation_guide()
```

**3. DELETED: `detect_problem_category()` function** (lines ~1617-1810)
```python
# ===== DELETED: detect_problem_category() =====
# This large if-else chain categorized queries into hardcoded categories
# New system uses pure vector/BM25 search filtered by doc_type parameter
# No category detection needed - routing handled by intent detection instead
```

**4. DELETED: `get_contact_info()` and `get_required_info()` functions** (lines ~1816-1850)
```python
# ===== DELETED: get_contact_info() and get_required_info() =====
# These static functions returned hardcoded contact info per category
# New system gets all info directly from database records via escalation_guide()
```

**5. DELETED: `_INCIDENT_ESCALATION_REPLY` variable** (lines ~1806-1820)
```python
# NOTE: _INCIDENT_ESCALATION_REPLY DELETED
# Reason: Now using escalation_guide(doc_type="INCIDENT_LINK") for dynamic responses
# This ensures all incident handling uses real database links instead of hardcoded URLs
```

---

### ✅ NEW IMPLEMENTATION: `escalation_guide()` Rewritten

```python
def escalation_guide(query_issue: str, vector_store, embedding_service, 
                     doc_type: str = "ORDER_LINK") -> str:
    """
    NEW REWRITTEN VERSION: Pure database-driven escalation guide using Vector + BM25 search.
    
    NO MORE HARDCODED DICTIONARIES OR CATEGORY DETECTION.
    All routing is now dynamic from the database.
    
    Args:
        query_issue: User's query/issue description
        vector_store: Vector store for semantic search
        embedding_service: Embedding service for vector encoding
        doc_type: Document type to search in ('ORDER_LINK' or 'INCIDENT_LINK')
                  Default is 'ORDER_LINK' for general service requests
    
    Returns:
        String with NAMA FORM and Link if found, else generic fallback message
    
    Strategy:
    1. Use Vector semantic search to find best matching chunk by doc_type
    2. Extract NAMA FORM and Link from the matched chunk
    3. Return structured response with form name and link
    4. If no match, return generic fallback asking user to contact IT Portal
    """
    from apps.rag.models import DocumentChunk
    
    try:
        logger.info("escalation_guide_request", extra={
            "query": query_issue[:80],
            "doc_type": doc_type,
        })
        
        # STRATEGY 1: Semantic Vector Search filtered by doc_type
        results = retrieve_context(
            query_issue, vector_store, embedding_service,
            doc_type=doc_type, top_k=1,
        )
        
        if results and results[0].get("content"):
            content = results[0]["content"]
            score = results[0].get("score", 0)
            
            # Extract NAMA FORM and Link
            form_name = None
            link = None
            
            for line in content.split('\n'):
                if 'NAMA FORM:' in line:
                    form_name = line.split('NAMA FORM:')[1].strip()
                elif 'Link:' in line:
                    link = line.split('Link:')[1].strip()
            
            # Validate link is not a placeholder
            if form_name and link and _is_valid_link(link):
                logger.info("escalation_guide_found", extra={
                    "form_name": form_name,
                    "doc_type": doc_type,
                    "score": round(score, 3),
                })
                return (
                    f"Untuk menangani masalah ini, silakan gunakan form berikut:\n\n"
                    f"📋 **NAMA FORM:** {form_name}\n\n"
                    f"🔗 **Link:** {link}"
                )
            elif form_name and not link:
                # Form found but link is missing or placeholder
                logger.warning("escalation_guide_no_valid_link", extra={
                    "form_name": form_name,
                    "doc_type": doc_type,
                    "score": score,
                })
        
        # FALLBACK: No valid result found
        logger.info("escalation_guide_no_match", extra={
            "query": query_issue[:60],
            "doc_type": doc_type,
        })
        
        portal_message = (
            f"Panduan spesifik untuk tipe '{doc_type}' belum tersedia.\n\n"
            f"Silakan kunjungi **Portal IT Support** untuk membuat tiket:\n"
            f"🔗 https://myssc.pertamina.com/dwp/app/\n\n"
            f"Tim IT kami siap membantu Anda selanjutnya!"
        )
        return portal_message

    except Exception as e:
        logger.error("escalation_guide_error", extra={
            "error": str(e),
            "doc_type": doc_type,
        })
        return (
            "Terjadi kesalahan saat mengambil panduan eskalasi.\n\n"
            "Silakan hubungi IT Support melalui Portal: https://myssc.pertamina.com/dwp/app/"
        )


def _is_valid_link(link: str) -> bool:
    """
    Check if link is valid URL (not a placeholder).
    Invalid patterns: [LINK_BELUM_TERSEDIA], [BELUM], 'null', 'n/a', etc.
    """
    if not link:
        return False
    
    link_lower = link.lower()
    
    # Check for placeholder patterns
    invalid_patterns = [
        '[link_belum_tersedia',
        '[belum',
        'not available',
        'tbd',
        'null',
        'n/a',
        'belum tersedia',
    ]
    
    for pattern in invalid_patterns:
        if pattern in link_lower:
            return False
    
    # Check if it's a real URL (starts with http/https or contains #/)
    if link.startswith('http') or link.startswith('https') or '/#' in link:
        return True
    
    return False
```

---

### ✅ UPDATED: `_handle_escalation_confirmation()`

```python
# BEFORE
elif confirmation is False:  # User menjawab "Belum/Tidak/Gagal"
    session["awaiting_support_confirmation"] = False
    # Gunakan _INCIDENT_ESCALATION_REPLY (hardcoded) — konsisten untuk semua kasus troubleshoot
    answer = _INCIDENT_ESCALATION_REPLY
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer

# AFTER
elif confirmation is False:  # User menjawab "Belum/Tidak/Gagal"
    session["awaiting_support_confirmation"] = False
    # NEW: Use dynamic escalation_guide with INCIDENT_LINK
    # This retrieves actual form and link from the database
    preamble = "Mohon maaf langkah-langkah di atas belum berhasil membantu.\n\n"
    incident_guide = escalation_guide(
        question, 
        vector_store, 
        embedding_service, 
        doc_type="INCIDENT_LINK"
    )
    answer = preamble + incident_guide
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer
```

---

### ✅ UPDATED: `_process_chat_sync()` - SERVICE_ORDER

```python
# BEFORE
elif intent == "SERVICE_ORDER":
    logger.info("intent_service_order", extra={"session_id": session_id, "question": question[:80]})
    guide = escalation_guide(question, vector_store, embedding_service)
    answer = (
        "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
        "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
        f"{guide}"
    )

# AFTER
elif intent == "SERVICE_ORDER":
    logger.info("intent_service_order", extra={"session_id": session_id, "question": question[:80]})
    guide = escalation_guide(question, vector_store, embedding_service, doc_type="ORDER_LINK")
    answer = (
        "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
        "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
        f"{guide}"
    )
```

---

### ✅ UPDATED: `_process_chat_sync()` - ESCALATION_QUERY

```python
# BEFORE
guide = escalation_guide(session.get("last_it_problem") or question, vector_store, embedding_service)
answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"

# AFTER
guide = escalation_guide(session.get("last_it_problem") or question, vector_store, embedding_service, doc_type="INCIDENT_LINK")
answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
```

---

### ✅ UPDATED: `_process_chat_stream()` - SERVICE_ORDER & ESCALATION

```python
# BEFORE (SERVICE_ORDER)
guide = escalation_guide(question, vector_store, embedding_service)
answer = (
    "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
    "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
    f"{guide}"
)

# AFTER (SERVICE_ORDER)
guide = escalation_guide(question, vector_store, embedding_service, doc_type="ORDER_LINK")
answer = (
    "Baik! Permintaan Anda terdeteksi sebagai **Service Order** (Pengadaan/Pemasangan). "
    "Berikut panduan pengajuan form yang perlu Anda isi:\n\n"
    f"{guide}"
)

# BEFORE (ESCALATION_QUERY)
guide = escalation_guide(
    session.get("last_it_problem") or question, vector_store, embedding_service
)
answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"

# AFTER (ESCALATION_QUERY)
guide = escalation_guide(
    session.get("last_it_problem") or question, vector_store, embedding_service, doc_type="INCIDENT_LINK"
)
answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
```

---

## Summary of Changes

| Type | Count | Impact |
|------|-------|--------|
| **Functions Deleted** | 7 | ~700 lines removed |
| **Variables Deleted** | 1 | _INCIDENT_ESCALATION_REPLY |
| **Functions Rewritten** | 1 | escalation_guide() |
| **Functions Modified** | 3 | _handle_escalation_confirmation(), _process_chat_sync(), _process_chat_stream() |
| **New Helper Functions** | 1 | _is_valid_link() (simplified) |
| **Files Changed** | 3 | models.py, knowledge_base.html, chat_service.py |
| **Net Code Reduction** | ~700 lines | Much cleaner codebase! |

---

## Testing Checklist

- [ ] SERVICE_ORDER intent → escalation_guide(doc_type="ORDER_LINK") → correct form
- [ ] Escalation confirmation "Belum" → escalation_guide(doc_type="INCIDENT_LINK") → incident form
- [ ] Dashboard upload → Select ORDER_LINK option → renders correctly
- [ ] Dashboard upload → Select INCIDENT_LINK option → renders correctly
- [ ] Vector search filters by doc_type parameter correctly
- [ ] Fallback message appears when no match found
- [ ] Link validation works (rejects placeholder links)
- [ ] Logging tracks successful/failed escalation_guide calls
