# 🔧 Code Improvement Recommendations - Implementation Guide

## Overview
File ini berisi code improvements spesifik yang bisa langsung di-implement untuk memperbaiki semantic detector dan intent detection flow.

---

## A. CRITICAL FIX #1: Add Error Handling untuk Semantic Detection

**Location**: Lines 283-290 dalam `detect_intent()`

**Current Code**:
```python
# Layer 2: Semantic Routing
if embedding_service:
    detector = get_semantic_detector(embedding_service)
    semantic_category, similarity = detector.detect(question)
    if semantic_category:
        logger.info("intent_detected", extra={...})
        return "OUT_OF_SCOPE"
```

**Problem**:
- Exception dalam `detector.detect()` tidak di-catch
- Akan crash request jika embedding service down
- No graceful fallback ke Layer 3

**Fixed Code**:
```python
# Layer 2: Semantic Routing
if embedding_service:
    try:
        detector = get_semantic_detector(embedding_service)
        semantic_category, similarity = detector.detect(question)
        if semantic_category:
            logger.info("intent_detected", extra={
                "intent_source": "semantic_routing",
                "intent": "OUT_OF_SCOPE",
                "category": semantic_category,
                "confidence": round(similarity, 3)
            })
            return "OUT_OF_SCOPE"
    except Exception as e:
        logger.warning("semantic_detection_error", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "question_length": len(question)
        })
        # Gracefully continue to Layer 3
```

---

## B. CRITICAL FIX #2: Fix Singleton Pattern untuk Thread-Safety

**Location**: Lines ~70-80 (di mana get_semantic_detector() defined)

**Current Code**:
```python
_semantic_detector_instance = None

def get_semantic_detector(embedding_service):
    global _semantic_detector_instance
    if _semantic_detector_instance is None:
        _semantic_detector_instance = OutOfScopeSemanticsDetector(embedding_service)
    return _semantic_detector_instance
```

**Problems**:
1. Race condition di concurrent requests (tidak ada lock)
2. Stale instance jika embedding_service di-replace
3. No cleanup, memory leak

**Fixed Code**:
```python
import threading

_semantic_detector_instance = None
_detector_lock = threading.Lock()

def get_semantic_detector(embedding_service):
    """
    Get or create semantic detector instance (singleton pattern).
    Thread-safe dengan double-check locking.
    
    Args:
        embedding_service: Service untuk embed text
        
    Returns:
        OutOfScopeSemanticsDetector instance
    """
    global _semantic_detector_instance
    
    # Quick check (most calls)
    if _semantic_detector_instance is not None:
        # Verify embedding_service masih sama
        if _semantic_detector_instance.embedding_service == embedding_service:
            return _semantic_detector_instance
    
    # Acquire lock untuk creation/update
    with _detector_lock:
        # Double-check setelah lock acquired
        if (_semantic_detector_instance is None or 
            _semantic_detector_instance.embedding_service != embedding_service):
            logger.info("semantic_detector_reinit", extra={
                "reason": "new_embedding_service" if _semantic_detector_instance is None else "embedding_service_changed"
            })
            _semantic_detector_instance = OutOfScopeSemanticsDetector(embedding_service)
    
    return _semantic_detector_instance
```

---

## C. IMPROVEMENT #1: Extract Hardcoded Threshold ke Config

**Location**: Line ~93 dalam `OutOfScopeSemanticsDetector.__init__()`

**Add ke config section (lines 71-83)**:
```python
# =====================================================
# CONFIGURATION - SEMANTIC ROUTING
# =====================================================
SEMANTIC_DETECTION_ENABLED = os.getenv("SEMANTIC_DETECTION_ENABLED", "true").lower() == "true"
SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.65"))
SEMANTIC_MIN_CONFIDENCE = float(os.getenv("SEMANTIC_MIN_CONFIDENCE", "0.5"))
```

