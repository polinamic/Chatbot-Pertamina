# 📝 EDIT CHECKLIST — File & Line Numbers

Quick reference untuk mengedit file yang tepat dengan line numbers yang spesifik.

---

## FILE #1: apps/rag/models.py

### Edit 1: Add trigger_keywords field ke DocumentChunk

**Line**: 45-55 (existing field definitions)

**Action**: TAMBAH field sebelum `created_at`

```python
# BEFORE LINE 48 (atau whereever created_at is)
trigger_keywords = models.TextField(
    blank=True,
    null=True,
    help_text="Comma-separated keywords untuk trigger form ini"
)
```

**Hasil**: DocumentChunk akan punya field `trigger_keywords`

**Command setelah edit**:
```powershell
python manage.py makemigrations rag
python manage.py migrate
```

---

## FILE #2: apps/rag/services/chat_service.py

### Edit 2A: Add _FORM_REQUEST_PATTERNS regex (sebelum detect_intent_rules)

**Line**: Cari `def detect_intent_rules(question:` (sekitar line 602)

**Action**: TAMBAH SEBELUM fungsi itu

```python
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

### Edit 2B: Modify detect_intent_rules() function

**Line**: ~605 (dalam fungsi, sebelum `if _ESCALATION_PATTERNS`)

**Action**: UBAH dari:
```python
def detect_intent_rules(question: str) -> Optional[str]:
    """..."""
    q = question.strip()

    if _ESCALATION_PATTERNS.search(q): return "REQUEST_IT_SUPPORT"
```

**Menjadi**:
```python
def detect_intent_rules(question: str) -> Optional[str]:
    """..."""
    q = question.strip()

    if _FORM_REQUEST_PATTERNS.search(q):
        return "REQUEST_FORM"  # ← TAMBAH BARIS INI
    if _ESCALATION_PATTERNS.search(q): return "REQUEST_IT_SUPPORT"
```

### Edit 2C: Update detect_intent_llm_fallback() valid intents

**Line**: ~635 (dalam try block, `valid = {...}`)

**Action**: UBAH dari:
```python
valid = {"REQUEST_IT_SUPPORT","REJECT_IT_SUPPORT","GENERAL_CHAT","IT_PROBLEM","OUT_OF_SCOPE"}
```

**Menjadi**:
```python
valid = {"REQUEST_IT_SUPPORT","REJECT_IT_SUPPORT","GENERAL_CHAT","IT_PROBLEM","REQUEST_FORM","OUT_OF_SCOPE"}
```

### Edit 2D: Update get_context_for_session() signature & logic

**Line**: ~851 (fungsi `def get_context_for_session(...)`)

**Action**: UBAH ENTIRE FUNCTION dari:
```python
def get_context_for_session(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
) -> Optional[str]:
```

**Menjadi**:
```python
def get_context_for_session(
    question: str,
    session: Dict,
    vector_store,
    embedding_service,
    intent: str = None,  # ← TAMBAH PARAMETER INI
) -> Optional[str]:
    """
    Session-level RAG caching dengan INTENT-AWARE doc_type routing.
    """
    
    # Tentukan doc_type berdasarkan intent ← TAMBAH SECTION INI
    doc_type_needed = "TROUBLESHOOT"  # Default
    if intent in ["REQUEST_FORM", "REQUEST_IT_SUPPORT"]:
        doc_type_needed = "ESCALATION"
    
    # MODIFY: get_relevant_context call
    if session["attempts"] == 0 or session["cached_context"] is None:
        context = get_relevant_context(
            question, 
            vector_store, 
            embedding_service,
            doc_type=doc_type_needed  # ← TAMBAH PARAMETER INI
        )
        session["cached_context"] = context
        logger.info("rag_cache_set", extra={
            "found": context is not None,
            "doc_type": doc_type_needed,  # ← TAMBAH LOG INI
            "intent": intent,  # ← TAMBAH LOG INI
            "query": question[:60],
        })
        return context
    
    logger.info("rag_cache_hit", extra={"attempts": session["attempts"]})
    return session["cached_context"]
```

### Edit 2E: Update _process_chat_sync() untuk pass intent

**Line**: ~1596 (dalam fungsi, setelah `intent = detect_intent(...)`)

**Action**: UBAH dari:
```python
    intent = detect_intent(question, embedding_service)
    
    context = get_context_for_session(question, session, vector_store, embedding_service)
```

**Menjadi**:
```python
    intent = detect_intent(question, embedding_service)
    
    context = get_context_for_session(
        question, session, vector_store, embedding_service,
        intent=intent  # ← TAMBAH PARAMETER INI
    )
```

### Edit 2F: Update _process_chat_stream() untuk pass intent

**Line**: ~1681 (dalam fungsi, setelah `intent = detect_intent(...)`)

**Action**: SAMA SEPERTI Edit 2E

```python
    intent = detect_intent(question, embedding_service)
    
    context = get_context_for_session(
        question, session, vector_store, embedding_service,
        intent=intent  # ← TAMBAH PARAMETER INI
    )
