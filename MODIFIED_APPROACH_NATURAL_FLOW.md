# 🎯 MODIFIED APPROACH: Natural Troubleshoot → Escalation Flow

**Request User**: Jawab dengan troubleshoot dulu, baru tampilkan panduan UI jika user escalate.

---

## ✅ GOOD NEWS: Current Flow Sudah Hampir Tepat!

Kode existing di `_process_chat_sync()` dan `_process_chat_stream()` **SUDAH PUNYA FLOW YANG BENAR**:

```python
Turn 1: User tanya "Kartu akses tidak terbaca"
  → intent = "IT_PROBLEM"
  → Jawab dengan TROUBLESHOOT (SOP steps) ✓

Turn 2: User: "Sudah coba tapi masih tidak bisa"
  → session["attempts"] >= 2
  → Tampilkan _ESCALATION_OFFER (tawarkan eskalasi) ✓

User confirm: "Ya, hubungi tim IT"
  → detect_confirmation() = True
  → Call escalation_guide()
  → Tampilkan PANDUAN UI untuk membuat tiket ✓
```

**Jadi flow yang user inginkan SUDAH BERJALAN!** 

Hanya perlu ensure knowledge base di-ingest dengan benar.

---

## 📋 APA YANG PERLU DIUBAH (Minimal Changes)

### Perubahan #1: PASTIKAN TROUBLESHOOT KB Di-Ingest dengan Benar
**File**: `knowledge_base_it.txt`  
**Current Status**: Belum clear teringestion dengan baik  
**Action**: Re-ingest dengan proper chunking

### Perubahan #2: TAMBAHKAN ESCALATION KB (Optional tapi Recommended)
**File**: `knowledge_base_website_tiket.txt`  
**Purpose**: Untuk escalation_guide() function  
**Action**: Upload via dashboard setelah re-organize

---

## 🛠️ IMPLEMENTASI (Simplified Version)

### STEP 1: Database Migration (5 menit)

**Hanya ini yang perlu di-code**:

Add field untuk track trigger keywords (optional, untuk future use):

```python
# apps/rag/models.py - TAMBAH field ini

class DocumentChunk(models.Model):
    document = models.ForeignKey(...)
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding_vector = models.BinaryField(blank=True, null=True)
    
    # ← OPTIONAL: Untuk future metadata matching
    # trigger_keywords = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
```

**Sebenarnya TIDAK PERLU migration** - current structure sudah cukup!

---

### STEP 2: YANG PENTING → Upload Knowledge Base via Dashboard

**Dashboard sudah ada!** Tinggal upload 2 file:

#### 2A: Upload TROUBLESHOOT Knowledge Base

**File**: `media/documents/knowledge_base_it.txt`

**Instruksi**:
1. Log in ke **Dashboard Admin** → http://your-app/admin/knowledge-base/
2. Klik **"+ Upload Knowledge Base"**
3. Category: **"TROUBLESHOOT"** (atau cek dropdown yang ada)
4. Upload file: **`knowledge_base_it.txt`** (dari `media/documents/`)
5. Klik **"Upload & Process"**

**Expected Result**: ~50+ troubleshoot documents terindex

![Step Admin Dashboard]

#### 2B: [OPTIONAL] Upload ESCALATION Knowledge Base

**File**: `media/documents/knowledge_base_website_tiket.txt`

**Instruksi**:
1. Klik **"+ Upload Knowledge Base"** lagi
2. Category: **"ESCALATION"** atau **"Escalation Guide"**
3. Upload file: **`knowledge_base_website_tiket.txt`**
4. Klik **"Upload & Process"**

**Expected Result**: ~30+ escalation forms terindex (untuk escalation_guide function)

---

## 📊 FLOW YANG AKAN TERJADI (After Changes)

