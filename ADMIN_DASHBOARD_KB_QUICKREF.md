# 🚀 Admin Dashboard KB Upload - Quick Reference

**Location:** `/dashboard/knowledge-base/`  
**Access:** Admin/Staff only  
**Updated:** April 8, 2026

---

## ⚡ Quick Start

### For Admin Users
```
1. Go to Admin Dashboard
2. Click "Knowledge Base Manager" (left sidebar)
3. Click "Upload Panduan Baru" button
4. Choose format (🔧 Troubleshoot or 🔗 Direct Link)
5. Upload TXT file (UTF-8, max 50MB)
6. Done! ✅
```

### File Format Requirements
```
📄 Type: TXT only
🔤 Encoding: UTF-8 (MUST)
📏 Size: Max 50MB
```

### URL
```
http://localhost:8000/dashboard/knowledge-base/
http://your-domain/dashboard/knowledge-base/
```

---

## 📋 Knowledge Base Formats

### Format 1: Troubleshoot (🔧)
```
KATEGORI JARINGAN_WIFI_LIMITED_ACCESS
Koneksi internet terbatas atau lambat saat...

Langkah Perbaikan:
1. Tekan Windows + R
2. Ketik 'ncpa.cpl' lalu Enter
...
```

### Format 2: Direct Link (🔗) [NEW]
```
---
NAMA FORM: Acces Control Device
TRIGGER KEYWORD: access, control, acs, pintu
PANDUAN TIKET: Untuk menghubungi tim IT silahkan klik link dibawah ini.
Link: https://myssc.pertamina.com/dwp/app/#/itemprofile/101

---
NAMA FORM: Email Configuration
...
```

---

## 🎛️ Dashboard Features

### Upload Modal
- ✅ Format selector (dropdown)
- ✅ Format examples (clickable)
- ✅ Drag & drop zone
- ✅ File preview (name + size)
- ✅ Validation feedback

### Knowledge Base Table
| Column | Shows |
|--------|-------|
| File Name | KB filename |
| Tipe KB | 🔧 TS or 🔗 ESC |
| Format | Direct Link or KATEGORI |
| Chunks | Number of chunks created |
| Ukuran | File size in KB |
| Upload By | Admin username |
| Tgl Upload | Upload date |
| Aksi | Delete button |

### Statistics
- 📊 Total Documents (all KBs)
- 🔧 Troubleshoot Guides (step-by-step)
- 🔗 Eskalasi Links (direct portal)

---

## 🔧 API Endpoints

### Upload KB
```
POST /dashboard/api/documents/upload/
Content-Type: multipart/form-data

Parameters:
  - file: TXT file (UTF-8)
  - doc_type: TROUBLESHOOT or ESCALATION

Response (Success):
{
  "status": "success",
  "message": "✅ KB berhasil diupload",
  "details": "43 chunks diproses (🔗 Direct Link)",
  "document_id": 42,
  "chunks_created": 43,
  "doc_type": "ESCALATION",
  "format_detected": "Direct Link (NAMA FORM)"
}
```

### Delete KB
```
DELETE /dashboard/api/documents/delete/{document_id}/

Response (Success):
{
  "status": "success",
  "message": "✅ Knowledge base dihapus (43 chunks removed)",
  "document_id": 42,
  "chunks_removed": 43
}
```

---

## ⚠️ Common Errors & Solutions

### ❌ "Hanya file TXT (UTF-8) yang diterima"
**Problem:** Not a TXT file or wrong encoding  
**Solution:** 
1. Save file as .txt in text editor
2. Ensure encoding is UTF-8 (not ANSI, not UTF-16)
3. File → Save As → UTF-8

### ❌ "Ukuran file terlalu besar (max 50MB)"
**Problem:** File > 50MB  
**Solution:** Split into smaller files

### ❌ "File harus menggunakan encoding UTF-8"
**Problem:** Wrong character encoding  
**Solution:** Open in Notepad++, choose Encoding → UTF-8 without BOM → Save

### ❌ "Could not read file"
**Problem:** File corrupted or permissions issue  
**Solution:** Check file, try different file

---

## 🔄 Processing Steps

```
1. Choose doc type (dropdown)
   ↓
2. Select/drag file
   ↓
3. Click Upload
   ↓
4. Validation (type, size, encoding)
   ↓
5. Create Document record
   ↓
6. Auto-detect format:
   - Look for "NAMA FORM:" → Direct Link
   - Look for "KATEGORI" → KATEGORI
   ↓
7. Ingest & chunk
   ↓
8. Generate embeddings
   ↓
9. Store chunks
   ↓
10. Show success & reload
```

