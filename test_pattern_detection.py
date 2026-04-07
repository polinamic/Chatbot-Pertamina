#!/usr/bin/env python
"""
Simple Pattern Test untuk Intent Detection
Hanya test rule-based detection tanpa LLM
"""
import re

# Copy dari chat_service.py
_NON_IT_INTENT_PATTERNS = re.compile(
    r'\b(siapa\s+(pencipta|penemu|pembuat|pendiri|yang\s+menciptakan)|'
    r'sejarah|asal.usul|kapan\s+ditemukan|kapan\s+diciptakan|'
    r'jokes?|humor|lucu|cerita\s+lucu|meme|'
    r'resep|masak|makanan|minuman|kuliner|restoran|'
    r'presiden|gubernur|bupati|politik|pemilu|'
    r'bola|olahraga|liga|pertandingan|skor|'
    r'artis|film|lagu|musik|konser|'
    r'cuaca|ramalan|zodiak|horoskop|'
    r'matematika|fisika|kimia|biologi|geografi|'
    r'harga\s+saham|crypto|bitcoin|investasi|'
    r'origami|kerajinan|craft|diy|mainan|permainan|'
    r'tutorial\s+(membuat|membentuk|menghias)|'
    r'cara\s+membuat\s+(boneka|mainan|hiasan)|'
    r'panduan\s+(seni|melukis|menyanyi|menari)|'
    r'pelajaran\s+(matematika|bahasa|seni|musik)|'
    r'berikanlah.*tutorial|berikanlah.*panduan|berikanlah.*cara\s+membuat|'
    r'coret|baret|lecet|goresan|cacat\s+fisik|rusak\s+fisik|pecah|penyok|kotor|'
    r'membersihkan|merawat|memoles|poles|lap|gosok|cuci|'
    r'cara\s+(membersihkan|merawat|memoles)\s+(laptop|komputer|perangkat|monitor|keyboard|printer|mouse|debu)|'
    r'tuhan|agama|kepercayaan|filsafat|filosofi|etika|makna\s+hidup|spiritual|metafisika|esoterik|nihilisme|psikologi|'
    r'(?:tv|televisi|hp|handphone|dompet|motor|mobil)\s+(?:saya\s+)?hilang)\b',
    re.IGNORECASE
)

# Test cases yang harus di-detect sebagai OUT_OF_SCOPE oleh pattern
TEST_OUT_OF_SCOPE = [
    "berikanlah kami tutorial untuk membuat mainan kertas origami pesawat",
    "tutorial membuat boneka dari kain",
    "cara membuat hiasan dinding",
    "panduan melukis bunga",
    "siapa pencipta wifi",
    "jokes tentang laptop",
    "resep nasi goreng",
    "origami pesawat",
    "kerajinan tangan dari kertas",
    "DIY lamp dari botol",
    "panduan seni melukis",
    # NEW: Physical hardware maintenance/cleaning ← FIX FOR NEW ISSUE
    "komputer saya di coret bagaimana cara membersilahkannya",
    "laptop saya lecet dan rusak fisik",
    "cara membersihkan keyboard laptop",
    "laptop saya baret gimana",
    "cara merawat monitor komputer",
    "monitor saya pecah bisa diperbaiki tidak",
    "keyboard saya kotor cara membersihkannya gimana",
    "printer saya terlihat bersih bagaimana cara memoles bodi",
    "cara membersihkan debu dari keyboard",
    "apakah tuhan ada",
    "tv saya hilang gimana cara lapornya",
]

# Test cases yang TIDAK harus di-detect sebagai OUT_OF_SCOPE
TEST_NOT_OUT_OF_SCOPE = [
    "bagaimana cara reset password laptop",  # IT problem
    "wifi saya tidak bisa konek",  # IT problem
    "laptop saya lambat",  # IT problem
    "printer tidak terdeteksi",  # IT problem
    "tutorial menggunakan VPN",  # Edges: bisa dianggap masalah IT practical
    "keyboard tidak berfungsi",  # IT PROBLEM (malfunction), bukan physical damage
    "monitor tidak menyala",  # IT PROBLEM, bukan physical damage
]

print("=" * 80)
print("PATTERN DETECTION TEST - OUT_OF_SCOPE")
print("=" * 80)

print("\n1. TEST: Pertanyaan yang HARUS terdeteksi sebagai OUT_OF_SCOPE")
print("-" * 80)
passed = 0
failed = 0

for question in TEST_OUT_OF_SCOPE:
    match = _NON_IT_INTENT_PATTERNS.search(question)
    if match:
        status = "✓ PASS"
        passed += 1
    else:
        status = "✗ FAIL"
        failed += 1
    
    print(f"{status}: {question}")
    if match:
        print(f"        Matched: {match.group()}")

print("\n" + "." * 80)
print(f"RESULT: {passed}/{len(TEST_OUT_OF_SCOPE)} passed\n")

print("2. TEST: Pertanyaan yang TIDAK boleh terdeteksi sebagai OUT_OF_SCOPE")
print("-" * 80)

passed2 = 0
failed2 = 0

for question in TEST_NOT_OUT_OF_SCOPE:
    match = _NON_IT_INTENT_PATTERNS.search(question)
    if not match:
        status = "✓ PASS"
        passed2 += 1
    else:
        status = "✗ FAIL (false positive)"
        failed2 += 1
    
    print(f"{status}: {question}")
    if match:
        print(f"        Incorrectly matched: {match.group()}")

print("\n" + "." * 80)
print(f"RESULT: {passed2}/{len(TEST_NOT_OUT_OF_SCOPE)} passed")

print("\n" + "=" * 80)
total_passed = passed + passed2
total_tests = len(TEST_OUT_OF_SCOPE) + len(TEST_NOT_OUT_OF_SCOPE)
print(f"OVERALL: {total_passed}/{total_tests} tests passed")
print("=" * 80)

if failed == 0 and failed2 == 0:
    print("\n✓ All pattern detection tests PASSED!")
    exit(0)
else:
    print(f"\n✗ {failed + failed2} test(s) FAILED!")
    exit(1)
