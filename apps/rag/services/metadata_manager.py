"""
metadata_manager.py — Ekstrak & manage metadata dari chunks

Fungsi ini membantu mengidentifikasi kategori, tipe dokumen,
dan informasi penting lain dari chunk content untuk digunakan
dalam filtering dan relevance scoring.
"""

import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


def extract_metadata_from_chunk(chunk_content: str) -> Dict[str, any]:
    """
    Ekstrak metadata dari content chunk.
    
    Metadata yang diextract:
    - primary_category: kategori utama (dari KATEGORI: xxx)
    - sub_category: sub-kategori jika ada
    - is_escalation: True jika content adalah panduan eskalasi
    - keywords: list kata kunci penting
    - priority: HIGH/MEDIUM/LOW berdasarkan pattern tertentu
    """
    metadata = {
        "primary_category": None,
        "sub_category": None,
        "is_escalation": False,
        "keywords": [],
        "priority": "MEDIUM",
        "structure_type": None,  # TROUBLESHOOT atau ESCALATION
    }
    
    # Extract kategori utama (KATEGORI: XXXXX)
    kategori_match = re.search(r'KATEGORI:\s*([A-Za-z_]+)', chunk_content, re.IGNORECASE)
    if kategori_match:
        metadata["primary_category"] = kategori_match.group(1)
    
    # Deteksi tipe struktur (Troubleshoot vs Escalation)
    if re.search(r'Langkah\s+Perbaikan:|Langkah\s+\d+\.', chunk_content, re.IGNORECASE):
        metadata["structure_type"] = "TROUBLESHOOT"
    elif re.search(r'Panduan\s+Eskalasi|Klik\s+|menu|tombol', chunk_content, re.IGNORECASE):
        metadata["structure_type"] = "ESCALATION"
        metadata["is_escalation"] = True
    
    # Extract keywords dari chunk
    # Cari kata-kata teknis yang penting
    tech_keywords = {
        'wifi': r'\bwifi|wi-fi\b',
        'password': r'\bpassword|kata sandi\b',
        'akun': r'\bakun|account\b',
        'email': r'\bemail|outlook\b',
        'laptop': r'\blaptop|pc|komputer\b',
        'printer': r'\bprinter|cetak\b',
        'vpn': r'\bvpn\b',
        'internet': r'\binternet\b',
        'jaringan': r'\bjaringan|network\b',
        'error': r'\berror|gagal|error code\b',
        'reset': r'\breset|restart\b',
        'kerberos': r'\bkerberos|klist\b',
        'mfa': r'\bmfa|2fa|authenticator\b',
    }
    
    content_lower = chunk_content.lower()
    for keyword, pattern in tech_keywords.items():
        if re.search(pattern, content_lower):
            metadata["keywords"].append(keyword)
    
    # Tentukan priority berdasarkan urgency signals
    if re.search(r'segera|urgent|critical|kritis|immediately', chunk_content, re.IGNORECASE):
        metadata["priority"] = "HIGH"
    elif re.search(r'peringatan|warning|danger|bahaya', chunk_content, re.IGNORECASE):
        metadata["priority"] = "HIGH"
    elif re.search(r'tidak penting|optional|opsional', chunk_content, re.IGNORECASE):
        metadata["priority"] = "LOW"
    
    return metadata


def get_category_from_chunk(chunk_content: str) -> Optional[str]:
    """Get primary category dari chunk content."""
    metadata = extract_metadata_from_chunk(chunk_content)
    return metadata.get("primary_category")


def get_structure_type_from_chunk(chunk_content: str) -> Optional[str]:
    """Get structure type (TROUBLESHOOT/ESCALATION) dari chunk."""
    metadata = extract_metadata_from_chunk(chunk_content)
    return metadata.get("structure_type")


def is_chunk_escalation_guide(chunk_content: str) -> bool:
    """Cek apakah chunk adalah panduan eskalasi."""
    metadata = extract_metadata_from_chunk(chunk_content)
    return metadata.get("is_escalation", False)


def calculate_metadata_similarity(
    chunk_metadata: Dict,
    query_metadata: Dict,
    weight: float = 0.3
) -> float:
    """
    Hitung similarity score berdasarkan metadata match.
    
    Args:
        chunk_metadata: Metadata dari chunk yang diambil
        query_metadata: Metadata yang diextract dari query
        weight: Bobot metadata similarity dalam range [0, 1]
    
    Returns:
        Score antara 0 - weight
    """
    score = 0.0
    
    # Category match (paling penting)
    if (chunk_metadata.get("primary_category") == query_metadata.get("primary_category")
        and chunk_metadata.get("primary_category") is not None):
        score += weight * 0.7
    
    # Structure type match
    if (chunk_metadata.get("structure_type") == query_metadata.get("structure_type")
        and chunk_metadata.get("structure_type") is not None):
        score += weight * 0.2
    
    # Keywords overlap
    chunk_keywords = set(chunk_metadata.get("keywords", []))
    query_keywords = set(query_metadata.get("keywords", []))
    if chunk_keywords and query_keywords:
        overlap = len(chunk_keywords & query_keywords)
        total = len(chunk_keywords | query_keywords)
        if total > 0:
            score += (weight * 0.1) * (overlap / total)
    
    return min(score, weight)
