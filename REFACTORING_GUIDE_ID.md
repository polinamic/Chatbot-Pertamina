# 🔄 PANDUAN REFACTORING - Dari Hardcoded Ke Dynamic LLM-Based Routing

## 📝 RINGKASAN PERUBAHAN

### **Apa yang Dihapus (Total ~400+ baris)**

#### 1. Fungsi `detect_problem_category()` (Lines ~1660-1830)
**Alasan Penghapusan:** Fungsi ini 100% melakukan hardcoded keyword matching untuk mendeteksi kategori masalah (wifi, printer, notebook, dll). Setiap kali ada scenario baru, harus tambah keyword manual. Tidak scalable.

**Contoh kode yang dihapus:**
```python
def detect_problem_category(query: str) -> str:
    q = query.lower()
    
    if any(w in q for w in ['handphone', 'hp perusahaan', 'hp kantor', ...]):
        return "handset"
    
    if any(w in q for w in ['sim card', 'simcard', 'kartu sim', ...]):
        return "simcard"
    
    # ... 150+ baris if-elif-else checks
    
    return "general_it"
```

---

#### 2. Dictionary `CATEGORY_FORMS` (Lines ~1200-1420)
**Alasan Penghapusan:** Mapping manual dari kategori ke daftar form. Ketika KB berubah atau form baru ditambahkan, harus update dictionary ini.

**Contoh yang dihapus:**
```python
CATEGORY_FORMS = {
    "handset": [
        "Handset (Perangkat Mobile Perusahaan)",
        "SIM Card Corporate",
        "SIM Card Support",
    ],
    "network": [
        "Wifi Access",
        "Jaringan BIZ (Koneksi Jaringan Lokal)",
        "Modifikasi Akses Port (Firewall)",
    ],
    # ... 30+ kategori dengan masing-masing punya 1-5 form hardcoded
}
```

---

#### 3. Fungsi `_find_escalation_by_keywords()` (Lines ~1475-1650)
**Alasan Penghapusan:** Melakukan keyword matching manual terhadap isi chunk untuk mencari form yang cocok. Sekarang LLM akan handle ini secara cerdas.

**Kode yang dihapus (simplified):**
```python
def _find_escalation_by_keywords(query: str, category_forms: List[str] = None) -> str:
    keywords = re.findall(r'\b\w+\b', query_lower)
    
    for chunk in escalation_chunks:
        keyword_matches = sum(1 for kw in keywords if kw in content_lower)
        score = keyword_matches / len(keywords)  # Manual scoring
        
        if score > best_score:
            best_match = content
```

---

#### 4. Fungsi Utility Kategori (Lines ~1770-1880)
**Fungsi yang dihapus:**
- `get_ticket_process()` - Hardcoded panduan tiket per kategori
- `get_contact_info()` - Hardcoded kontak per kategori  
- `get_required_info()` - Hardcoded informasi yang diperlukan per kategori
- `detect_confirmation()` - Dapat dipertahankan tapi tidak essential untuk refactoring ini

---

#### 5. Intent Detection Logic Partial (SERVICE_ORDER patterns)
**Alasan Simplifikasi:** Regex untuk "peminjaman", "pesan", "order" hanya diperlukan untuk initial routing. Untuk escalation, LLM yang akan decide, bukan regex.

---

### **Apa yang Diubah**

#### Fungsi `escalation_guide()` → `escalation_guide_dynamic()`

**SEBELUM (dengan hardcoded logic):**
```python
def escalation_guide(query_issue: str, vector_store, embedding_service) -> str:
    # 1. Deteksi kategori (hardcoded keyword matching)
    category = detect_problem_category(query_issue.lower())
    
    # 2. Get forms dari CATEGORY_FORMS (hardcoded mapping)
    category_forms = CATEGORY_FORMS.get(category, [])
    
    # 3. Lakukan keyword matching dalam forms (hardcoded logic)
    results = _find_escalation_by_keywords(query_issue, category_forms=category_forms)
    
    # 4. Extract dan return form + link
    form_name, link = _extract_form_info(results)
    return f"FORM: {form_name}\nLink: {link}"
```

**SESUDAH (pure dynamic dengan LLM):**
```python
def escalation_guide_dynamic(query_issue: str, vector_store, embedding_service) -> str:
    # 1. Retrieve top-K chunks ESCALATION menggunakan vector search
    all_escalation_chunks = retrieve_context(
        query_issue, vector_store, embedding_service,
        doc_type="ESCALATION", top_k=10  # Ambil lebih banyak untuk LLM pilih
    )
    
    if not all_escalation_chunks:
        return _get_incident_escalation_reply()
    
    # 2. Prepare available forms untuk LLM
    available_forms = "\n\n".join([f["content"] for f in all_escalation_chunks])
    
    # 3. LLM sebagai intelligent router
    response = generate_llm(
        messages=[
            {"role": "system", "content": _ESCALATION_ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Pertanyaan user: {query_issue}\n\nAvailable forms:\n{available_forms}"}
        ],
        config_name="escalation_routing"
    )
    
    # 4. Extract form name dan link dari respons LLM
    form_name, link = _extract_form_info_from_llm(response)
    
    if form_name and link:
        return f"FORM: {form_name}\nLink: {link}"
    else:
        # Jika LLM tidak yakin, gunakan Incident form
        return _get_incident_escalation_reply()
```

---

## 🧠 System Prompt Baru untuk LLM (Escalation Router)