**Update class initialization**:
```python
class OutOfScopeSemanticsDetector:
    def __init__(self, embedding_service):
        self.embedding_service = embedding_service
        self.similarity_threshold = SEMANTIC_SIMILARITY_THRESHOLD  # Use config
        self.min_confidence = SEMANTIC_MIN_CONFIDENCE
        self.out_of_scope_anchors = self._init_anchors()
        logger.info("semantic_detector_init", extra={
            "threshold": self.similarity_threshold,
            "num_anchors": len(self.out_of_scope_anchors)
        })
```

**Add .env example**:
```env
# Semantic Routing Configuration
SEMANTIC_DETECTION_ENABLED=true
SEMANTIC_SIMILARITY_THRESHOLD=0.65  # Range: 0.5 - 0.8
SEMANTIC_MIN_CONFIDENCE=0.5         # Range: 0.3 - 0.7
```

---

## D. IMPROVEMENT #2: Context-Aware OUT_OF_SCOPE Responses

**Location**: Lines 506-507 dalam `_process_chat_sync()`

**Current Code**:
```python
elif intent == "OUT_OF_SCOPE":
    answer = "Maaf, saya hanya dapat membantu dengan pertanyaan seputar IT seperti masalah wifi, printer, laptop, email, VPN, atau software perusahaan. 😊\n\nApakah ada masalah IT yang bisa saya bantu?"
```

**Improved Code**:
```python
elif intent == "OUT_OF_SCOPE":
    # Get category untuk response yang lebih kontekstual
    category_specific_response = _get_out_of_scope_response(question, embedding_service)
    answer = category_specific_response
```

**Add helper function (baru)**:
```python
def _get_out_of_scope_response(question: str, embedding_service) -> str:
    """
    Generate OUT_OF_SCOPE response berdasarkan kategori semantic detection.
    Lebih informatif dan kontekstual dibanding generic message.
    """
    
    # Default response untuk semua kategori
    default_response = (
        "Maaf, saya hanya dapat membantu dengan pertanyaan seputar IT "
        "seperti masalah wifi, printer, laptop, email, VPN, atau software perusahaan. 😊\n\n"
        "Apakah ada masalah IT yang bisa saya bantu?"
    )
    
    # Jika embedding_service tidak tersedia, gunakan default
    if not embedding_service:
        return default_response
    
    try:
        # Deteksi kategori untuk response yang lebih spesifik
        detector = get_semantic_detector(embedding_service)
        category, similarity = detector.detect(question)
        
        if not category or similarity < SEMANTIC_MIN_CONFIDENCE:
            return default_response
        
        # Category-specific responses
        category_responses = {
            "craft_and_hobbies": (
                "Saya lihat pertanyaan Anda tentang kerajinan/hobi. "
                "Saya adalah asisten IT Support dan hanya focus di masalah teknis.\n\n"
                "Ada masalah dengan IT infrastructure Anda yang bisa saya bantu?"
            ),
            "culinary": (
                "Pertanyaan tentang memasak/makanan bukan bagian dari expertise IT saya. "
                "Mohon tanya ke resource lain untuk topik kuliner.\n\n"
                "Ada masalah jaringan/perangkat yang perlu bantuan?"
            ),
            "entertainment": (
                "Saya hanya bisa membantu dengan masalah teknis IT, bukan entertainment/hiburan. "
                "Apakah ada kendala internet/streaming yang bisa saya debug?"
            ),
            "history_general": (
                "Pertanyaan sejarah umum di luar scope support IT saya. "
                "Apakah ada masalah dengan sistem/perangkat yang butuh help?"
            ),
            "lifestyle": (
                "Topik lifestyle/fashion bukan bagian dari IT support. "
                "Silakan hubungi department lain untuk pertanyaan non-teknis.\n\n"
                "Ada issue IT yang bisa saya selesaikan?"
            ),
            "physical_damage": (
                "Saya lihat perangkat Anda mengalami damage fisik. "
                "Masalah ini mungkin butuh pengiriman ke service center hardware. "
                "Hubungi IT Support untuk proses service/repair portal.\n\n"
                "Atau apakah ada masalah software/networking yang bisa saya bantu sementara?"
            ),
        }
        
        response = category_responses.get(category, default_response)
        logger.info("out_of_scope_response", extra={
            "category": category,
            "confidence": round(similarity, 3)
        })
        return response
        
    except Exception as e:
        logger.warning("out_of_scope_response_generation_failed", extra={
            "error": str(e)
        })
        return default_response
```

