#!/usr/bin/env python
"""
Test Intent Detection untuk Out-of-Scope Questions
Mengecek apakah pertanyaan non-IT terdeteksi dengan benar
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.services.chat_service import detect_intent, detect_intent_rules

# Test cases
TEST_CASES = [
    # Original bug case
    ("berikanlah kami tutorial untuk membuat mainan kertas origami pesawat", "OUT_OF_SCOPE"),
    
    # Other out-of-scope cases
    ("tutorial membuat boneka dari kain flanel", "OUT_OF_SCOPE"),
    ("cara membuat hiasan dinding dari kertas", "OUT_OF_SCOPE"),
    ("panduan melukis bunga dengan cat air", "OUT_OF_SCOPE"),
    ("siapa pencipta wifi", "OUT_OF_SCOPE"),
    ("jokes tentang laptop", "OUT_OF_SCOPE"),
    ("resep bikin nasi goreng", "OUT_OF_SCOPE"),
    
    # IT Problem cases (should still work)
    ("wifi saya tidak bisa konek", "IT_PROBLEM"),
    ("laptop saya lambat", "IT_PROBLEM"),
    ("printer tidak terdeteksi", "IT_PROBLEM"),
    ("tidak bisa login email", "IT_PROBLEM"),
    
    # General chat cases
    ("halo", "GENERAL_CHAT"),
    ("ok terima kasih", "GENERAL_CHAT"),
    
    # Edge cases
    ("bagaimana cara reset password laptop", "IT_PROBLEM"),  # IT-related
    ("bagaimana cara kerja wifi", "OUT_OF_SCOPE"),  # Edukasi, bukan masalah
]

def test_intent_detection():
    print("=" * 70)
    print("TESTING INTENT DETECTION")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for question, expected_intent in TEST_CASES:
        # Test rule-based first
        rule_result = detect_intent_rules(question)
        
        # If rule not matched, test full detect_intent (with LLM fallback)
        detected_intent = rule_result if rule_result else detect_intent(question)
        
        status = "✓ PASS" if detected_intent == expected_intent else "✗ FAIL"
        
        if detected_intent == expected_intent:
            passed += 1
        else:
            failed += 1
        
        print(f"\n{status}")
        print(f"  Q: {question}")
        print(f"  Expected: {expected_intent}")
        print(f"  Got:      {detected_intent}")
        print(f"  Rule:     {rule_result if rule_result else '(LLM fallback)'}")
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(TEST_CASES)} tests")
    print("=" * 70)
    
    return failed == 0

if __name__ == "__main__":
    success = test_intent_detection()
    sys.exit(0 if success else 1)