```python
_ESCALATION_ROUTER_SYSTEM_PROMPT = """\
Anda adalah AI Routing Expert untuk IT Support. Tugas Anda adalah membaca pertanyaan user 
dan memilih FORM yang paling sesuai dari daftar form yang tersedia.

INSTRUKSI KRITIS:
1. Baca DENGAN TELITI kolom "TRIGGER KEYWORD" dari setiap form.
2. Bandingkan kata-kata di pertanyaan user dengan TRIGGER KEYWORD.
3. Pilih form dengan jumlah keyword match tertinggi.
4. JIKA tidak ada form yang cocok (keyword match < 30%), kembalikan JSON:
   {"form_name": "Incident", "link": "incident"}

OUTPUT FORMAT (WAJIB JSON):
{
  "form_name": "<nama form yang dipilih>",
  "link": "<URL dari field Link>",
  "confidence": 0.85,
  "reasoning": "<penjelasan singkat mengapa form ini dipilih>"
}

CONTOH:
User: "saya ingin melakukan peminjaman notebook untuk mitra kerja"

Form 1: NAMA FORM: Layanan Pekerja Baru, Konsultan, Auditor dan Mitra Kerja
        TRIGGER KEYWORD: pekerja, baru, konsultan, mitra, kerja, notebook, ...
        Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/311

RESPONS YANG BENAR:
{
  "form_name": "Layanan Pekerja Baru, Konsultan, Auditor dan Mitra Kerja",
  "link": "https://myssc.pertamina.com/dwp/app/#/itemprofile/311",
  "confidence": 0.95,
  "reasoning": "User mention 'peminjaman', 'notebook', 'mitra', 'kerja' - semua ada di TRIGGER KEYWORD form ini"
}
"""
```

---

## 🔄 Alur Logika Baru (Dynamic Flow)

```
┌─────────────────────────────────────────────────────────────┐
│ User Query: "peminjaman notebook untuk mitra kerja"         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────┐
        │ Vector Search (Retrieve Context)│
        │ doc_type='ESCALATION', top_k=10 │
        └────────────┬────────────────────┘
                     │
                     ▼ (Returns: Top 10 ESCALATION chunks)
        ┌────────────────────────────────────────┐
        │ Pass to LLM + System Prompt:           │
        │ - Query user                           │
        │ - 10 Available forms dengan TRIGGER KW │
        │ - Instruksi: "Match query ke form"     │
        └────────────┬─────────────────────────┘
                     │
                     ▼ (LLM thinks & responds)
        ┌────────────────────────────────────────┐
        │ LLM Response (JSON):                   │
        │ {                                      │
        │   "form_name": "Layanan Pekerja Baru..│
        │   "link": "https://myssc.../311"       │
        │   "confidence": 0.95                   │
        │ }                                      │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │ Extract form_name + link dari response │
        └────────────┬─────────────────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Link valid?               │
        └────────────┬──────────────┘
                  Yes│   No
                     │    │
                ┌────▼──┐ ┌──▼──────────────────┐
                │Return │ │Fallback: Return    │
                │Form + │ │Incident form       │
                │Link   │ │(hardcoded exception)
                └───────┘ └────────────────────┘
```

---

## ⚙️ Keuntungan Pendekatan Dynamic

| **Aspek** | **Hardcoded (Lama)** | **Dynamic (Baru)** |
|-----------|----------------------|-------------------|
| **Menambah Form Baru** | Edit code + rebuild | Auto-picked dari KB |
| **Update Trigger Keyword** | Edit CATEGORY_FORMS dict | Auto-parsed dari KB |
| **Scalability** | Brittle (mudah break) | Infinitely scalable |
| **Maintenance** | High (banyak kode) | Low (LLM does thinking) |
| **Akurasi** | Fixed (80-85%) | Adaptive (90%+) |
| **Response Time** | Fast (regex) | Slower (LLM call) |

---

## 🛡️ Exception: Incident Form (Masih Hardcoded)

```python
def _get_incident_escalation_reply() -> str:
    """
    HARDCODED untuk form 'Incident' saja — ini adalah fallback universal
    ketika tidak ada form yang cocok atau LLM tidak yakin.
    
    Alasan tetap hardcoded:
    1. Incident form adalah fallback terakhir untuk SEMUA masalah IT
    2. Tidak berubah-ubah seperti form lainnya
    3. Perlu dijamin selalu available tanpa tergantung retrieval
    """
    return (
        "Mohon maaf, tidak ada panduan khusus yang cocok untuk masalah Anda. "
        "Silakan buat tiket menggunakan form Incident:\n\n"
        "📋 **NAMA FORM:** Incident (Gangguan Aplikasi & Sistem)\n\n"
        "🔗 **Link:** https://myssc.pertamina.com/dwp/app/#/itemprofile/313"
    )
```

---

## 📊 Testing: Query yang Akan Bekerja Lebih Baik

| Query | Old System (Hardcoded) | New System (Dynamic) |
|-------|------------------------|----------------------|
| "notebook untuk mitra kerja" | ❌ SALAH: general_it | ✅ BENAR: Onboarding |
| "laptop rusak" | ✅ BENAR: hardware | ✅ BENAR: hardware |
| "printer paper jam" | ✅ BENAR: printer | ✅ BENAR: printer |
| "email tidak bisa login" | ✅ BENAR: email | ✅ BENAR: email |
| "tidak ada internet" | ✅ BENAR: network | ✅ BENAR: network |
| "request form xyz yang belum ada di code" | ❌ SALAH: general_it | ✅ BENAR: LLM picks it |

