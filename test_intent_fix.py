#!/usr/bin/env python
"""
Test intent classification fix for SERVICE_ORDER detection.

The issue: "Tolong dong pesenin HT (Handy Talky) baru" was being misclassified
as INCIDENT instead of SERVICE_ORDER.

The fix:
1. Updated regex pattern to catch colloquial forms like "pesenin" (pesan\w*)
2. Added explicit HT/handset/handy-talky keywords
3. Added "BARU" (new) keyword detection
4. Enhanced LLM system prompt with examples
"""

import re
import sys

# Updated pattern from chat_service.py
_SERVICE_ORDER_PATTERNS = re.compile(
    r'(?:'
    # "pesan X" / "pesenin X" / "order X" — pemesanan item dengan/tanpa kata depan
    # Catches: pesan, pesenin, pesen, order, pinjam, peminjaman, dll
    r'(?:mau\s+|ingin\s+|minta\s+|butuh\s+|perlu\s+|tolong\s+)?(?:pesen|pesan|order|pinjam|peminjaman)\w*\s+\w+'
    # "baru" keyword di tengah atau akhir kalimat menunjukkan pengadaan item baru
    r'|\b(?:HT|handset|handy.?talky|laptop|notebook|tablet|printer|monitor|mouse|keyboard|headset|webcam|cctv|kamera|proyektor|switch|router|server|harddisk|ssd|memori|keyboard|perangkat)\b.*\bBARU\b'
    # "pasang X" — pemasangan fisik perangkat/layanan IT
    r'|pasang\s+(?:wifi|wi-fi|cctv|kamera|jaringan|telepon|printer|proyektor|internet|vpn|lan|switch|access\s*point)'
    # "pengadaan X" — permintaan pengadaan resmi
    r'|\bpengadaan\b'
    # "ajukan/pengajuan perangkat/layanan" — formulir pengajuan
    r'|\b(?:ajukan|pengajuan)\s+(?:perangkat|layanan|akses|hardware|software|laptop|komputer|printer|cctv|handset|HT)'
    r')',
    re.IGNORECASE,
)

# Test cases
test_queries = [
    ("Tolong dong pesenin HT (Handy Talky) baru", True, "Original failing case"),
    ("pesan printer baru", True, "Simple pesan + baru"),
    ("order cctv", True, "order keyword"),
    ("pasang wifi di ruang meeting", True, "pasang keyword"),
    ("pengadaan laptop", True, "pengadaan keyword"),
    ("minta handset baru", True, "minta + handset + baru"),
    ("butuh tablet baru untuk tim", True, "butuh + tablet + baru"),
    ("wifi saya tidak bisa konek", False, "IT_PROBLEM - should NOT match"),
    ("keyboard tidak berfungsi", False, "IT_PROBLEM - should NOT match"),
    ("bagaimana cara kerja VPN", False, "OUT_OF_SCOPE - should NOT match"),
    ("halo", False, "GENERAL_CHAT - should NOT match"),
]

print("=" * 80)
print("SERVICE_ORDER Intent Classification Test")
print("=" * 80)
print()

passed = 0
failed = 0

for query, should_match, description in test_queries:
    match = _SERVICE_ORDER_PATTERNS.search(query)
    is_matched = match is not None
    
    status = "✓ PASS" if is_matched == should_match else "✗ FAIL"
    if is_matched == should_match:
        passed += 1
    else:
        failed += 1
    
    print(f"{status} | {description}")
    print(f"        Query: '{query}'")
    print(f"        Expected: {'MATCH' if should_match else 'NO MATCH'} | Got: {'MATCH' if is_matched else 'NO MATCH'}")
    if match:
        print(f"        Matched: '{match.group(0)}'")
    print()

print("=" * 80)
print(f"Results: {passed} passed, {failed} failed out of {len(test_queries)} tests")
print("=" * 80)

sys.exit(0 if failed == 0 else 1)
