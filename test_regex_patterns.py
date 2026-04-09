import re

pattern = re.compile(
    r'\b(hubungi|bicara dengan|minta tolong|it support|operator|teknisi|'
    r'helpdesk|eskalasi|bantuan manusia|'
    r'buat tiket|buatkan tiket|membuat tiket|cara membuat tiket|'
    r'link tiket|form|panduan tiket|escalat)\b',
    re.IGNORECASE,
)

test_strings = [
    "bertu buatlah tiketnya, bagi link untuk membuat tiketnya aja",
    "buat tiket",
    "membuat tiket",
    "cara membuat tiket",
    "buatlah tiket",
]

for test in test_strings:
    result = pattern.search(test)
    print("Query: " + test)
    if result:
        print("  MATCH: " + result.group())
    else:
        print("  NO MATCH")
    print()
