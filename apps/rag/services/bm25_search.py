"""
bm25_search.py — BM25 Hybrid Search untuk Retrieval

Menggabungkan semantic search (embedding-based) dengan
lexical search (BM25) untuk meningkatkan recall dan
precision retrieval system.

BM25 baik untuk:
- Keyword matching yang tepat
- Menangani typos/variations
- Menangani term frequency

Semantic search baik untuk:
- Understanding konteks
- Synonyms & paraphrasing
- Abstraksi konsep

Hybrid = Best of both worlds.
"""

import logging
from typing import List, Dict
from rank_bm25 import BM25Okapi
import re

logger = logging.getLogger(__name__)


# ============================================================
# LANGUAGE-MISMATCH PENALTY (Fix for Bug 2)
# ============================================================
# Problem: Indonesian query "kartu akses" semantically matches
# English chunk "Object Key Access" because the BM25 tokenizer
# treats "akses" and "access" as near-identical tokens after
# lowercasing. The embedding model also overlaps them heavily.
#
# Solution: detect the dominant language of both the query and
# the candidate chunk, then apply a score penalty when they
# mismatch. This is a cheap heuristic (no external library)
# that works by counting common Indonesian function words.
#
# Trade-off: purely heuristic; bilingual chunks score neutrally.
# ============================================================

# A small set of high-frequency Indonesian words that almost
# never appear in English text — used as a language signal.
_ID_STOPWORDS_SIGNAL = frozenset([
    'yang', 'dan', 'atau', 'untuk', 'dengan', 'dalam', 'pada',
    'dari', 'tidak', 'adalah', 'ke', 'di', 'ini', 'itu',
    'jika', 'karena', 'saya', 'anda', 'kami', 'kita',
    'mau', 'bisa', 'akan', 'sudah', 'belum', 'masih',
    'pengajuan', 'pengadaan', 'permintaan', 'akses', 'kartu',
    'baru', 'tolong', 'butuh', 'perlu', 'ingin',
])

# Minimum fraction of tokens that must be Indonesian signal words
# for a text to be classified as "predominantly Indonesian".
_ID_LANG_THRESHOLD = 0.12  # >=12% signal words → Indonesian


def _detect_lang_id(text: str) -> bool:
    """
    Return True if ``text`` is likely Indonesian.

    Uses presence-ratio of Indonesian signal words as a fast
    proxy for language detection (no external library needed).
    """
    tokens = re.findall(r'[a-z]+', text.lower())
    if not tokens:
        return False
    id_count = sum(1 for t in tokens if t in _ID_STOPWORDS_SIGNAL)
    return (id_count / len(tokens)) >= _ID_LANG_THRESHOLD


# Penalty multiplier applied when query and chunk languages differ.
# 0.65 cuts a 0.72 cross-encoder score down to ~0.47,
# placing it below a true match at 0.55+.
_LANG_MISMATCH_PENALTY = 0.65



class BM25Search:
    """
    BM25 search engine untuk chunks.
    
    Needs to be initialized dengan list of chunks
    sebelum melakukan search.
    """
    
    def __init__(self):
        self.bm25 = None
        self.documents = []
        self.doc_ids = []
    
    def index_documents(self, documents: List[Dict]):
        """
        Index documents untuk BM25 search.
        
        Args:
            documents: List of dicts dengan struktur:
                {
                    "id": chunk_id,
                    "content": chunk_content,
                    "category": category_name (optional)
                }
        """
        self.documents = documents
        self.doc_ids = [doc.get("id") for doc in documents]
        
        # Tokenize content untuk BM25
        tokenized_docs = []
        for doc in documents:
            tokens = self._tokenize(doc.get("content", ""))
            tokenized_docs.append(tokens)
        
        self.bm25 = BM25Okapi(tokenized_docs)
        logger.info("bm25_indexed", extra={
            "document_count": len(documents),
            "status": "ready"
        })
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search menggunakan BM25.
        
        Args:
            query: Query string
            top_k: Jumlah hasil yang diharapkan
        
        Returns:
            List hasil dengan struktur:
            {
                "id": chunk_id,
                "score": bm25_score,
                "content": chunk_content
            }
        """
        if self.bm25 is None:
            logger.warning("bm25_search_not_indexed")
            return []
        
        try:
            tokens = self._tokenize(query)
            logger.debug("bm25_search_tokens", extra={"query": query[:50], "tokens": tokens, "num_tokens": len(tokens)})
            scores = self.bm25.get_scores(tokens)
            
            # Top-k results
            ranked = sorted(
                enumerate(scores),
                key=lambda x: x[1],
                reverse=True
            )[:top_k]
            
            results = []
            for idx, score in ranked:
                if idx < len(self.documents):
                    doc = self.documents[idx]
                    results.append({
                        "id": doc.get("id"),
                        "score": float(score),
                        "content": doc.get("content"),
                        "category": doc.get("category"),
                        "doc_type": doc.get("doc_type")
                    })
            
            logger.debug("bm25_search_results", extra={
                "results_count": len(results),
                "scores": [round(r["score"], 3) for r in results[:5]]
            })
            
            return results
        except Exception as e:
            logger.error("bm25_search_error", extra={"error": str(e)})
            return []
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization untuk BM25.
        
        - Lowercase
        - Remove special chars
        - Split by whitespace
        - Min length 2 chars
        """
        # Remove special chars tapi keep some yang penting (dash, dot di command)
        text = re.sub(r'[^\w\s\-.]', ' ', text.lower())
        
        # Split
        tokens = text.split()
        
        # Filter: min length 2, skip stopwords
        stopwords = {
            'dan', 'atau', 'yang', 'di', 'ke', 'dari', 'jika', 'jangan',
            'a', 'an', 'the', 'is', 'are', 'in', 'on', 'at', 'of', 'for',
            'untuk', 'dengan', 'dalam', 'pada', 'oleh', 'sebagai', 'bagi', 'kepada',
            'dari', 'ke', 'di', 'dengan', 'oleh', 'pada', 'dalam', 'tentang', 'seperti',
            'sebagai', 'bagi', 'kepada', 'adalah', 'telah', 'akan', 'sudah', 'belum',
            'lagi', 'masih', 'juga', 'saja', 'hanya', 'bahwa', 'karena', 'oleh',
            'sebelum', 'sesudah', 'saat', 'ketika', 'dimana', 'bagaimana', 'mengapa'
        }
        
        tokens = [t for t in tokens if len(t) >= 2 and t not in stopwords]
        return tokens


