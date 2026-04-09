# Admin Dashboard - Knowledge Base Upload Visual Guide

## 📍 Location
**URL:** `http://localhost:8000/dashboard/knowledge-base/`  
**Access:** Admin/Staff users only  
**Permission:** `@user_passes_test(is_admin_or_staff)`

---

## 🖼️ Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  📚 Knowledge Base Manager                [📤 Upload Panduan Baru] │
│  Upload & manage panduan troubleshooting dan eskalasi...          │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────┐│
│  │ Total Documents      │  │ Troubleshoot Guides  │  │Eskalasi    ││
│  │ 53                   │  │ 10                   │  │Links       ││
│  │ 📦 uploaded today: 2 │  │ 🔧 Solusi mandiri    │  │ 🔗 43      ││
│  └──────────────────────┘  └──────────────────────┘  └────────────┘│
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│ 📋 Daftar Knowledge Base                                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  File Name         │ Tipe   │ Format      │ Chunks │ Ukuran │ Aksi  │
│  ──────────────────┼────────┼─────────────┼────────┼────────┼──────  │
│  🔗 knowledge...   │ 🔗 Esk │ Direct Link │  43 ch │ 2.1 KB │ [🗑️]  │
│  🔧 knowledge...   │ 🔧 TS  │ KATEGORI    │  10 ch │ 1.8 KB │ [🗑️]  │
│  ──────────────────┼────────┼─────────────┼────────┼────────┼──────  │
│                                                                       │
│                  [«First] [‹ Prev] [1] [2] [3] [Next›] [Last»]    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 📤 Upload Modal

```
┌──────────────────────────────────────────────────────────┐
│ Upload Document                                      [✕] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ 📋 Tipe Knowledge Base:                                 │
│ ┌──────────────────────────────────────────────────────┐│
│ │ 🔧 Langkah Troubleshooting (Solusi Mandiri)        ▼ ││
│ └──────────────────────────────────────────────────────┘│
│ <Format Hint Box with icons & borders>                  │
│                                                          │
│ 📝 Format Info:                                          │
│ ┌──────────────────────────────────────────────────────┐│
│ │ • TXT (UTF-8)                                         ││
│ │ • Max 50MB                                           ││
│ │ • UTF-8 Encoding                                     ││
│ └──────────────────────────────────────────────────────┘│
│                                                          │
│ 📌 Format yang Diterima:                                │
│ • Troubleshoot: KATEGORI: [nama] dengan langkah-langkah│
│ • Direct Link: NAMA FORM: | TRIGGER KEYWORD: | ...     │
│                                                          │
│              [⏬ Lihat Contoh Format ▼]                 │
│                                                          │
│              ┌──────────────────────────────┐           │
│              │ ☁️ Drag & drop file TXT     │           │
│              │    or click to browse        │           │
│              └──────────────────────────────┘           │
│              📁 Choose File                             │
│                                                          │
│                     Supported: TXT (UTF-8)             │
│                     Max size: 50MB                      │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ [Close]                    [📤 Upload Knowledge Base]   │
└──────────────────────────────────────────────────────────┘
```

### Format Examples (Expanded)

```
┌─────────────────────────────────────────────────────────────┐
│ ✓ Format Troubleshoot:                                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ KATEGORI JARINGAN_WIFI_LIMITED_ACCESS                  ││
│ │ Koneksi internet terbatas atau lambat saat...           ││
│ │ Langkah Perbaikan:                                      ││
│ │ 1. Tekan Windows + R                                    ││
│ │ 2. Ketik 'ncpa.cpl' lalu Enter                         ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ ✓ Format Direct Link (Baru):                             │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ ---                                                     ││
│ │ NAMA FORM: Acces Control Device                        ││
│ │ TRIGGER KEYWORD: access, control, acs, pintu           ││
│ │ PANDUAN TIKET: Untuk menghubungi tim IT silahkan...    ││
│ │ Link: https://myssc.pertamina.com/dwp/app/#/...        ││
│ │                                                         ││
│ │ ---                                                     ││
│ │ NAMA FORM: Email Configuration                         ││
│ │ TRIGGER KEYWORD: email, outlook, setup                 ││
│ │ PANDUAN TIKET: Untuk mengkonfigurasi email...          ││
│ │ Link: https://myssc.pertamina.com/dwp/app/#/...        ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Upload States

### State 1: File Selected
```
         ┌──────────────────────────────┐
         │ ✓ filename.txt               │
         │ 1.23 MB • Ready to upload    │
         └──────────────────────────────┘
