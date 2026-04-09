# IMPLEMENTATION GUIDE
## Memperbaiki: "Acces Control Device Tidak Muncul"

---

## 🔍 PROBLEM SUMMARY (60 detik explanation)

| Aspek | Status |
|-------|--------|
| **File knowledge_base_website_tiket.txt** | ✓ ADA (sudah di workspace) |
| **Content "Acces Control Device"** | ✓ ADA (di file) |
| **Tersimpan di Database** | ✗ TIDAK (belum di-ingest) |
| **Tampil saat user bertanya** | ✗ TIDAK (tidak terindex) |

**Root Cause**: Knowledge base website tiket **TIDAK di-ingest ke database dengan doc_type="ESCALATION"**. File hanya tersimpan di disk, belum di-parse dan di-simpan di DocumentChunk table.

---

## 📋 STEP-BY-STEP IMPLEMENTATION (Estimated: 1-2 jam)

### STEP 1️⃣: Database Migration (10 menit)

**Tujuan**: Tambah field `trigger_keywords` ke DocumentChunk untuk metadata matching.

```bash
# File: apps/rag/models.py
```

**Lokasi untuk edit**: [apps/rag/models.py](apps/rag/models.py#L45)

**Tambahkan field ini ke DocumentChunk class**:
```python
class DocumentChunk(models.Model):
    document = models.ForeignKey(...)
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding_vector = models.BinaryField(blank=True, null=True)
    
    # ← TAMBAH FIELD INI:
    trigger_keywords = models.TextField(
        blank=True,
        null=True,
        help_text="Comma-separated keywords untuk trigger form ini"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
```

**Jalankan migration**:
```powershell
python manage.py makemigrations rag
python manage.py migrate
```

---

### STEP 2️⃣: Intent Detection Enhancement (10 menit)

**Tujuan**: Tambah pattern untuk mendeteksi "REQUEST_FORM" intent.

**Lokasi untuk edit**: [apps/rag/services/chat_service.py](apps/rag/services/chat_service.py#L602)

**Cari fungsi `detect_intent_rules()` dan tambahkan SEBELUM fungsi itu**:

```python
# Sebelum class OutOfScopeSemanticsDetector

_FORM_REQUEST_PATTERNS = re.compile(
    r'''(?x)
    (
      bagaimana.*?(?:membuat|buat|buka|akses|submit).*?tiket
      | cara.*?(?:membuat|buat).*?(?:tiket|form)
      | form.*?(?:apa|bagaimana|cara|step)
      | step.*?(?:membuat|buat).*?tiket
      | panduan.*?(?:membuat|membuat|submit).*?tiket
      | di mana.*?(?:klik|menu|tombol|bagian)
      | portal.*?(?:caranya|bagaimana|cara)
      | akses control.*?(?:bagaimana|cara|form|tiket|submit)
      | kartu akses.*?(?:tiket|form|cara|submit)
      | pintu.*?(?:membuat|buat).*?tiket
      | fingerprint.*?(?:membuat|buat).*?tiket
    )
    ''', re.IGNORECASE
)
```

**Dalam fungsi `detect_intent_rules()`, tambahkan di awal sebelum return None**:

```python
def detect_intent_rules(question: str) -> Optional[str]:
    """..."""
    q = question.strip()

    if _FORM_REQUEST_PATTERNS.search(q):
        return "REQUEST_FORM"  # ← TAMBAH BARIS INI
    if _ESCALATION_PATTERNS.search(q): 
        return "REQUEST_IT_SUPPORT"
    # ... existing logic
```

---

### STEP 3️⃣: Extend detect_intent() untuk recognize REQUEST_FORM (5 menit)

**Lokasi untuk edit**: [apps/rag/services/chat_service.py](apps/rag/services/chat_service.py#L663)

**Di function `detect_intent()`, update INTENT validation**:

```python
def detect_intent(question: str, embedding_service=None) -> str:
    """..."""
    rule_result = detect_intent_rules(question)
    if rule_result:
        logger.info("intent_detected", extra={
            "intent": rule_result,
            "latency_ms": "<1",
        })
        return rule_result
    # ... rest tetap sama
```

**Di function `detect_intent_llm_fallback()`, update valid intents**:

```python
def detect_intent_llm_fallback(question: str) -> str:
    """..."""
    try:
        # ... existing code
        valid = {
            "REQUEST_IT_SUPPORT",
            "REJECT_IT_SUPPORT",
            "GENERAL_CHAT",
            "IT_PROBLEM",
            "REQUEST_FORM",  # ← TAMBAH INI
            "OUT_OF_SCOPE"
        }
```

---

### STEP 4️⃣: Update Chat Processing untuk Pass Intent (10 menit)

**Lokasi untuk edit**: [apps/rag/services/chat_service.py](apps/rag/services/chat_service.py#L1577)

**Di function `_process_chat_sync()`, update context retrieval**:

```python
def _process_chat_sync(question, session, vector_store, embedding_service, session_id):
    """..."""
    
    # Detect intent
    intent = detect_intent(question, embedding_service)  # ← Already exists
    
    # ← MODIFICATION: Pass intent to get_context_for_session
    context = get_context_for_session(
        question, session, vector_store, embedding_service,
        intent=intent  # ← TAMBAH PARAMETER INI
    )
    
    # ... rest tetap sama
```

**Di function `_process_chat_stream()`, lakukan hal sama**:

```python
def _process_chat_stream(question, session, vector_store, embedding_service, session_id):
    """..."""
    
    intent = detect_intent(question, embedding_service)
    
    context = get_context_for_session(
        question, session, vector_store, embedding_service,
        intent=intent  # ← TAMBAH PARAMETER INI
    )
    
    # ... rest tetap sama
```

---

### STEP 5️⃣: Modify get_context_for_session() untuk Intent-Aware Routing (15 menit)

**Lokasi untuk edit**: [apps/rag/services/chat_service.py](apps/rag/services/chat_service.py#L851)

**Replace entire function**:

```python
def get_context_for_session(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    intent: str = None,  # ← NEW PARAMETER
) -> Optional[str]:
    """
    Session-level RAG caching dengan INTENT-AWARE doc_type routing.
    
    Jika intent="REQUEST_FORM" → cari di doc_type="ESCALATION"
    Jika intent="IT_PROBLEM" atau None → cari di doc_type="TROUBLESHOOT"
    """
    
    # Tentukan doc_type berdasarkan intent
    doc_type_needed = "TROUBLESHOOT"  # Default
    if intent in ["REQUEST_FORM", "REQUEST_IT_SUPPORT"]:
        doc_type_needed = "ESCALATION"
    
    # Caching logic tetap sama
    if session["attempts"] == 0 or session["cached_context"] is None:
        context = get_relevant_context(
            question, 
            vector_store, 
            embedding_service,
            doc_type=doc_type_needed  # ← PASS doc_type YANG TEPAT
        )
        session["cached_context"] = context
        logger.info("rag_cache_set", extra={
            "found": context is not None,
            "doc_type": doc_type_needed,
            "intent": intent,
            "query": question[:60],
        })
        return context

    logger.info("rag_cache_hit", extra={"attempts": session["attempts"]})
    return session["cached_context"]
```

---

### STEP 6️⃣: Reorganize KB — Extract & Ingest knowledge_base_website_tiket.txt (45 menit)

Ini adalah step KRITIS. Kita perlu:
1. **Parse** file knowledge_base_website_tiket.txt
2. **Extract** setiap form (Acces Control Device, Change Password, CCTV, dll)
3. **Ingest** ke database dengan doc_type="ESCALATION"

**Create file baru**: `apps/rag/management/commands/reorganize_escalation_kb.py`

```python
from django.core.management.base import BaseCommand
from apps.rag.models import Document, DocumentChunk
from apps.rag.services.embedding import EmbeddingService
import re
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Parse knowledge_base_website_tiket.txt dan ingest ke DB dengan doc_type=ESCALATION"

    def handle(self, *args, **options):
        embedding_service = EmbeddingService()
        
        # STEP A: Parse file
        file_path = 'media/documents/knowledge_base_website_tiket.txt'
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # STEP B: Split by "NAMA FORM:"
        # Pattern: ===...===\n\nNAMA FORM: XYZ\n...CATATAN KHUSUS: ...\n\n---
        form_pattern = re.compile(
            r'NAMA FORM:\s*([^\n]+)\n'
            r'TRIGGER KEYWORD:\s*([^\n]+)\n'
            r'KONTEKS MASALAH:\s*([^\n]+?)\n'
            r'PANDUAN UI:\n(.*?)'
            r'(?=CATATAN KHUSUS:|$)',
            re.DOTALL | re.IGNORECASE
        )
        
        forms = form_pattern.finditer(content)
        
        for form_match in forms:
            nama_form = form_match.group(1).strip()
            trigger_keywords = form_match.group(2).strip()
            konteks_masalah = form_match.group(3).strip()
            panduan_ui = form_match.group(4).strip()
            
            # Parse CATATAN KHUSUS jika ada
            catatan_idx = content.find("CATATAN KHUSUS:", form_match.start())
            if catatan_idx != -1 and catatan_idx < form_match.end():
                catatan_match = re.search(
                    r'CATATAN KHUSUS:\s*([^\n]+(?:\n(?!NAMA FORM:|---|\n\n)[^\n]+)*)',
                    content[form_match.start():],
                    re.MULTILINE
                )
                catatan_khusus = catatan_match.group(1).strip() if catatan_match else ""
            else:
                catatan_khusus = ""
            
            # STEP C: Buat Document
            self.stdout.write(f"Processing: {nama_form}")
            
            try:
                # Delete existing if any
                Document.objects.filter(
                    title=nama_form,
                    doc_type="ESCALATION"
                ).delete()
                
                # Create document
                full_content = f"""NAMA FORM: {nama_form}
TRIGGER KEYWORD: {trigger_keywords}
KONTEKS MASALAH: {konteks_masalah}
PANDUAN UI:
{panduan_ui}
CATATAN KHUSUS: {catatan_khusus}"""
                
                doc = Document.objects.create(
                    title=nama_form,
                    content=full_content,
                    category="ESCALATION_GUIDE",
                    doc_type="ESCALATION",
                    is_active=True,
                )
                
                # STEP D: Buat chunk dengan embedding
                embedding = embedding_service.embed_text(full_content)
                
                DocumentChunk.objects.create(
                    document=doc,
                    chunk_index=0,
                    content=full_content,
                    embedding_vector=embedding,
                    trigger_keywords=trigger_keywords,  # ← Store keywords
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created: {nama_form}")
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Error with {nama_form}: {str(e)}")
                )
                logger.error(f"Failed to ingest {nama_form}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS("✓ Reorganization complete!")
        )
```

**Jalankan command**:
```powershell
python manage.py reorganize_escalation_kb
```

**Verifikasi hasil**:
```powershell
python manage.py shell
>>> from apps.rag.models import Document
>>> docs = Document.objects.filter(doc_type="ESCALATION")
>>> print(f"Total ESCALATION docs: {docs.count()}")
>>> for doc in docs:
...     print(f"  - {doc.title}: {doc.content[:100]}...")
```

---

### STEP 7️⃣: Enhance retrieval.py dengan Trigger Keyword Matching (30 menit)

**Lokasi untuk edit**: [apps/rag/services/retrieval.py](apps/rag/services/retrieval.py#L75)

**Tambahkan fungsi baru SEBELUM `retrieve_context()`**:

```python
def filter_by_trigger_keywords(question: str) -> list:
    """
    Pre-filter ESCALATION documents berdasarkan trigger keywords.
    
    Returns sorted list dengan score boost untuk keyword match.
    """
    from apps.rag.models import DocumentChunk
    import re
    
    q_lower = question.lower()
    matches = []
    
    # Query all ESCALATION chunks dengan trigger_keywords
    chunks = DocumentChunk.objects.filter(
        document__doc_type="ESCALATION",
        document__is_active=True,
        trigger_keywords__isnull=False,
    ).exclude(trigger_keywords="").select_related('document')
    
    for chunk in chunks:
        keywords = chunk.trigger_keywords.split(',')
        keywords = [kw.strip().lower() for kw in keywords if kw.strip()]
        
        if not keywords:
            continue
        
        # Count keyword matches (word boundary)
        match_count = 0
        for kw in keywords:
            # Match whole word only
            if re.search(rf'\b{re.escape(kw)}\b', q_lower):
                match_count += 1
        
        if match_count >= 1:  # At least 1 keyword match
            matches.append({
                "id": chunk.id,
                "document_chunk_id": chunk.id,
                "score": 0.92 + (min(match_count, 5) * 0.02),  # Boost score
                "content": chunk.content,
                "category": chunk.document.category,
                "doc_type": chunk.document.doc_type,
                "match_type": "trigger_keyword",
                "matched_keywords_count": match_count,
            })
    
    # Sort by match count desc, then score desc
    return sorted(
        matches,
        key=lambda x: (-x["matched_keywords_count"], -x["score"])
    )
```

**Dalam fungsi `retrieve_context()`, tambahkan trigger keyword pre-filtering**:

**Cari baris**:
```python
def retrieve_context(question, vector_store, embedding_service, doc_type=None, top_k=3):
    """..."""
    try:
        timer_start = time.time()
        
        # Wajib load memori agar tidak kosong!
        vector_store.load_embeddings()
```

**Ubah menjadi**:
```python
def retrieve_context(question, vector_store, embedding_service, doc_type=None, top_k=3):
    """..."""
    try:
        timer_start = time.time()
        
        # ← NEW: Trigger keyword pre-filtering untuk ESCALATION
        if doc_type == "ESCALATION":
            keyword_matches = filter_by_trigger_keywords(question)
            if keyword_matches and len(keyword_matches) > 0:
                logger.info("retrieval_keyword_match", extra={
                    "matches": len(keyword_matches),
                    "top_match": keyword_matches[0].get("content", "")[:60],
                })
                # Return top keyword matches
                return keyword_matches[:top_k]
        
        # Lanjut ke semantic search jika tidak ada keyword match
        vector_store.load_embeddings()
```

---

## ✅ VERIFICATION CHECKLIST

Setelah semua step selesai, jalankan test ini:

```powershell
# Test Case 1: Database check
python manage.py shell
>>> from apps.rag.models import Document
>>> from django.db.models import Count
>>> doc_counts = Document.objects.values('doc_type').annotate(count=Count('id'))
>>> for dc in doc_counts:
...     print(f"{dc['doc_type']}: {dc['count']} documents")
# Expected: TROUBLESHOOT: X, ESCALATION: 30+

# Test Case 2: Intent detection
>>> from apps.rag.services.chat_service import detect_intent
>>> queries = [
...     "kartu akses pintu tidak terbaca",
...     "bagaimana cara membuat tiket akses kontrol",
...     "cara membuat tiket untuk kartu akses",
... ]
>>> for q in queries:
...     intent = detect_intent(q)
...     print(f"{q} -> {intent}")
# Expected: REQUEST_FORM untuk yang punya "cara membuat tiket"

# Test Case 3: Chat test
# Buka chatbot dan jalankan:
# User: "Bagaimana cara membuat tiket untuk kartu akses yang tidak terbaca?"
# Expected: ✓ Muncul PANDUAN UI dengan tahap-tahapan membuat tiket
```

---

## 📊 EXPECTED RESULTS

```
SEBELUM IMPLEMENTASI:
┌─ User: "bagaimana cara membuat tiket kartu akses?"
├─ Intent: IT_PROBLEM
├─ Search: doc_type="TROUBLESHOOT"
├─ Result: "Tidak ada hasil yang relevan"
└─ Fallback: Generic ticket process ❌

SETELAH IMPLEMENTASI:
┌─ User: "bagaimana cara membuat tiket kartu akses?"
├─ Intent: REQUEST_FORM ✓
├─ Search: doc_type="ESCALATION" + trigger_keywords="kartu akses" ✓
├─ Result: "Acces Control Device form guide" ✓
└─ UI Steps:
   1. Login ke portal IT Support...
   2. Pilih kategori "Infrastruktur & Keamanan Fisik"
   3. Klik kotak "Acces Control Device"
   4. ... ✓✓✓ CORRECT!
```

---

## ⚠️ COMMON ISSUES & FIXES

| Issue | Cause | Fix |
|-------|-------|-----|
| KeyError: 'query' | Migration tidak jalan | `python manage.py migrate` |
| Intent masih IT_PROBLEM | Regex pattern tidak match | Check regex case sensitivity |
| trigger_keywords field kosong | DocumentChunk tidak populate | Re-run `reorganize_escalation_kb` |
| No ESCALATION docs found | File parsing gagal | Cek file path dan encoding utf-8 |
| Keyword match tapi score rendah | Scoring logic | Increase boost factor di `filter_by_trigger_keywords()` |