---

## E. IMPROVEMENT #3: Add Embedding Caching untuk Performance

**Location**: Dalam `OutOfScopeSemanticsDetector` class

**Why**: 
- Semantic detection adalah bottleneck (80-120ms)
- Same questions sering di-ask (caching membantu)
- Question embeddings expensive untuk compute

**Implementation**:
```python
from functools import lru_cache
import time

class OutOfScopeSemanticsDetector:
    def __init__(self, embedding_service):
        self.embedding_service = embedding_service
        self.similarity_threshold = SEMANTIC_SIMILARITY_THRESHOLD
        self.out_of_scope_anchors = self._init_anchors()
        self._embedding_cache = {}  # {question: (embedding, timestamp)}
        self.cache_ttl = 300  # 5 minutes
        
    def _get_cached_embedding(self, question: str):
        """Get cached embedding atau compute baru."""
        current_time = time.time()
        
        if question in self._embedding_cache:
            embedding, timestamp = self._embedding_cache[question]
            # Check if still valid
            if current_time - timestamp < self.cache_ttl:
                return embedding
        
        # Compute new embedding
        embedding = self.embedding_service.embed_text(question)
        self._embedding_cache[question] = (embedding, current_time)
        
        # Cleanup old entries jika cache terlalu besar
        if len(self._embedding_cache) > 1000:
            # Remove oldest 25% entries
            sorted_cache = sorted(
                self._embedding_cache.items(),
                key=lambda x: x[1][1]  # Sort by timestamp
            )
            entries_to_remove = len(sorted_cache) // 4
            for question, _ in sorted_cache[:entries_to_remove]:
                del self._embedding_cache[question]
        
        return embedding
    
    def detect(self, question: str) -> Tuple[Optional[str], float]:
        """Detect out-of-scope intent dengan cached embeddings."""
        try:
            # Use cached embedding jika ada
            q_embedding = self._get_cached_embedding(question)
            
            max_similarity = 0.0
            detected_category = None
            
            for category, anchor_embedding in self.out_of_scope_anchors.items():
                similarity = np.dot(q_embedding, anchor_embedding) / (
                    np.linalg.norm(q_embedding) * np.linalg.norm(anchor_embedding) + 1e-8
                )
                if similarity > self.similarity_threshold and similarity > max_similarity:
                    max_similarity = similarity
                    detected_category = category
            
            return detected_category, max_similarity
            
        except Exception as e:
            logger.warning("semantic_detection_error", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            return None, 0.0
```

---

## F. IMPROVEMENT #4: Refactor Large Functions

**Problem**: `_process_chat_sync()` adalah 200+ lines, terlalu besar.

**Solution**: Break into smaller functions:

```python
def _process_chat_sync(question: str, session: Dict, vector_store, embedding_service, session_id: str) -> str:
    """Main chat router - synchronous version."""
    question = question.strip()
    
    # Handle awaiting confirmation
    if session["awaiting_support_confirmation"]:
        return _handle_support_confirmation(question, session, vector_store, embedding_service, session_id)
    
    # Detect intent (Layer 1-3)
    intent = detect_intent(question, embedding_service)
    
    # Route based on intent
    if intent == "IT_PROBLEM":
        return _handle_it_problem(question, session, vector_store, embedding_service, session_id)
    elif intent == "GENERAL_CHAT":
        return _handle_general_chat(question, session, session_id)
    elif intent == "OUT_OF_SCOPE":
        return _handle_out_of_scope(question, session, embedding_service, session_id)
    elif intent == "REQUEST_IT_SUPPORT":
        return _handle_escalation_request(question, session, vector_store, embedding_service, session_id)
    elif intent == "REJECT_IT_SUPPORT":
        return _handle_escalation_reject(question, session, session_id)
    else:
        return _handle_fallback(question, session, session_id)


def _handle_support_confirmation(question: str, session: Dict, vector_store, embedding_service, session_id: str) -> str:
    """Handle YES/NO response untuk escalation."""
    confirmation = detect_confirmation(question)
    
    if confirmation is True:
        session["awaiting_support_confirmation"], session["attempts"] = False, 0
        guide = escalation_guide(session["last_it_problem"] or question, vector_store, embedding_service)
        answer = f"Baik, saya akan bantu mencarikan panduan eskalasi untuk Anda.\n\n{guide}"
    elif confirmation is False:
        session["awaiting_support_confirmation"], session["offered_support"] = False, False
        answer = "Baik, mari kita coba langkah lain. Apakah ada hal lain yang bisa saya bantu?"
    else:
        session["awaiting_support_confirmation"], session["offered_support"] = False, False
        session["attempts"], session["cached_context"] = 0, None
        answer = "Saya kurang paham. Maksud Anda baik atau tidak?"
    
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer


def _handle_it_problem(question: str, session: Dict, vector_store, embedding_service, session_id: str) -> str:
    """Handle IT problem detection dan troubleshooting."""
    if session["attempts"] == 0:
        clarification = needs_clarification(question, session["history"])
        if clarification:
            _update_history(session, question, clarification)
            session_manager.save(session_id, session)
            return clarification
    
    session["last_it_problem"] = question if session["attempts"] == 0 else session["last_it_problem"]
    
    # Track failed steps
    if re.search(r'\b(masih|belum|tidak berhasil|gagal|tidak bisa|sama saja|tidak mempan)\b', question, re.IGNORECASE):
        if session["history"]:
            last_bot_msgs = [m["content"] for m in session["history"] if m["role"] == "assistant"]
            if last_bot_msgs and last_bot_msgs[-1][:60] not in session["failed_steps"]:
                session["failed_steps"].append(last_bot_msgs[-1][:60] + "...")
    
    # Generate RAG-based response
    rag_query = rewrite_query_for_rag(question, session["history"], original_problem=session.get("last_it_problem", ""))
    answer = get_llm_response(question, session["history"], "troubleshoot", vector_store, embedding_service, 
                             rag_query=rag_query, failed_steps=session["failed_steps"], session=session)
    session["attempts"] += 1
    
    # Offer escalation if stuck
    if session["attempts"] >= 2 and not session["offered_support"]:
        session["offered_support"], session["awaiting_support_confirmation"] = True, True
        answer += "\n\n---\nMasalah ini sepertinya membutuhkan penanganan lebih lanjut. Apakah Anda ingin saya pandu untuk menghubungi tim IT Support? (Ya/Tidak)"
    
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer


def _handle_general_chat(question: str, session: Dict, session_id: str) -> str:
    """Handle general greetings dan small talk."""
    answer = get_llm_response(question, session["history"], "small_talk")
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer


def _handle_out_of_scope(question: str, session: Dict, embedding_service, session_id: str) -> str:
    """Handle OUT_OF_SCOPE pertanyaan dengan category-specific responses."""
    answer = _get_out_of_scope_response(question, embedding_service)
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer


def _handle_escalation_request(question: str, session: Dict, vector_store, embedding_service, session_id: str) -> str:
    """Handle request untuk eskalasi ke IT Support."""
    session["attempts"], session["offered_support"] = 0, False
    guide = escalation_guide(session.get("last_it_problem") or question, vector_store, embedding_service)
    answer = f"Tentu! Berikut panduan eskalasi ke IT Support:\n\n{guide}"
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer


def _handle_escalation_reject(question: str, session: Dict, session_id: str) -> str:
    """Handle penolakan eskalasi."""
    session["offered_support"] = False
    answer = "Baik, saya akan tetap berusaha membantu Anda di sini. Silakan ceritakan masalahnya lebih lanjut."
    _update_history(session, question, answer)
    session_manager.save(session_id, session)
    return answer
```

---

## G. IMPROVEMENT #5: Add Monitoring & Metrics

**Add metrics tracking**:

```python
from collections import defaultdict
import time

class ChatMetrics:
    """Track chatbot usage metrics untuk monitoring."""
    
    def __init__(self):
        self.intent_distribution = defaultdict(int)  # {intent: count}
        self.intent_sources = defaultdict(int)       # {source (rules/semantic/llm): count}
        self.latencies = defaultdict(list)           # {layer: [latency_ms]}
        self.errors = defaultdict(int)               # {error_type: count}
    
    def record_intent(self, intent: str, source: str, latency_ms: int, confidence: float):
        """Record intent detection metrics."""
        self.intent_distribution[intent] += 1
        self.intent_sources[source] += 1
        self.latencies[source].append(latency_ms)
        
        # Log untuk monitoring
        logger.info("intent_detected", extra={
            "intent": intent,
            "source": source,
            "latency_ms": latency_ms,
            "confidence": round(confidence, 3)
        })
    
    def record_error(self, error_type: str):
        """Record error metrics."""
        self.errors[error_type] += 1
        logger.warning("error_recorded", extra={
            "error_type": error_type,
            "total_errors": self.errors[error_type]
        })
    
    def get_avg_latency(self, source: str) -> float:
        """Get average latency untuk specific source."""
        if not self.latencies[source]:
            return 0.0
        return sum(self.latencies[source]) / len(self.latencies[source])
    
    def get_summary(self) -> dict:
        """Get metrics summary untuk dashboard."""
        return {
            "intents": dict(self.intent_distribution),
            "sources": dict(self.intent_sources),
            "avg_latencies": {
                source: round(self.get_avg_latency(source), 2)
                for source in self.latencies
            },
            "errors": dict(self.errors)
        }

# Global metrics instance
metrics = ChatMetrics()

# Use dalam detect_intent()
def detect_intent(question: str, embedding_service=None) -> str:
    start_time = time.time()
    
    # Layer 1: Rule-Based
    rule_result = detect_intent_rules(question)
    if rule_result:
        latency_ms = int((time.time() - start_time) * 1000)
        metrics.record_intent(rule_result, "rules", latency_ms, 0.95)
        return rule_result
    
    # Layer 2: Semantic Routing
    if embedding_service:
        try:
            detector = get_semantic_detector(embedding_service)
            semantic_category, similarity = detector.detect(question)
            if semantic_category:
                latency_ms = int((time.time() - start_time) * 1000)
                metrics.record_intent("OUT_OF_SCOPE", "semantic_routing", latency_ms, similarity)
                return "OUT_OF_SCOPE"
        except Exception as e:
            metrics.record_error("semantic_detection_failed")
            logger.warning("semantic_detection_error", extra={"error": str(e)})
    
    # Layer 3: LLM Fallback
    llm_result = detect_intent_llm_fallback(question)
    latency_ms = int((time.time() - start_time) * 1000)
    confidence = 0.85 if llm_result == "IT_PROBLEM" else 0.88 if llm_result == "OUT_OF_SCOPE" else 0.75
    metrics.record_intent(llm_result, "llm_fallback", latency_ms, confidence)
    return llm_result
```

---

## Summary: Implementation Checklist

- [ ] **CRITICAL FIX #1**: Add try-except untuk semantic detection (Section A)
- [ ] **CRITICAL FIX #2**: Fix singleton pattern dengan thread-safety (Section B)
- [ ] **IMPROVEMENT #1**: Extract threshold ke config (Section C)
- [ ] **IMPROVEMENT #2**: Context-aware OUT_OF_SCOPE responses (Section D)
- [ ] **IMPROVEMENT #3**: Add embedding caching (Section E)
- [ ] **IMPROVEMENT #4**: Refactor large functions (Section F)
- [ ] **IMPROVEMENT #5**: Add metrics/monitoring (Section G)
- [ ] Run tests: `python test_pattern_detection.py` (should still pass 27/27)
- [ ] Load test semantic layer untuk verify performance
- [ ] Deploy to staging & monitor error rates
- [ ] Production deployment dengan monitoring enabled

---

**Estimated Implementation Time**: 
- Critical fixes: 1 hour
- Improvements: 2-3 hours
- Testing: 1 hour
- Deployment: 0.5 hour

**Total**: ~5-6 hours engineering work