```
┌─ USER TURN 1
│  ├─ Query: "Kartu akses tidak terbaca"
│  ├─ Intent Detection: IT_PROBLEM ✓
│  ├─ RAG Search: knowledge_base_it.txt ✓
│  ├─ Result: SOP cara fix (troubleshoot steps)
│  └─ Bot Answer:
│     "Coba langkah berikut:
│      1. Bersihkan kartu dengan kain lembut
│      2. Coba akses ulang di pintu berbeda
│      3. Jika masih tidak bisa, restart mesin fingerprint
│      4. Hubungi maintenance jika tetap layar mati"
│
├─ USER TURN 2
│  ├─ Query: "Sudah coba semua tapi masih tidak bisa"
│  ├─ session["attempts"] = 1 → increment jadi 2
│  ├─ Trigger ESCALATION_OFFER
│  └─ Bot Answer:
│     "[Previous troubleshoot answer]
│      
│      Tambahannya jika masih ada masalah, saya bisa membantu Anda
│      membuat tiket ke IT Support. Apakah Anda ingin saya arahkan?"
│
├─ USER TURN 3 (Escalation Confirm)
│  ├─ Query: "Ya, hubungi tim IT" atau "Iya please"
│  ├─ detect_confirmation() = True ✓
│  ├─ Call escalation_guide("Kartu akses tidak terbaca")
│  ├─ RAG Search: knowledge_base_website_tiket.txt ✓
│  └─ Bot Answer:
│     "Baik! Berikut panduan membuat tiket:
│      
│      === FORM: Acces Control Device ===
│      1. Login ke portal IT Support
│      2. Klik menu 'Infrastruktur & Keamanan Fisik'
│      3. Pilih 'Acces Control Device'
│      4. Isi detail masalah & klik 'Buat Tiket'"
```

---

## ✅ CHECKLIST (Delete Sebelum Implementasi)

```
☐ Knowledge base file ada:
   ✓ media/documents/knowledge_base_it.txt (TROUBLESHOOT)
   ✓ media/documents/knowledge_base_website_tiket.txt (ESCALATION)

☐ Database:
   ☐ python manage.py migrate (run jika ada perubahan model)

☐ Dashboard Upload:
   ☐ Open admin dashboard: http://localhost:8000/admin/
   ☐ Upload knowledge_base_it.txt dengan category TROUBLESHOOT
   ☐ Upload knowledge_base_website_tiket.txt dengan category ESCALATION

☐ Test Chat:
   ☐ Test Turn 1: "Bagaimana cara jika kartu akses tidak bisa?"
      Expected: ✓ Troubleshoot steps
   ☐ Test Turn 2: "Sudah coba tapi masih tidak bisa"
      Expected: ✓ Escalation offer
   ☐ Test Turn 3: "Ya hubungi tim IT"
      Expected: ✓ Form guide (Acces Control Device)
```

---

## 🎯 APA YANG TIDAK PERLU DIUBAH

| Item | Status | Alasan |
|------|--------|--------|
| Intent Detection | ✓ Keep As Is | Flow sudah tepat untuk IT_PROBLEM |
| RAG Routing | ✓ Keep As Is | Default ke TROUBLESHOOT sudah benar |
| Escalation Flow | ✓ Keep As Is | Logic `attempts >= 2` sudah benar |
| Chat Stream/Sync | ✓ Keep As Is | Already has proper routing |

---

## 📝 NEXT STEPS

### Langkah 1: Prepare Files (1 menit)
✓ Already done - files sudah ada di `media/documents/`

### Langkah 2: Upload via Dashboard (3 menit)
- [ ] Open http://localhost:8000/admin/knowledge-base/
- [ ] Upload `knowledge_base_it.txt` (TROUBLESHOOT)
- [ ] Upload `knowledge_base_website_tiket.txt` (ESCALATION)

### Langkah 3: Test Flow (5 menit)
- [ ] Chat test dengan 3 turns seperti di-atas
- [ ] Verify troubleshoot steps muncul di Turn 1
- [ ] Verify escalation offer muncul di Turn 2+
- [ ] Verify form guide muncul saat user confirm

---

## ⚡ TIPS: Jika Dashboard Upload Tidak Ada

Jika page admin tidak ada option upload, gunakan management command:

```powershell
# Create management command jika belum ada

python manage.py shell
>>> from apps.rag.models import Document
>>> doc = Document.objects.create(
...     title="Knowledge Base IT",
...     content=open('media/documents/knowledge_base_it.txt').read(),
...     category="TROUBLESHOOT",
...     is_active=True
... )
>>> print(f"Created: {doc.id}")
```

Tapi dashboard lebih simple dan recommended.

---

## 🎓 SUMMARY

**Modified Approach**:
- ✅ **Simpler** - tidak perlu ubah logic, hanya upload KB
- ✅ **Natural** - troubleshoot dulu, escalation on-demand
- ✅ **Low Risk** - tidak ada code changes, hanya data upload
- ✅ **Fast** - ready to test dalam 10 menit

**Key Difference from Previous Solution**:
- Previous: Complex - intent detection, RAG routing, metadata matching
- Now: Simple - just upload & test, flow sudah there!