---

## 📊 Statistics Explained

**Total Documents**
- All KB files uploaded
- Includes both Troubleshoot & Escalation
- Changes when new KB uploaded

**Troubleshoot Guides**
- Only TROUBLESHOOT type documents
- Format: Step-by-step instructions
- Used for user self-service

**Eskalasi Links**
- Only ESCALATION type documents
- Format: Direct link to IT portal
- Used when troubleshoot fails

---

## 🛠️ Technical Columns

| Column | What It Means |
|--------|--------------|
| **Tipe KB** | 🔧 = Troubleshoot, 🔗 = Escalation |
| **Format** | Direct Link = NAMA FORM format, KATEGORI = old format |
| **Chunks** | How many pieces the KB was split into for RAG |
| **Ukuran** | How big the original TXT file is |

---

## 📱 Mobile Access

Dashboard is responsive:
- ✅ Works on phone/tablet
- ✅ Touch-friendly buttons
- ✅ Scrollable table
- ✅ Readable on small screens

---

## 🔐 Permissions

### Admin Dashboard Access
Requires: `@login_required` + `@user_passes_test(is_admin_or_staff)`

Roles with access:
- ✅ Admin
- ✅ Staff/Editor
- ❌ Regular users

---

## 🌙 Dark/Light Mode

- ✅ Both modes supported
- ✅ Auto-follows system theme
- ✅ Can toggle in dashboard
- ✅ All elements styled

---

## 📈 Monitoring

### What Gets Logged
- ✅ User who uploaded
- ✅ File name & size
- ✅ Doc type selected
- ✅ Chunks created
- ✅ Format detected
- ✅ User who deleted
- ✅ All errors

Check logs at: `VSCODE_TARGET_SESSION_LOG` or Django logs

---

## 🎯 Tips & Best Practices

### ✅ DO
- Save files in UTF-8 encoding
- Use clear, descriptive filenames
- Test format detection (examples visible)
- Delete old KBs when migrating
- Monitor chunk count (indicates coverage)

### ❌ DON'T
- Use wrong file encoding
- Upload files > 50MB
- Upload non-TXT files
- Delete KBs in production without backup
- Mix formats in single file

---

## 🔗 Related Resources

- Documentation: `/ADMIN_DASHBOARD_KB_UPDATES.md`
- Visual Guide: `/ADMIN_DASHBOARD_KB_VISUAL_GUIDE.md`
- Checklist: `/ADMIN_DASHBOARD_KB_IMPLEMENTATION_CHECKLIST.md`
- Final Summary: `/ADMIN_DASHBOARD_KB_FINAL_SUMMARY.md`

---

## 📞 Support

### Issues
1. Check error message carefully
2. Review "Common Errors" section above
3. Check file encoding (UTF-8 required)
4. Verify file is valid TXT

### Questions
- Check documentation files
- Review format examples in modal
- Contact admin/developer

---

## ⏱️ Performance

### Upload Time
- Small file (< 1MB): ~1-2 seconds
- Medium file (1-10MB): ~5-10 seconds
- Large file (10-50MB): ~15-30 seconds

### Depends On
- File size
- Number of chunks
- Embedding model (runs on CPU/GPU)
- Server load

---

## 📌 Important Notes

✅ **Format Flexible**
- Both KATEGORI and Direct Link formats work
- System auto-detects which format
- Can have both in dashboard

✅ **No Breaking Changes**
- Admin interface still works
- Command-line still works
- All existing KBs still work
- Chat functionality unchanged

✅ **Easy Recovery**
- Delete creates clean removal
- No orphaned data
- All chunks deleted with KB

---

## 🚀 Quick Commands

**For Developers (Command Line Alternative)**

```bash
# Still works as before
python manage.py ingest_kb \
  --file knowledge_base_website_tiket.txt \
  --category ESCALATION

# But now admin can use dashboard instead ✨
```

---

## 📋 Status Indicators

| Icon | Meaning |
|------|---------|
| 🔧 | Troubleshooting guide (step-by-step) |
| 🔗 | Escalation link (portal direct link) |
| 📤 | Upload button |
| 🗑️ | Delete button |
| ✅ | Success notification |
| ❌ | Error notification |
| ⏳ | Processing/Loading |

---

**Last Updated:** April 8, 2026  
**Status:** ✅ PRODUCTION READY

For full documentation, see the .md files in project root.
