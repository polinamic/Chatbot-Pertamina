"""
EXAMPLE: Semantic OUT_OF_SCOPE Detection Layer
File ini menunjukkan bagaimana mengimplementasikan Layer 2 (semantic)
untuk auto-detect kategori baru tanpa edit regex manual.

STATUS: EXAMPLE/FUTURE — Belum diimplementasikan di production
TIMELINE: Pertimbangkan ini setelah 6 bulan jika pattern count > 50
"""

from typing import Optional, Dict, Tuple
import numpy as np
from apps.rag.services.embedding import EmbeddingService


class OutOfScopeSemanticsDetector:
    """
    Semantic detection untuk OUT_OF_SCOPE categories.
    Menggunakan embedding yang sama dengan RAG vector store (reuse, no extra cost).
    """
    
    def __init__(self, embedding_service: EmbeddingService):
        """
        Args:
            embedding_service: Instance embedding yang sama dengan RAG
                             (all-mpnet-base-v2 atau model apapun yang dipakai)
        """
        self.embedding_service = embedding_service
        self.similarity_threshold = 0.65
        
        # OUT_OF_SCOPE category anchors
        # Setiap kategori punya descriptive text yang di-embed
        # Text ini capture semantic essence kategori
        # (Hanya di-embed SATU KALI saat init, lalu di-cache)
        self.out_of_scope_anchors = self._init_anchors()
        
    def _init_anchors(self) -> Dict[str, np.ndarray]:
        """
        Initialize semantic anchors untuk setiap OUT_OF_SCOPE category.
        
        Anchor adalah representative text yang di-embed sekali dan di-cache.
        Jika embedding_service support batch, bisa embed semua sekaligus (faster).
        """
        anchor_texts = {
            # CRAFT & DIY
            "craft": (
                "tutorial cara membuat origami pesawat mainan kertas. "
                "panduan DIY kerajinan tangan dari barang bekas. "
                "langkah-langkah membuat boneka dari kain flanel. "
                "cara membuat hiasan dinding dari kardus. "
                "panduan seni melukis dan mewarnai. "
                "tips membuat miniature dan figurine. "
                "diorama craft project. woodworking carpentry hobby."
            ),
            
            # CULINARY
            "culinary": (
                "resep memasak nasi goreng. "
                "panduan membuat kue dari tepung. "
                "cara membuat minuman smoothie. "
                "tips chef memasak daging. "
                "kuliner dan menu makanan restoran. "
                "panduan diet dan nutritional advice. "
                "cooking guide kitchen tips."
            ),
            
            # ENTERTAINMENT & HUMOR
            "entertainment": (
                "jokes lucu tentang wifi dan laptop. "
                "kumpulan meme dan humor. "
                "cerita lucu dan komedi. "
                "film movie recommendations. "
                "lagu musik artist. "
                "konser entertainment show. "
                "funny story entertainment content."
            ),
            
            # HISTORY & EDUCATION (non-IT)
            "history": (
                "siapa pencipta wifi dan internet. "
                "sejarah teknologi dan penemuan. "
                "kapan ditemukan komputer pertama. "
                "biografi tokoh inventor. "
                "pelajaran matematika fisika kimia. "
                "geografis dan geografi kelas. "
                "history lesson educational content."
            ),
            
            # LIFESTYLE & PERSONAL
            "lifestyle": (
                "tips fashion dan pakaian. "
                "panduan beauty makeup skincare. "
                "relationship dan dating advice. "
                "health fitness exercise routine. "
                "travel tips holiday destination. "
                "home decoration interior design. "
                "lifestyle personal development."
            ),
        }
        
        anchors = {}
        for category, text in anchor_texts.items():
            try:
                # Embed description kategori (cached)
                embedding = self.embedding_service.embed_text(text)
                anchors[category] = np.array(embedding)
            except Exception as e:
                print(f"Warning: Failed to embed anchor for '{category}': {e}")
                continue
        
        return anchors
    
    def detect(self, question: str) -> Tuple[Optional[str], float]:
        """
        Detect OUT_OF_SCOPE based on semantic similarity dengan anchor categories.
        
        Args:
            question: User question
            
        Returns:
            (category, confidence) atau (None, 0.0) jika tidak match
            
        Example:
            >>> detector.detect("cara membuat miniature rumah")
            ('craft', 0.72)  # ← Confidence 72%
            
            >>> detector.detect("bagaimana cara reset password")
            (None, 0.0)  # ← Bukan OUT_OF_SCOPE, fallthrough ke LLM
        """
        try:
            q_embedding = self.embedding_service.embed_text(question)
            q_embedding = np.array(q_embedding)
            
            # Find most similar category
            best_category = None
            best_similarity = 0.0
            
            for category, anchor_embedding in self.out_of_scope_anchors.items():
                # Cosine similarity (kedua vector sudah normalized dari FAISS/sentence-transformers)
                similarity = self._cosine_similarity(q_embedding, anchor_embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_category = category
            
            # Return only if confidence > threshold
            if best_similarity > self.similarity_threshold:
                return (best_category, float(best_similarity))
            else:
                return (None, 0.0)
                
        except Exception as e:
            print(f"Error in semantic detection: {e}")
            return (None, 0.0)
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity antara dua vectors (normalized)."""
        if vec1.size == 0 or vec2.size == 0:
            return 0.0
        
        # Normalize
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
        
        # Dot product = cosine similarity untuk normalized vectors
        return float(np.dot(vec1_norm, vec2_norm))
    
    def set_threshold(self, threshold: float):
        """Tune similarity threshold (0.0 - 1.0)."""
        self.similarity_threshold = threshold


# =====================================================
# INTEGRATION DENGAN EXISTING CHAT SERVICE
# =====================================================

def detect_intent_with_semantic_layer(
    question: str,
    semantic_detector: OutOfScopeSemanticsDetector,
) -> str:
    """
    Three-layer intent detection dengan semantic fallback.
    
    Layer 1: Rule-based (EXISTING) → Fast
    Layer 2: Semantic (NEW) → Auto-adaptive
    Layer 3: LLM classifier (EXISTING) → Accurate
    """
    # Layer 1: Rule-based (existing)
    from apps.rag.services.chat_service import detect_intent_rules
    
    rule_result = detect_intent_rules(question)
    if rule_result:
        return rule_result  # Confident hit
    
    # Layer 2: Semantic similarity (NEW)
    semantic_category, confidence = semantic_detector.detect(question)
    if semantic_category:
        # Log the detection
        import logging
        logger = logging.getLogger("chatbot")
        logger.info("intent_semantic_detection", extra={
            "category": semantic_category,
            "confidence": confidence
        })
        return "OUT_OF_SCOPE"
    
    # Layer 3: LLM fallback (existing)
    from apps.rag.services.chat_service import detect_intent_llm_fallback
    
    return detect_intent_llm_fallback(question)


# =====================================================
# USAGE EXAMPLE
# =====================================================

"""
Cara pakai di apps/rag/apps.py atau views.py:

    from apps.rag.services.embedding import EmbeddingService
    from chat_service_future import OutOfScopeSemanticsDetector
    
    # Init semantic detector (saat server startup)
    embedding_service = EmbeddingService()
    semantic_detector = OutOfScopeSemanticsDetector(embedding_service)
    
    # Di chat view
    def siti_chat(request):
        intent = detect_intent_with_semantic_layer(
            question,
            semantic_detector
        )
        ...

TEST CASES:
    1. "cara membuat miniature rumah dari kardus"
       Layer 1: ❌ No regex match
       Layer 2: ✓ Semantic match to "craft" (similarity: 0.72)
       Result: OUT_OF_SCOPE ✓
       Time: 0ms (rule) + 100ms (semantic) = 100ms total
    
    2. "bagaimana cara reset password laptop"
       Layer 1: ❌ No clear pattern
       Layer 2: ❌ Similarity 0.38 (below threshold 0.65)
       Layer 3: ✓ LLM: IT_PROBLEM
       Result: IT_PROBLEM ✓
       Time: 0ms + 100ms + 1000ms = 1100ms
    
    3. "siapa pencipta wifi"
       Layer 1: ✓ Regex match "siapa pencipta"
       Result: OUT_OF_SCOPE ✓
       Time: 0ms (instant)
"""


# =====================================================
# MONITORING & TUNING
# =====================================================

def analyze_semantic_performance(
    test_questions: list,
    semantic_detector: OutOfScopeSemanticsDetector,
) -> dict:
    """
    Analyze semantic detector performance.
    Gunakan untuk tune threshold.
    """
    results = {
        "correct_oos": 0,      # Correctly detected as OUT_OF_SCOPE
        "correct_iti": 0,      # Correctly not OUT_OF_SCOPE (let fallthrough)
        "false_positive": 0,   # Incorrectly OUT_OF_SCOPE
        "false_negative": 0,   # Should be OUT_OF_SCOPE but wasn't
        "similarities": []
    }
    
    for question, expected_intent in test_questions:
        detected_category, similarity = semantic_detector.detect(question)
        
        results["similarities"].append({
            "question": question,
            "category": detected_category,
            "similarity": similarity,
            "expected": expected_intent
        })
        
        if expected_intent == "OUT_OF_SCOPE":
            if detected_category:
                results["correct_oos"] += 1
            else:
                results["false_negative"] += 1
        else:  # IT_PROBLEM or other
            if detected_category:
                results["false_positive"] += 1
            else:
                results["correct_iti"] += 1
    
    # Calculate metrics
    total = sum([results["correct_oos"], results["correct_iti"],
                results["false_positive"], results["false_negative"]])
    
    accuracy = (results["correct_oos"] + results["correct_iti"]) / total if total > 0 else 0
    
    return {
        **results,
        "accuracy": accuracy,
        "false_positive_rate": results["false_positive"] / (results["false_positive"] + results["correct_iti"]) if (results["false_positive"] + results["correct_iti"]) > 0 else 0,
        "false_negative_rate": results["false_negative"] / (results["false_negative"] + results["correct_oos"]) if (results["false_negative"] + results["correct_oos"]) > 0 else 0,
    }


# =====================================================
# COMPARISON: CURRENT vs SEMANTIC APPROACH
# =====================================================

"""
TEST CASE: "cara membuat miniature rumah dari kardus"

CURRENT (Rule-based only):
  ├─ detect_intent_rules()
  │  ├─ Check escalation patterns → No match (0ms)
  │  ├─ Check greeting patterns → No match (0ms)
  │  ├─ Check non-IT patterns
  │  │  └─ Look for: origami, kerajinan, craft, diy, mainan
  │  │     ✓ MATCH! "miniature" NOT in pattern ← BUG
  │  │     But "craft" might trigger if question has it
  │  │  └─ "miniature rumah" has no matching keyword ✗
  │  └─ Check IT-problem patterns → No match (0ms)
  └─ Returns: None
  
  Result: Fallthrough to LLM (1000ms) ← SLOW PATH

WITH SEMANTIC LAYER:
  ├─ detect_intent_rules() → None (0ms)
  ├─ detect_intent_semantic()
  │  ├─ Embed "cara membuat miniature rumah dari kardus"
  │  ├─ Compare dengan "craft" anchor embedding
  │  │  └─ Similarity: 0.72 > threshold 0.65
  │  └─ Returns: ("craft", 0.72)
  └─ Returns: OUT_OF_SCOPE (100ms)
  
  Result: Detected as OUT_OF_SCOPE (100ms) ← FAST + ACCURATE

BENEFIT:
✓ "miniature" tidak perlu ada di regex
✓ Semantic understanding: "miniature rumah" = craft semantically
✓ 10x faster than LLM (100ms vs 1000ms)
✓ Auto-adapt ke variasi bahasa ("figurine", "diorama", "craft project" dll)
"""


if __name__ == "__main__":
    # Example usage (requires embedding service)
    print("This is example code for future semantic detection layer.")
    print("Not yet integrated into production.")
    print("\nWhen to activate:")
    print("  - After 6 months of pattern rule maintenance")
    print("  - If pattern count exceeds 100")
    print("  - If update frequency > 1 per week")
    print("  - For better UX on emerging categories")