```

### State 2: Uploading
```
         ┌──────────────────────────────────┐
         │ ⏳ Processing...                │
         └──────────────────────────────────┘
```

### State 3: Success
```
✅ Upload berhasil!
43 chunks diproses (🔗 Direct Link)

[Auto-reload in 1.5 seconds...]
```

### State 4: Error
```
❌ Error: Hanya file TXT (UTF-8) yang diterima
```

---

## 🗑️ Delete Confirmation

```
❓ Yakin ingin menghapus "knowledge_base_website_tiket.txt"?

Semua chunks akan dihapus dan tidak bisa dipulihkan.

[Batal] [Hapus]
```

After confirmation:
```
✅ Knowledge base dihapus (43 chunks removed)

[Auto-reload in 1.2 seconds...]
```

---

## 📊 Stats Card Example

```
┌─────────────────────────────────┐
│ 📄 Total Documents              │
│ ┌────────────────────────────── │
│ │            53                 │
│ │        ⬆ 2 KB uploaded        │
│ │        hari ini               │
│ └────────────────────────────── │
└─────────────────────────────────┘
```

---

## 📋 Table Actions

### Delete Button
```
Row: [🔗 knowledge_base_website_tiket.txt] [Direct Link] [43 ch] [2.1 KB] [🗑️ Delete]
                                                                         ↑
                                                                    Hover shows tooltip
```

---

## 🌙 Dark Mode Support

All components have dark mode styling:
- ✅ Modal background: `--gray-800` (#1f2937)
- ✅ Text color: `--text-light` (#f9fafb)
- ✅ Borders: `--gray-700` (#374151)
- ✅ Input fields: Dark background with visibility
- ✅ Format hints: Dark theme with proper contrast

---

## 🎨 Color Scheme

| Element | Light | Dark |
|---------|-------|------|
| **Troubleshoot Badge** | Green (#047857) | Green (#10b981) |
| **Escalation Badge** | Orange (#b45309) | Orange (#f59e0b) |
| **File Size Badge** | Blue (#3b82f6) with 5% opacity | Blue (#3b82f6) with 10% opacity |
| **Format Hint Box** | Blue border, 5% bg | Blue border, 10% bg |
| **Modal Background** | White (#ffffff) | Gray (#1f2937) |
| **Success (Notification)** | Green background | Green with 20% opacity |
| **Error (Notification)** | Red background | Red with 20% opacity |
| **Warning (Notification)** | Yellow background | Yellow with 20% opacity |

---

## 🚀 User Journey

```
1. Admin visits /dashboard/
                    ↓
2. Clicks "Knowledge Base" in sidebar
                    ↓
3. Loads knowledge_base.html with:
   - Stats cards (Total, Troubleshoot, Escalation)
   - Document list table
   - "Upload Panduan Baru" button
                    ↓
4. Admin clicks "Upload Panduan Baru"
                    ↓
5. Modal opens with:
   - Doc type selector (🔧 vs 🔗)
   - Format explanation
   - Drag & drop zone
   - Collapsible examples
                    ↓
6. Admin selects doc type and uploads file
                    ↓
7. JavaScript validates locally:
   - Must be TXT
   - Must be < 50MB
   - Shows file preview
                    ↓
8. Admin clicks "Upload Knowledge Base"
                    ↓
9. API call to /dashboard/api/documents/upload/
   - Server validates encoding (UTF-8)
   - Creates Document record
   - Calls ingest_document()
   - Auto-detects format
   - Returns success/error
                    ↓
10. Success notification + page reload
                    ↓
11. New KB visible in table with:
    - Icon (🔧 or 🔗)
    - Format type
    - Chunk count
    - Upload info
```

---

## 📱 Responsive Design

- ✅ Table responsive on mobile (horizontal scroll)
- ✅ Modal max-width: 90% on small screens
- ✅ Stats grid adapts to 1-3 columns based on screen
- ✅ Buttons align properly on touch devices

---

## ♿ Accessibility

- ✅ Form inputs have proper labels
- ✅ Buttons have clear purposes
- ✅ Color + icons (not just color)
- ✅ Delete confirmation prevents accidents
- ✅ Keyboard navigation supported
- ✅ ARIA labels where applicable

---

## 🔐 Security

- ✅ CSRF protection on all forms
- ✅ Login required (`@login_required`)
- ✅ Admin only (`@user_passes_test`)
- ✅ File size limit (50MB)
- ✅ File type validation (TXT only)
- ✅ Encoding validation (UTF-8)
- ✅ User ID logged on upload/delete