def hybrid_search(
    query: str,
    semantic_results: List[Dict],
    bm25_results: List[Dict],
    semantic_weight: float = 0.6,
    bm25_weight: float = 0.4,
    top_k: int = 5
) -> List[Dict]:
    """
    Gabungkan hasil semantic search dan BM25 search.
    
    Args:
        query: Query string
        semantic_results: Hasil dari semantic search (embedding)
        bm25_results: Hasil dari BM25 search
        semantic_weight: Bobot semantic search (0-1)
        bm25_weight: Bobot BM25 search (0-1)
        top_k: Jumlah final results
    
    Returns:
        Merged & ranked results
    """
    # Normalize scores
    def normalize_score(results, max_raw_score=1.0):
        if not results:
            return {}
        
        scores_dict = {}
        max_score = max([r.get("score", 0) for r in results]) or 1.0
        
        for r in results:
            doc_id = r.get("id") or r.get("document_chunk_id")
            score = r.get("score", 0)
            normalized = (score / max_score) if max_score > 0 else 0
            scores_dict[doc_id] = normalized
        
        return scores_dict
    
    semantic_scores = normalize_score(semantic_results)
    bm25_scores = normalize_score(bm25_results)
    
    # Combine scores
    all_ids = set(semantic_scores.keys()) | set(bm25_scores.keys())
    combined_scores = {}
    
    for doc_id in all_ids:
        sem_score = semantic_scores.get(doc_id, 0) * semantic_weight
        bm25_score = bm25_scores.get(doc_id, 0) * bm25_weight
        combined_scores[doc_id] = sem_score + bm25_score
    
    # If all scores are near zero, no relevant results
    if not combined_scores or max(combined_scores.values()) < 0.001:
        logger.debug("hybrid_search_no_relevant_results", extra={"max_score": max(combined_scores.values()) if combined_scores else 0})
        return []
    
    # ── Language-mismatch penalty ──────────────────────────────────────────────
    # Build a lookup from doc_id → chunk content for the penalty check.
    # Combine both result lists; semantic_results takes precedence.
    all_docs: Dict = {r.get("id") or r.get("document_chunk_id"): r
                      for r in bm25_results + semantic_results}  # semantic overwrites

    query_is_id = _detect_lang_id(query)

    penalised: Dict[int, float] = {}
    for doc_id, score in combined_scores.items():
        chunk_text = (all_docs.get(doc_id) or {}).get("content", "")
        chunk_is_id = _detect_lang_id(chunk_text)
        if query_is_id != chunk_is_id:
            # Language mismatch: scale score down
            penalised[doc_id] = score * _LANG_MISMATCH_PENALTY
            logger.debug(
                "hybrid_lang_mismatch_penalty",
                extra={
                    "doc_id": doc_id,
                    "query_lang": "id" if query_is_id else "en",
                    "chunk_lang": "id" if chunk_is_id else "en",
                    "original_score": round(score, 4),
                    "penalised_score": round(score * _LANG_MISMATCH_PENALTY, 4),
                    "snippet": chunk_text[:60],
                }
            )
        else:
            penalised[doc_id] = score

    combined_scores = penalised
    # ──────────────────────────────────────────────────────────────────────────

    # Top-k hasil
    ranked = sorted(
        combined_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:top_k]
    
    # Build final results (preserving original data)
    final_results = []
    
    for doc_id, score in ranked:
        if doc_id in all_docs:
            result = all_docs[doc_id].copy()
            result["combined_score"] = score
            result["hybrid_rank"] = len(final_results) + 1
            final_results.append(result)
    
    return final_results
