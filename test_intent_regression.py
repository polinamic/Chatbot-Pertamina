import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.disable(logging.CRITICAL)

from apps.rag.services.chat_service import detect_intent
from apps.rag.services.embedding import EmbeddingService

embedding_service = EmbeddingService()

# Test that regular IT problems still detect correctly
test_cases = [
    ("wifi saya tidak bisa konek", "IT_PROBLEM", "WiFi connectivity issue"),
    ("akses pintu error", "IT_PROBLEM", "Access door error"),
    ("install software please", "IT_PROBLEM", "Software installation"),
    ("buat tiket", "REQUEST_IT_SUPPORT", "Create ticket request"),
    ("link untuk buat tiket", "REQUEST_IT_SUPPORT", "Link for ticket"),
    ("tolong hubungi IT", "REQUEST_IT_SUPPORT", "Call IT support"),
    ("terima kasih", "GENERAL_CHAT", "Thank you"),
]

print("=" * 70)
print("INTENT DETECTION REGRESSION TEST")
print("=" * 70)
print()

passed = 0
failed = 0

for query, expected_intent, description in test_cases:
    actual_intent = detect_intent(query, embedding_service)
    status = "PASS" if actual_intent == expected_intent else "FAIL"
    
    if status == "PASS":
        passed += 1
        symbol = "[OK]"
    else:
        failed += 1
        symbol = "[XX]"
    
    print("{} {}".format(symbol, description))
    print("  Query: {}".format(query))
    print("  Expected: {}".format(expected_intent))
    print("  Actual: {}".format(actual_intent))
    print()

print("=" * 70)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 70)

if failed == 0:
    print("All tests PASSED! No regressions detected.")
else:
    print(f"WARNING: {failed} test(s) failed!")