```

---

## FILE #3: apps/rag/services/retrieval.py

### Edit 3A: Add filter_by_trigger_keywords() function (optional, aber recommended)

**Line**: ~75 (sebelum `def retrieve_context(...)`)

**Action**: TAMBAH FUNGSI BARU

```python
def filter_by_trigger_keywords(question: str) -> list:
    """
    Pre-filter ESCALATION documents berdasarkan trigger keywords.
    """
    from apps.rag.models import DocumentChunk
    import re
    
    q_lower = question.lower()
    matches = []
    
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
        
        match_count = 0
        for kw in keywords:
            if re.search(rf'\b{re.escape(kw)}\b', q_lower):
                match_count += 1
        
        if match_count >= 1:
            matches.append({
                "id": chunk.id,
                "document_chunk_id": chunk.id,
                "score": 0.92 + (min(match_count, 5) * 0.02),
                "content": chunk.content,
                "category": chunk.document.category,
                "doc_type": chunk.document.doc_type,
                "match_type": "trigger_keyword",
                "matched_keywords_count": match_count,
            })
    
    return sorted(
        matches,
        key=lambda x: (-x["matched_keywords_count"], -x["score"])
    )
```

### Edit 3B: Enhance retrieve_context() dengan keyword pre-filtering

**Line**: ~96 (dalam fungsi, setelah `timer_start = time.time()` dan `vector_store.load_embeddings()`)

**Action**: TAMBAH SEBELUM semantic search

```python
        # ← NEW: Trigger keyword pre-filtering untuk ESCALATION
        if doc_type == "ESCALATION":
            keyword_matches = filter_by_trigger_keywords(question)
            if keyword_matches and len(keyword_matches) > 0:
                logger.info("retrieval_keyword_match", extra={
                    "matches": len(keyword_matches),
                    "top_match": keyword_matches[0].get("content", "")[:60],
                })
                return keyword_matches[:top_k]
```

---

## FILE #4: apps/rag/management/commands/reorganize_escalation_kb.py (NEW FILE)

**Action**: CREATE FILE BARU dengan isi:

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
        
        # Parse file
        file_path = 'media/documents/knowledge_base_website_tiket.txt'
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by "NAMA FORM:"
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
            
            self.stdout.write(f"Processing: {nama_form}")
            
            try:
                Document.objects.filter(
                    title=nama_form,
                    doc_type="ESCALATION"
                ).delete()
                
                full_content = f"""NAMA FORM: {nama_form}
TRIGGER KEYWORD: {trigger_keywords}
KONTEKS MASALAH: {konteks_masalah}
PANDUAN UI:
{panduan_ui}"""
                
                doc = Document.objects.create(
                    title=nama_form,
                    content=full_content,
                    category="ESCALATION_GUIDE",
                    doc_type="ESCALATION",
                    is_active=True,
                )
                
                embedding = embedding_service.embed_text(full_content)
                
                DocumentChunk.objects.create(
                    document=doc,
                    chunk_index=0,
                    content=full_content,
                    embedding_vector=embedding,
                    trigger_keywords=trigger_keywords,
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

---

## EXECUTION ORDER

```
1️⃣  Edit apps/rag/models.py (Edit 1)
    └─ Add trigger_keywords field

2️⃣  Create migration & run
    └─ python manage.py makemigrations rag
    └─ python manage.py migrate

3️⃣  Edit apps/rag/services/chat_service.py (Edit 2A-F)
    └─ Add patterns & update functions

4️⃣  Edit apps/rag/services/retrieval.py (Edit 3A-B)
    └─ Add trigger keyword filtering

5️⃣  Create FILE: apps/rag/management/commands/reorganize_escalation_kb.py
    └─ NEW FILE untuk ingest

6️⃣  Run ingest command
    └─ python manage.py reorganize_escalation_kb

7️⃣  Test dalam chatbot
    └─ User: "Bagaimana cara membuat tiket kartu akses?"
    └─ Expected: ✓ Acces Control Device form guide
```

---

## QUICK COPY-PASTE COMMANDS

```powershell
# 1. Migrate
python manage.py makemigrations rag
python manage.py migrate

# 2. Ingest escalation KB
python manage.py reorganize_escalation_kb

# 3. Check database
python manage.py shell
>>> from apps.rag.models import Document
>>> print(Document.objects.filter(doc_type="ESCALATION").count())
# Expected: 30+

# 4. Test intent detection
>>> from apps.rag.services.chat_service import detect_intent
>>> print(detect_intent("Bagaimana cara membuat tiket kartu akses"))
# Expected: REQUEST_FORM
```

---

## Estimasi Waktu Per File

| File | Edits | Time |
|------|-------|------|
| models.py | 1 | 5 min |
| chat_service.py | 6 | 25 min |
| retrieval.py | 2 | 15 min |
| reorganize_escalation_kb.py | 1 (new) | 30 min |
| Migration & test | - | 10 min |
| **TOTAL** | - | **1.5 jam** |

