# Migration Guide: Dari Rule-Based ke Semantic Layer
## Kapan Harus Migrasi?

### ⚠️ WARNING SIGNS: Migrasi Diperlukan Jika...

```python
# Indicator 1: Pattern count & complexity
patterns_count = len(_NON_IT_INTENT_PATTERNS.pattern.split('|'))
if patterns_count > 100:
    print("⚠️ Regex complexity too high → Consider semantic migration")

# Indicator 2: Update frequency
avg_pattern_updates_per_week = count_weekly_pattern_additions()
if avg_pattern_updates_per_week > 1.0:
    print("⚠️ Pattern updates too frequent → Semantic layer saves maintenance")

# Indicator 3: False negatives tracking
false_negative_rate = count_oos_questions_classified_as_it() / total_oos_questions
if false_negative_rate > 0.10:  # > 10%
    print("⚠️ Missing 10%+ of OUT_OF_SCOPE → Semantic helps catch variations")

# Indicator 4: Lag time
time_from_request_to_pattern_add = measure_implementation_lag()
if time_from_request_to_pattern_add.days > 7:
    print("⚠️ Pattern deployment lag > 7 days → Semantic is faster")
```

---

## Decision Matrix: Current vs Semantic

| Trigger | Current OK? | Semantic Better? |
|---------|:-----:|:--------:|
| Pattern count < 50 | ✅ Yes | ⭕ Optional |
| Pattern count 50-100 | ⚠️ Maybe | ✅ Recommended |
| Pattern count > 100 | ❌ No | ✅ Required |
| Weekly updates < 1 | ✅ Yes | ⭕ Nice-to-have |
| Weekly updates 1-3 | ⚠️ Maybe | ✅ Recommended |
| Weekly updates > 3 | ❌ No | ✅ Required |
| You want auto-adapt | ❌ No | ✅ Yes |
| Latency < 100ms critical | ✅ Yes (rule) | ⭕ 100ms acceptable |

**Current Status (April 2026):**
```
- Pattern count: ~20 ✓
- Weekly updates: 0-1 ✓
- False negative rate: ~2% ✓
→ VERDICT: Rule-based still sufficient (not urgent to migrate)
→ DECISION: Plan migration for ~6 months from now
```

---

## Migration Checklist

### Phase 1: Preparation (Week 1)

- [ ] **Read & understand semantic_detector_example.py**
- [ ] **Verify embedding_service availability**
  ```python
  # Check: embedding_service sudah singleton cached?
  # Lihat: apps/rag/apps.py atau apps/rag/views.py
  # Pastikan: Tidak ada instantiation ganda
  ```
- [ ] **Design anchor categories**
  ```python
  # Identify semantic groups:
  # - Craft/DIY: kerajinan, miniature, diorama, figurine
  # - Culinary: resep, masak, menu, chef
  # - Entertainment: jokes, humor, meme, film
  # - History: sejarah, penemuan, biography
  # - Lifestyle: fashion, beauty, dating, travel
  # - Education: pelajaran (non-IT), matematika, geografi
  ```
- [ ] **Establish baseline metrics**
  ```python
  # BEFORE semantic layer:
  # - Accuracy of current OUT_OF_SCOPE detection
  # - False positive rate
  # - False negative rate
  # - Average latency per intent_detection call
  ```

### Phase 2: Implementation (Week 2-3)

- [ ] **Copy semantic_detector_example.py → semantic_detector.py**
- [ ] **Adapt anchors to Indonesian IT support context**
  ```python
  # Ensure anchor texts are:
  # ✓ Representative of OUT_OF_SCOPE categories
  # ✓ Written in natural Indonesian
  # ✓ Similar examples to what users actually ask
  ```
- [ ] **Integrate into detect_intent()**
  ```python
  def detect_intent(question: str) -> str:
      result = detect_intent_rules(question)
      if result: return result
      
      # ← INSERT semantic layer here
      result = detect_intent_semantic(question)
      if result: return result
      
      return detect_intent_llm_fallback(question)
  ```
