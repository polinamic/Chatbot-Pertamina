import re
import ollama


# ---------------------------------------------------------------------------
# 1. KEYWORD REGISTRIES
#    Dipisah per kategori agar mudah di-maintain tanpa menyentuh logika inti.
# ---------------------------------------------------------------------------

# Kata kerja / frasa transaksional yang secara MUTLAK menunjukkan pengadaan.
# Urutan tidak penting — semua diperiksa secara paralel via regex.
ORDER_KEYWORDS: list[str] = [
    r"\bpesan(in|kan)?\b",
    r"\border\b",
    r"\bminta(in|kan)?\b",
    r"\bpengadaan\b",
    r"\btambah(kan)?\b",
    r"\bbelikan\b",
    r"\bbeliin\b",
    r"\bbeli\b",
    r"\bprocurement\b",
    r"\brequest\b",
    r"\bpermintaan\b",
    r"\bpenyediaan\b",
    r"\bsediakan\b",
    r"\bpengajuan\b",
    r"\bajukan\b",
    r"\bbaru\b",          # "baru" sebagai adjektif pengadaan, mis. "laptop baru"
    r"\bunit baru\b",
    r"\btambahan\b",
]

# Kata yang mengindikasikan kerusakan / insiden.
# Digunakan di tahap LLM prompt & sebagai sinyal konflik.
INCIDENT_KEYWORDS: list[str] = [
    r"\bruSAK\b",
    r"\brusak(nya)?\b",
    r"\berror\b",
    r"\bgangguan\b",
    r"\btidak bisa\b",
    r"\bnggak bisa\b",
    r"\bgak bisa\b",
    r"\bmati\b",
    r"\bproblem\b",
    r"\bmasalah\b",
    r"\bhilang\b",
    r"\bkehilangan\b",
    r"\btrouble\b",
    r"\bbuggy\b",
    r"\bbox mati\b",
    r"\bkonslet\b",
    r"\blemot\b",
    r"\blambat\b",
]


# ---------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase + hapus tanda baca agar regex lebih konsisten."""
    return text.lower().strip()


def _match_any(text: str, patterns: list[str]) -> bool:
    """Return True jika salah satu pattern cocok dengan text."""
    normalized = _normalize(text)
    return any(re.search(p, normalized, re.IGNORECASE) for p in patterns)


def _has_conflict(text: str) -> bool:
    """
    [DEPRECATED] Deteksi apakah query mengandung SEKALIGUS sinyal order DAN sinyal incident.
    
    Tidak lagi digunakan — sistem prioritas ORDER keywords sekarang mengatasi konflik
    dengan cara eksplisit (order keywords override incident keywords), bukan dengan
    deferral ke LLM.
    
    Contoh konflik lama: "Laptop baru saya rusak" — ada 'baru' (order?) dan 'rusak' (incident).
    Solusi baru: Deteksi 'baru' (order keyword) → langsung ORDER_LINK (tidak di-defer ke LLM).
    """
    has_order = _match_any(text, ORDER_KEYWORDS)
    has_incident = _match_any(text, INCIDENT_KEYWORDS)
    return has_order and has_incident


# ---------------------------------------------------------------------------
# 3. PRE-FILTER — LAPISAN DETERMINISTIK (TIDAK MEMANGGIL LLM)
# ---------------------------------------------------------------------------

def _pre_filter(question: str) -> str | None:
    """
    Periksa apakah intent bisa ditentukan secara deterministik.
    
    PRIORITY: Transactional/procurement keywords override damage/incident keywords.
    Contoh: "Kartu corporate saya rusak, mau request ganti sim card baru"
    → Has "rusak" (incident) BUT has "request", "ganti", "baru" (order keywords)
    → Correctly classified as ORDER_LINK (user wants REPLACEMENT, not troubleshooting)

    Return:
        "ORDER_LINK"    → yakin ini pengadaan (highest priority)
        "INCIDENT_LINK" → yakin ini laporan kerusakan (tanpa sinyal order)
        None            → tidak conclusive, serahkan ke LLM
    """
    # PRIORITY 1: Check ORDER keywords FIRST — transactional intent has highest priority
    # If procurement/request keywords found, classify immediately as ORDER_LINK
    # even if damage/incident keywords also present
    if _match_any(question, ORDER_KEYWORDS):
        return "ORDER_LINK"

    # PRIORITY 2: Check INCIDENT keywords only if no order keywords found
    if _match_any(question, INCIDENT_KEYWORDS):
        return "INCIDENT_LINK"

    # PRIORITY 3: No clear signals — defer to LLM for context-aware classification
    return None  # fallback ke LLM


# ---------------------------------------------------------------------------
# 4. LLM CLASSIFIER — FALLBACK DENGAN FEW-SHOT PROMPT
# ---------------------------------------------------------------------------

