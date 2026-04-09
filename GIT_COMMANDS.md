# 📝 Git Commands - Siap Dijalankan

## Status Saat Ini
- **Branch**: `feature/test-evaluasi-fungsi-perbaikan-backend`
- **Staged Files**: 3 files
  - `MIGRATION_FIX_SUMMARY.md` (new)
  - `apps/chatbot/urls.py` (modified)
  - `config/urls.py` (modified)

---

## 1️⃣ COMMIT & PUSH - Ke Branch Saat Ini

### Commit changes:
```bash
git commit -m "fix: resolve migration warning dan URL namespace conflict

- Hapus duplikasi include dari apps/chatbot/urls.py
- Refactor URL structure: pisahkan template dan API endpoints
- Tamabahan explicit namespace di config/urls.py
- Dokumentasi dalam MIGRATION_FIX_SUMMARY.md
- Semua 37 migrations berhasil di-apply
- Tidak ada lagi URL namespace warning"
```

### Push ke remote:
```bash
git push origin feature/test-evaluasi-fungsi-perbaikan-backend
```

---

## 2️⃣ CREATE & SWITCH - Branch Baru

### Option A: Buat branch dari feature branch saat ini
```bash
# Buat branch baru berdasarkan feature branch saat ini
git checkout -b "feature/migration-url-fix"

# Push branch baru ke remote
git push -u origin feature/migration-url-fix
```

### Option B: Buat branch dari main
```bash
# Kembali ke main
git checkout main

# Update main dengan latest
git pull origin main

# Buat branch baru dari main
git checkout -b "feature/migration-url-fix"

# Push branch baru ke remote
git push -u origin feature/migration-url-fix
```

### Option C: Buat branch dengan nama custom
```bash
git checkout -b "feature/perbaikan-migrations-url-routing"
git push -u origin feature/perbaikan-migrations-url-routing
```

---

## 3️⃣ QUICK COMMANDS - Copy-Paste Ready

### Commit & Push (current branch):
```bash
git commit -m "fix: migration warning dan URL namespace conflict" && git push origin feature/test-evaluasi-fungsi-perbaikan-backend
```

### Create & Push (new branch dari current):
```bash
git checkout -b "feature/migration-url-fix" && git push -u origin feature/migration-url-fix
```

### Create & Push (from main):
```bash
git checkout main && git pull origin main && git checkout -b "feature/migration-url-fix" && git push -u origin feature/migration-url-fix
```

---

## 4️⃣ STEP-BY-STEP EXECUTION

### Step 1: Commit changes
```
git commit -m "fix: migration warning dan URL namespace conflict"
```

### Step 2: Push ke branch saat ini
```
git push origin feature/test-evaluasi-fungsi-perbaikan-backend
```

### Step 3: View branches
```
git branch -a
```

### Step 4: Create branch baru
```
git checkout -b feature/migration-url-fix
```

### Step 5: Push branch baru
```
git push -u origin feature/migration-url-fix
```

---

## 5️⃣ BRANCH NAMING CONVENTIONS

Choose salah satu naming convention:

| Pattern | Example | Untuk |
|---------|---------|-------|
| `feature/...` | `feature/migration-url-fix` | Feature/enhancement baru |
| `fix/...` | `fix/migration-warning` | Bug fixes |
| `docs/...` | `docs/migration-guide` | Documentation |
| `refactor/...` | `refactor/url-structure` | Code refactoring |

---

## 6️⃣ HELPFUL COMMANDS

### View pending commits:
```bash
git log --oneline -5
```

### View all branches:
```bash
git branch -a
```

### View branch tracking:
```bash
git branch -vv
```

### Switch between branches:
```bash
git checkout feature/migration-url-fix
git checkout main
```

### Delete local branch:
```bash
git branch -d feature/migration-url-fix
```

### Delete remote branch:
```bash
git push origin --delete feature/migration-url-fix
```

---

## ✅ Recommended Workflow

```
1. Commit current changes:
   git commit -m "fix: migration warning dan URL namespace conflict"

2. Push to current branch:
   git push origin feature/test-evaluasi-fungsi-perbaikan-backend

3. Create & push new branch:
   git checkout -b feature/migration-url-fix
   git push -u origin feature/migration-url-fix

4. Switch to main (optional):
   git checkout main
   git pull origin main
```

---

## 🔗 GitHub URLs

- **Current Branch**: https://github.com/polinamic/Chatbot-Pertamina/tree/feature/test-evaluasi-fungsi-perbaikan-backend
- **Create PR**: https://github.com/polinamic/Chatbot-Pertamina/pull/new/feature/test-evaluasi-fungsi-perbaikan-backend

---

## 📌 Notes

- Flag `-u` pada `git push -u` membuat branch tracking otomatis
- Gunakan `--force` hanya jika benar-benar perlu (dangerous!)
- Selalu pull sebelum push untuk menghindari conflict