- [ ] **Initialize semantic_detector at server startup**
  ```python
  # apps/rag/apps.py atau views.py
  semantic_detector = OutOfScopeSemanticsDetector(embedding_service)
  ```

### Phase 3: Testing (Week 4)

- [ ] **Run regression tests**
  ```bash
  python test_pattern_detection.py  # Rule-based still works?
  ```
- [ ] **Create semantic detection tests**
  ```python
  TEST_SEMANTIC_CASES = [
      ("cara membuat miniature rumah", "craft"),
      ("resep membuat kue", "culinary"),
      ("jokes tentang wifi", "entertainment"),
      ("sejarah internet", "history"),
      ("tips fashion", "lifestyle"),
  ]
  ```
- [ ] **Tune similarity threshold**
  ```python
  # Start with 0.65, then adjust based on test results:
  # If too many false positives → increase to 0.70
  # If too many false negatives → decrease to 0.60
  
  from semantic_detector import analyze_semantic_performance
  
  metrics = analyze_semantic_performance(
      test_questions=TEST_SEMANTIC_CASES,
      detector=semantic_detector
  )
  
  if metrics["false_positive_rate"] > 0.10:
      semantic_detector.set_threshold(0.70)
  ```
- [ ] **A/B test with users (optional)**
  ```
  - Route 10% traffic ke semantic layer
  - Monitor false positive/negative rates
  - Gather user feedback
  - Rollout 100% jika metrics OK
  ```

### Phase 4: Monitoring (Ongoing)

- [ ] **Log semantic detections separately**
  ```python
  logger.info("intent_semantic_detection", extra={
      "category": category,
      "similarity": similarity,
      "question": question[:100]
  })
  ```
- [ ] **Monthly accuracy report**
  ```python
  # Count:
  # - True positives (correctly OUT_OF_SCOPE)
  # - True negatives (correctly NOT out-of-scope)
  # - False positives (false OUT_OF_SCOPE rejection)
  # - False negatives (missed OUT_OF_SCOPE)
  
  # Calculate:
  # - Precision = TP / (TP + FP)
  # - Recall = TP / (TP + FN)
  # - F1 = 2 * (Precision * Recall) / (Precision + Recall)
  ```
- [ ] **Update anchors quarterly**
  ```python
  # Every 3 months:
  # 1. Review new OUT_OF_SCOPE categories emerged
  # 2. Add to anchor text if needed
  # 3. Re-embed anchors
  # 4. Validate no regression in metrics
  ```

### Phase 5: Rollback Plan

If semantic layer causes issues:

```python
# Quick disable (option 1):
def detect_intent(question: str) -> str:
    result = detect_intent_rules(question)
    if result: return result
    
    # DISABLED: Semantic layer
    # result = detect_intent_semantic(question)
    # if result: return result
    
    return detect_intent_llm_fallback(question)

# Or (option 2):
USE_SEMANTIC_LAYER = False  # Quick toggle

def detect_intent(question: str) -> str:
    result = detect_intent_rules(question)
    if result: return result
    
    if USE_SEMANTIC_LAYER:
        result = detect_intent_semantic(question)
        if result: return result
    
    return detect_intent_llm_fallback(question)
```

---

## Success Criteria

### After Migration, Target Metrics:

| Metric | Current | Target | Note |
|--------|---------|--------|------|
| Accuracy | ~98% | ≥98% | Tidak turun |
| False Positive Rate | <1% | <2% | Acceptable trade-off |
| False Negative Rate | ~2% | <5% | Improved detection range |
| Latency (Layer 2) | N/A | <100ms | Acceptable vs 1000ms LLM |
| Pattern Maintenance | ~1x/month | 0x/month (auto) | Reduced manual work |
| Time to Handle New Category | ~3 days | Real-time | Auto-adapt |

### Rollback Triggers:

❌ **Rollback if ANY of these happen:**
1. Accuracy drops > 3%
2. False positive rate > 5%
3. Latency > 200ms (semantic layer)
4. User complaints about false rejections > 2x baseline

---

## Cost-Benefit Analysis