_CLASSIFICATION_PROMPT = """
Anda adalah sistem klasifikasi intent untuk IT Helpdesk perusahaan.
Klasifikasikan pertanyaan berikut ke salah satu kategori:

ORDER_LINK    → Permintaan pengadaan, pembelian, atau penambahan barang/layanan baru.
INCIDENT_LINK → Laporan kerusakan, gangguan, atau masalah pada perangkat/layanan yang sudah ada.
GENERAL_IT    → Pertanyaan umum seputar IT yang bukan order maupun insiden.
NON_IT        → Di luar topik IT sama sekali.

ATURAN PENTING:
- Jika kalimat mengandung KATA KERJA pengadaan (pesan, order, minta, beli, tambah, sediakan, dll.)
  meskipun barangnya biasa muncul di laporan kerusakan (HT, laptop, printer, dll.),
  TETAP klasifikasikan sebagai ORDER_LINK.
- Kehadiran nama barang keras (HT, radio, laptop) BUKAN penentu utama — KATA KERJAlah yang menentukan.
- Kata "baru" yang merujuk pada unit/perangkat baru = sinyal ORDER_LINK.

CONTOH:
Q: "Pesenin HT baru buat security dong"        → ORDER_LINK
Q: "HT tim security mati, tolong dicek"        → INCIDENT_LINK
Q: "Request tambahan unit laptop untuk divisi" → ORDER_LINK
Q: "Laptop saya nggak bisa nyala"              → INCIDENT_LINK
Q: "Cara setting VPN gimana?"                  → GENERAL_IT
Q: "Tolong pesan kue ulang tahun"              → NON_IT

Jawab HANYA dengan satu kata dari pilihan: ORDER_LINK / INCIDENT_LINK / GENERAL_IT / NON_IT

Pertanyaan: {question}
"""


def _llm_classify(question: str) -> str:
    """Panggil LLM untuk klasifikasi; return label yang sudah di-strip."""
    prompt = _CLASSIFICATION_PROMPT.format(question=question)
    response = ollama.chat(
        model="llama3:8b",
        messages=[{"role": "user", "content": prompt}],
        options={
            "temperature": 0.0,   # Deterministic — tidak butuh kreativitas di sini
            "num_predict": 10,    # Label pendek, tidak perlu token banyak
        }
    )
    raw = response["message"]["content"].strip()

    # Sanitasi: ambil kata pertama saja untuk mencegah respons verbose
    first_token = raw.split()[0].upper() if raw else "GENERAL_IT"

    valid_labels = {"ORDER_LINK", "INCIDENT_LINK", "GENERAL_IT", "NON_IT"}
    return first_token if first_token in valid_labels else "GENERAL_IT"


# ---------------------------------------------------------------------------
# 5. PUBLIC API
# ---------------------------------------------------------------------------

def classify_intent(question: str) -> str:
    """
    Klasifikasikan intent query ke salah satu dari:
        ORDER_LINK | INCIDENT_LINK | GENERAL_IT | NON_IT

    Alur:
        1. Pre-filter deterministik (keyword-based) → cepat, gratis, zero-latency
        2. Jika pre-filter tidak conclusive → fallback ke LLM dengan prompt few-shot

    Args:
        question: Kalimat input dari user.

    Returns:
        String label intent.
    """
    # Tahap 1: Pre-filter
    pre_result = _pre_filter(question)
    if pre_result is not None:
        return pre_result

    # Tahap 2: LLM fallback
    return _llm_classify(question)


# Alias backward-compatible dengan nama fungsi lama di codebase lain
def classify_domain(question: str) -> str:
    """
    Alias untuk classify_intent().
    Dipertahankan untuk kompatibilitas mundur — arahkan ke classify_intent.
    """
    return classify_intent(question)


# ---------------------------------------------------------------------------
# 6. QUICK SMOKE TEST (jalankan langsung: python intent_service.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        # (input, expected_label)
        ("Tolong dong pesenin HT baru sama charger-nya buat tim security di lapangan", "ORDER_LINK"),
        ("HT tim security rusak, tolong bantu cek",                                    "INCIDENT_LINK"),
        ("Minta tambahan unit laptop untuk onboarding karyawan baru bulan depan",      "ORDER_LINK"),
        ("Printer di lantai 3 error, nggak bisa ngeprint",                             "INCIDENT_LINK"),
        ("Order 2 unit radio komunikasi untuk divisi warehouse",                        "ORDER_LINK"),
        ("Cara setting VPN dari rumah gimana?",                                         "GENERAL_IT"),
        ("Tolong pesan nasi box untuk rapat besok",                                    "NON_IT"),
        # Kasus konflik — diserahkan ke LLM
        ("Laptop baru saya yang baru dibeli minggu lalu sudah rusak",                  "INCIDENT_LINK"),
    ]

    print(f"{'INPUT':<65} {'EXPECTED':<15} {'RESULT':<15} {'STATUS'}")
    print("-" * 110)

    passed = 0
    for question, expected in test_cases:
        result = classify_intent(question)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        if result == expected:
            passed += 1
        print(f"{question:<65} {expected:<15} {result:<15} {status}")

    print("-" * 110)
    print(f"Score: {passed}/{len(test_cases)}")