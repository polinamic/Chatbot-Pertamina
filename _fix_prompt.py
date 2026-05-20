"""
Patch script v3: inject VERBATIM extraction rules into the LLM extraction prompt.
Works by finding the unique anchor text, then splicing in the new block.
"""
PATH = r"apps\rag\services\chat_service.py"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Find the arrow and em-dash by their context inside the prompt block
PROMPT_START = src.find('"ATURAN WAJIB:\\\\n"')
if PROMPT_START < 0:
    print("ERROR: Cannot find prompt start marker.")
    exit(1)

# Find "fisik " followed by the em-dash char in the prompt block
# Line: "3. 'kartu akses'...adalah item fisik X HARUS"
marker = "adalah item fisik "
idx = src.find(marker, PROMPT_START)
D = src[idx + len(marker)]   # em-dash character
print(f"Em-dash: U+{ord(D):04X}  repr={repr(D)}")

# Find the arrow char: appears in "kertas' X items"
marker2 = "'kertas' "
idx2 = src.find(marker2, PROMPT_START)
A = src[idx2 + len(marker2)]
print(f"Arrow:   U+{ord(A):04X}  repr={repr(A)}")

# ── Locate block boundaries ────────────────────────────────────────────────
START_MARKER = '"ATURAN WAJIB:\\\\n"'
END_MARKER   = '"Jangan sertakan teks apapun selain JSON."'

start_idx = src.find(START_MARKER, PROMPT_START)
end_idx   = src.find(END_MARKER, start_idx) + len(END_MARKER)

print(f"Block: [{start_idx}:{end_idx}]  len={end_idx-start_idx}")

NEW_BLOCK = "\n".join([
    '"ATURAN WAJIB:\\\\n"',
    f'        "1. Ekstrak SEMUA noun/benda: hardware, software, consumable, ATK, supplies, akses fisik.\\\\n"',
    f'        "2. JANGAN filter item hanya karena terdengar seperti office supplies biasa.\\\\n"',
    f'        "3. \'kartu akses\', \'access card\', \'ID card\' adalah item fisik {D} HARUS diekstrak.\\\\n"',
    f'        "4. \'kertas\' {A} items: [\'kertas\']. \'tinta\' {A} items: [\'tinta\']. \'baterai\' {A} items: [\'baterai\'].\\\\n"',
    f'        "5. \'ATK\' atau \'alat tulis\' {A} items: [\'ATK\'].\\\\n"',
    f'        "6. Array KOSONG HANYA jika tidak ada SATU PUN objek fisik dalam kalimat (e.g., \'saya mau pesan\', \'orderin dong\').\\\\n\\\\n"',
    f'        "ATURAN KRITIS {D} EKSTRAK VERBATIM (WAJIB DIIKUTI 100%):\\\\n"',
    f'        "7. SALIN kata-kata item PERSIS seperti yang ditulis user. DILARANG menerjemahkan ke Bahasa Inggris.\\\\n"',
    f'        "8. DILARANG merangkum, menyederhanakan, atau mengganti frasa user dengan sinonim Bahasa Inggris.\\\\n"',
    f'        "9. Jika user menulis frasa multi-kata (mis. \'access control pintu\'), salin SELURUH frasa apa adanya.\\\\n"',
    f'        "10. CONTOH KESALAHAN FATAL yang DILARANG:\\\\n"',
    f'        "    \'access control pintu\' {A} JANGAN ubah jadi \'access card\' atau \'access control\'. WAJIB: \'access control pintu\'.\\\\n"',
    f'        "    \'kartu akses mahasiswa\' {A} JANGAN ubah jadi \'ID card\' atau \'access card\'. WAJIB: \'kartu akses mahasiswa\'.\\\\n\\\\n"',
    f'        "CONTOH FEW-SHOT (analisis HANYA kalimat yang diberikan, tanpa konteks lain):\\\\n"',
    f'        "  \'pesan printer baru\'                                            {A} {{\\\"items\\\": [\\\"printer\\\"]}}\\\\n"',
    f'        "  \'order kertas untuk divisi retail\'                              {A} {{\\\"items\\\": [\\\"kertas\\\"]}}\\\\n"',
    f'        "  \'saya mau melakukan order kertas untuk kebutuhan divisi retail\'  {A} {{\\\"items\\\": [\\\"kertas\\\"]}}\\\\n"',
    f'        "  \'minta toner dan flashdisk\'                                     {A} {{\\\"items\\\": [\\\"toner\\\", \\\"flashdisk\\\"]}}\\\\n"',
    f'        "  \'pengadaan ATK kantor\'                                          {A} {{\\\"items\\\": [\\\"ATK\\\"]}}\\\\n"',
    f'        "  \'mau order baterai untuk remote AC\'                             {A} {{\\\"items\\\": [\\\"baterai\\\"]}}\\\\n"',
    f'        "  \'saya ingin meminta kartu akses baru\'                           {A} {{\\\"items\\\": [\\\"kartu akses\\\"]}}\\\\n"',
    f'        "  \'butuh access card untuk lantai 3\'                              {A} {{\\\"items\\\": [\\\"access card\\\"]}}\\\\n"',
    f'        "  \'pesan access control pintu untuk ruang server\'                 {A} {{\\\"items\\\": [\\\"access control pintu\\\"]}}\\\\n"',
    f'        "  \'pengajuan access control pintu dan CCTV\'                       {A} {{\\\"items\\\": [\\\"access control pintu\\\", \\\"CCTV\\\"]}}\\\\n"',
    f'        "  \'mau mengajukan kartu akses baru untuk mahasiswa magang\'        {A} {{\\\"items\\\": [\\\"kartu akses\\\"]}}\\\\n"',
    f'        "  \'saya mau order\'                                                {A} {{\\\"items\\\": []}}\\\\n\\\\n"',
    f'        "FORMAT OUTPUT: Jawab HANYA dengan JSON. Contoh: {{\\\"items\\\": [\\\"printer\\\"]}}\\\\n"',
    f'        "Jangan sertakan teks apapun selain JSON."',
])

patched = src[:start_idx] + NEW_BLOCK + src[end_idx:]

with open(PATH, "w", encoding="utf-8") as f:
    f.write(patched)

print("SUCCESS: file written.")
if "access control pintu" in patched and "EKSTRAK VERBATIM" in patched:
    print("VERIFY OK: new rules confirmed.")
else:
    print("WARNING: spot-check failed after write.")
