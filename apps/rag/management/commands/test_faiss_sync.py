"""
management/commands/test_faiss_sync.py

Diagnostic command untuk memverifikasi sinkronisasi FAISS VectorStore
dengan database, menguji cosine similarity secara manual, dan membandingkan
skor raw FAISS vs skor cross-encoder reranker.

Usage:
    python manage.py test_faiss_sync
    python manage.py test_faiss_sync --keyword "kartu akses" --doc-type ORDER_LINK
    python manage.py test_faiss_sync --keyword "kertas" --top-k 5
"""

from django.core.management.base import BaseCommand

import numpy as np
import struct
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Diagnose FAISS sync: embed a keyword, run raw FAISS search, compare "
        "manual cosine similarity of stored chunk embeddings, and check cross-encoder scores."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--keyword",
            type=str,
            default="kertas",
            help="Keyword to embed and search (default: kertas)",
        )
        parser.add_argument(
            "--doc-type",
            type=str,
            default="ORDER_LINK",
            help="Filter results by doc_type (default: ORDER_LINK)",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="Number of results to return (default: 5)",
        )

    def handle(self, *args, **options):
        keyword = options["keyword"]
        doc_type = options["doc_type"]
        top_k = options["top_k"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== FAISS SYNC DIAGNOSTIC ===\n"
            f"Keyword : '{keyword}'\n"
            f"doc_type: {doc_type}\n"
            f"top_k   : {top_k}\n"
        ))

        # ── 1. Load singleton services ────────────────────────────────────────
        self.stdout.write("\n[1/5] Loading singleton services...")
        try:
            from apps.rag.apps import get_vector_store, get_embedding_service
            embedding_service = get_embedding_service()
            vector_store = get_vector_store()

            if embedding_service is None:
                self.stdout.write(self.style.ERROR("  EmbeddingService singleton is None. Aborting."))
                return
            if vector_store is None:
                self.stdout.write(self.style.ERROR("  VectorStore singleton is None. Aborting."))
                return

            self.stdout.write(self.style.SUCCESS(
                f"  EmbeddingService: {type(embedding_service).__name__} ✓\n"
                f"  VectorStore     : {type(vector_store).__name__} ✓"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Failed to load services: {e}"))
            return

        # ── 2. Embed the keyword ──────────────────────────────────────────────
        self.stdout.write(f"\n[2/5] Embedding keyword: '{keyword}'...")
        try:
            query_vector = embedding_service.embed_text(keyword)
            query_np = np.array(query_vector, dtype="float32")
            query_norm = float(np.linalg.norm(query_np))
            self.stdout.write(self.style.SUCCESS(
                f"  Dimension    : {query_np.shape[0]}\n"
                f"  L2 norm      : {query_norm:.4f}  (expected ≈1.0 after normalization)"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Embedding failed: {e}"))
            return

        # ── 3. Raw FAISS search (load_embeddings first) ───────────────────────
        self.stdout.write(f"\n[3/5] Raw FAISS search (top {top_k * 5} over-fetch)...")
        try:
            vector_store.load_embeddings()  # force reload from DB
            raw_results = vector_store.search(query_vector, top_k=top_k * 5)

            if not raw_results:
                self.stdout.write(self.style.WARNING("  FAISS returned 0 results!"))
                self.stdout.write("  → Check that DocumentChunk rows exist and have embedding_vector set.")
            else:
                self.stdout.write(f"  FAISS returned {len(raw_results)} raw results:")
                from apps.rag.models import DocumentChunk
                for i, r in enumerate(raw_results[:top_k]):
                    try:
                        chunk = DocumentChunk.objects.select_related("document").get(
                            id=r["document_chunk_id"]
                        )
                        chunk_doc_type = chunk.document.doc_type if chunk.document else "?"
                        content_preview = chunk.content[:80].replace("\n", " ")
                        score_display = f"{r['score']:.6f}"
                        marker = " ✓" if chunk_doc_type == doc_type else ""
                        self.stdout.write(
                            f"  [{i+1}] score={score_display}  doc_type={chunk_doc_type}{marker}\n"
                            f"       {content_preview}..."
                        )
                    except DocumentChunk.DoesNotExist:
                        self.stdout.write(f"  [{i+1}] chunk_id={r['document_chunk_id']} NOT FOUND in DB!")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  FAISS search failed: {e}"))
            import traceback; traceback.print_exc()
            return

        # ── 4. Manual cosine similarity for doc_type chunks ──────────────────
        self.stdout.write(f"\n[4/5] Manual cosine similarity against all {doc_type} chunks...")
        try:
            from apps.rag.models import DocumentChunk

            # Normalize query for cosine sim
            query_normalized = query_np / (np.linalg.norm(query_np) + 1e-8)

            chunks_qs = DocumentChunk.objects.filter(
                document__doc_type=doc_type
            ).exclude(embedding_vector=None).select_related("document")

            similarities = []
            for chunk in chunks_qs:
                try:
                    stored_vec = embedding_service.from_bytes(chunk.embedding_vector)
                    if stored_vec is None:
                        continue
                    stored_np = np.array(stored_vec, dtype="float32")
                    stored_normalized = stored_np / (np.linalg.norm(stored_np) + 1e-8)
                    cos_sim = float(np.dot(query_normalized, stored_normalized))
                    dim_ok = stored_np.shape[0] == query_np.shape[0]
                    similarities.append((cos_sim, chunk, dim_ok))
                except Exception as ex:
                    self.stdout.write(
                        self.style.WARNING(f"  Chunk {chunk.id} decode error: {ex}")
                    )

            if not similarities:
                self.stdout.write(self.style.WARNING(
                    f"  No {doc_type} chunks with valid embeddings found."
                ))
            else:
                similarities.sort(key=lambda x: x[0], reverse=True)
                self.stdout.write(f"  Top {min(top_k, len(similarities))} manual cosine similarities:")
                for cos_sim, chunk, dim_ok in similarities[:top_k]:
                    content_preview = chunk.content[:80].replace("\n", " ")
                    dim_label = "✓" if dim_ok else f"✗ DIM MISMATCH (stored={np.array(embedding_service.from_bytes(chunk.embedding_vector)).shape[0]})"
                    kw_hit = keyword.lower() in chunk.content.lower()
                    kw_label = " [KEYWORD HIT]" if kw_hit else ""
                    self.stdout.write(
                        f"  cos_sim={cos_sim:.6f}  dim={dim_label}{kw_label}\n"
                        f"    {content_preview}..."
                    )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Manual similarity failed: {e}"))
            import traceback; traceback.print_exc()

        # ── 5. Cross-encoder reranker score ──────────────────────────────────
        self.stdout.write(f"\n[5/5] Cross-encoder reranker score for '{keyword}' vs top chunks...")
        try:
            from apps.rag.services.retrieval import _get_reranker, retrieve_context
            reranker = _get_reranker()
            if reranker is None:
                self.stdout.write(self.style.WARNING(
                    "  Reranker model not available. Skipping this step."
                ))
            else:
                # Grab chunks that contain the keyword
                hits = [
                    c for c in chunks_qs
                    if keyword.lower() in c.content.lower()
                ][:top_k]
                if not hits:
                    self.stdout.write(f"  No {doc_type} chunks contain keyword '{keyword}'.")
                else:
                    pairs = [[keyword, h.content] for h in hits]
                    scores = reranker.predict(pairs)
                    self.stdout.write(f"  Reranker scores for keyword='{keyword}':")
                    for score, hit in zip(scores, hits):
                        content_preview = hit.content[:60].replace("\n", " ")
                        score_label = self.style.SUCCESS(f"{score:.6f}") if score > 0 else self.style.ERROR(f"{score:.6f} (FILTERED OUT)")
                        self.stdout.write(f"    score={score_label}  {content_preview}...")

                # Also test the enriched query
                enriched = f"pengadaan {keyword}"
                self.stdout.write(f"\n  Reranker scores for ENRICHED query='{enriched}':")
                pairs_enriched = [[enriched, h.content] for h in hits]
                scores_enriched = reranker.predict(pairs_enriched)
                for score, hit in zip(scores_enriched, hits):
                    content_preview = hit.content[:60].replace("\n", " ")
                    score_label = self.style.SUCCESS(f"{score:.6f}") if score > 0 else self.style.ERROR(f"{score:.6f}")
                    self.stdout.write(f"    score={score_label}  {content_preview}...")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Reranker test failed: {e}"))
            import traceback; traceback.print_exc()

        self.stdout.write(self.style.SUCCESS("\n=== Diagnostic complete ===\n"))
        self.stdout.write(
            "INTERPRETATION GUIDE:\n"
            "  cos_sim > 0.35 → Embedding space is synced & semantically relevant\n"
            "  cos_sim < 0.10 → LIKELY embedding model mismatch (chunk stored with different model)\n"
            "  reranker > 0.0 → Cross-encoder considers the pair relevant\n"
            "  reranker ≈ 0.001 → Query too short/generic for cross-encoder; use enriched query\n"
            "  reranker < 0.0 → Filtered out (chunk is not relevant to this query)\n"
        )