### CURRENT (Rule-Based)
```
Pros:
  + No extra infrastructure
  + 0ms latency for matches
  + 100% transparent (just regex)
  + Minimal maintenance (so far)

Cons:
  - Manual pattern updates needed
  - Limited to known keywords
  - Regex explosion risk (complexity)
  - ~2% false negatives (new variations)
  
Cost: ~1 hour/month maintenance (currently)
```

### WITH SEMANTIC LAYER
```
Pros:
  + Auto-detect new variations
  + Semantic understanding (not keyword-based)
  + Better UX (fewer false rejections)
  + Scales to 100+ categories easily
  + No more regex complexity

Cons:
  - 100ms extra latency (acceptable)
  - Needs tuning (threshold parameter)
  - More complex code
  - Embedding service must be stable

Cost: ~4 hours implementation + 30 min/month monitoring
Benefit: Save ~45 min/month on pattern maintenance
```

### ROI Calculation:
```
If pattern updates > 2x/month:
  Current cost: 2+ hours/month
  Semantic cost: 30 min/month
  Savings: ~1.5+ hours/month
  Payoff: 4 hours implementation / 1.5 hours saved = 2.7 months ✓

If pattern updates < 1x/month:
  Current cost: ~1 hour/month
  Semantic cost: 30 min/month
  Savings: 30 min/month
  Payoff: 4 hours / 0.5 hours = 8 months (borderline)
```

**Recommendation:**
- **Now (April 2026):** Keep current (rule-based only)
- **Later (Oct 2026):** Evaluate & Plan migration
- **Future (Jan+ 2027):** Implement semantic layer if metrics justify

---

## Implementation Timeline

```
Current Phase (Apr 2026 - Sep 2026): 6 months
├─ Continue rule-based approach
├─ Add patterns as needed
├─ Monitor metrics
└─ Prepare migration plan

Preparation Phase (Oct 2026): 1 month
├─ Design semantic categories
├─ Create test data sets
├─ Document anchor texts
└─ Get team alignment

Implementation Phase (Nov 2026): 2-3 weeks
├─ Code semantic detector
├─ Integration tests
├─ Performance validation
└─ Documentation

Monitoring Phase (Dec 2026 - ongoing):
├─ Track metrics
├─ Gather user feedback
├─ Quarterly tuning
└─ Continuous improvement
```

---

## FAQ: Rule-Based vs Semantic

### Q: Jika sudah ada LLM fallback, kenapa perlu semantic layer?
**A:** 
- LLM: Akurat tapi LAMBAT (1 detik)
- Semantic: Fast (100ms) + Akurat (95%+)
- Semantic adalah "middleman" untuk ambiguous cases
- Mengurangi beban pada LLM (fewer calls)

### Q: Apakah embedding service menambah latency?
**A:**
- Embedding satu pertanyaan: ~100ms (satu kali per session, bisa cached)
- Jauh lebih cepat dari LLM inference (1000ms)
- Trade-off: +100ms latency untuk +10% akurasi ✓

### Q: Bagaimana jika embedding model berubah?
**A:**
- Anchor embeddings perlu di-refresh
- Automated: Detect model version mismatch, re-embed
- Tidak ada breaking changes (just re-encode old anchors)

### Q: Perlukah retrain embedding model?
**A:**
- NO - gunakan pre-trained model existing (all-mpnet-base-v2)
- Model universal, tidak perlu custom training
- Transfer learning sudah optimal untuk semantic clustering

### Q: Bagaimana dengan bahasa Indonesia support?
**A:**
- all-mpnet-base-v2: Multilingual, support Indonesian ✓
- Anchor texts sudah in Indonesian
- No additional training needed

---

## Contacts & Support

**If you have questions:**
- Review `semantic_detector_example.py` for code
- Check `BEST_PRACTICE_ANALYSIS.md` for theory
- Refer to `FIX_OUT_OF_SCOPE_DETECTION.md` for current approach

**Before migrating, consult:**
- [ ] Backend team (embedding service stability)
- [ ] ML team (threshold tuning methodology)
- [ ] DevOps team (monitoring & alerting setup)
