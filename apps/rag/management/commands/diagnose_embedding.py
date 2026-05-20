"""
Diagnostic command: python manage.py diagnose_embedding

Investigates root cause of low similarity score for ORDER_LINK chunks.
Checks:
  1. Chunk content integrity (is it complete or truncated?)
  2. Doc_type correctness
  3. Cosine similarity between query and stored embedding vector
  4. Singleton embedding service identity
"""

import re
import numpy as np
from django.core.management.base import BaseCommand
from apps.rag.models import DocumentChunk


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32).flatten()
    b = b.astype(np.float32).flatten()
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


SEP = "=" * 60


class Command(BaseCommand):
    help = 'Diagnose embedding mismatch for ORDER_LINK chunks (specifically proyektor).'

    def handle(self, *args, **options):
        from apps.rag.apps import get_embedding_service
        from apps.rag.services.embedding import EmbeddingService

        # --- Step 0: Singleton identity check ---
        self.stdout.write("\n" + SEP)
        self.stdout.write("STEP 0: Singleton Identity Check")
        self.stdout.write(SEP)
        singleton_es = get_embedding_service()
        fresh_es = EmbeddingService()
        self.stdout.write("  Singleton id : %d" % id(singleton_es))
        self.stdout.write("  Fresh inst id: %d" % id(fresh_es))
        if singleton_es is not None:
            self.stdout.write("  Singleton model id: %d" % id(singleton_es.model))
        self.stdout.write("  Fresh model   id : %d" % id(fresh_es.model))
        if singleton_es is not None and singleton_es.model is fresh_es.model:
            self.stdout.write("[WARN] Same model object - they share weights (OK)")
        else:
            self.stdout.write(self.style.ERROR(
                "[ERROR] DIFFERENT model instances! This IS the embedding mismatch bug."
            ))

        embedding_service = singleton_es if singleton_es is not None else fresh_es

        # --- Step 1: Find chunks containing "proyektor" ---
        self.stdout.write("\n" + SEP)
        self.stdout.write("STEP 1: Database Chunk Inspection")
        self.stdout.write(SEP)
        keyword = "proyektor"
        chunks = DocumentChunk.objects.filter(content__icontains=keyword)
        self.stdout.write("  Found %d chunk(s) containing '%s'" % (chunks.count(), keyword))

        if not chunks.exists():
            self.stdout.write(self.style.ERROR(
                "\n  [ERROR] No chunks found for '%s'!\n"
                "    a) The document has NOT been re-ingested after the refactor.\n"
                "    b) The chunker is still splitting incorrectly.\n"
                "  ACTION: Re-upload your ORDER_LINK document via the dashboard." % keyword
            ))

        for chunk in chunks:
            self.stdout.write("\n  -- Chunk ID: %d --" % chunk.id)
            self.stdout.write("     doc_type  : %s" % chunk.document.doc_type)
            self.stdout.write("     char len  : %d" % len(chunk.content))
            has_nama_form = "NAMA FORM:" in chunk.content
            has_trigger   = "TRIGGER KEYWORD:" in chunk.content
            has_link      = "Link:" in chunk.content or "url:" in chunk.content.lower()
            self.stdout.write("     NAMA FORM present      : %s" % ("OK" if has_nama_form else "MISSING"))
            self.stdout.write("     TRIGGER KEYWORD present: %s" % ("OK" if has_trigger  else "MISSING"))
            self.stdout.write("     Link present           : %s" % ("OK" if has_link     else "MISSING"))
            self.stdout.write("\n     -- Content Preview --\n")
            self.stdout.write(chunk.content[:800])
            if len(chunk.content) > 800:
                self.stdout.write("\n     ... [%d chars truncated]" % (len(chunk.content) - 800))

            # --- Step 2: Cosine Similarity Test ---
            self.stdout.write("\n  -- Step 2: Cosine Similarity Test --")
            if not chunk.embedding_vector:
                self.stdout.write(self.style.ERROR("     [ERROR] embedding_vector is NULL - chunk was never embedded!"))
                continue

            stored_vec = embedding_service.from_bytes(chunk.embedding_vector)
            self.stdout.write("     stored vector dim : %d" % stored_vec.shape[0])
            self.stdout.write("     stored vector norm: %.4f" % np.linalg.norm(stored_vec))

            queries = [
                "proyektor",
                "pengadaan proyektor",
                "saya ingin melakukan pengadaan proyektor untuk divisi saya",
                "Multimedia and Sound System",
            ]

            for q in queries:
                query_vec = embedding_service.embed_text(q)
                sim = cosine_similarity(query_vec, stored_vec)
                if sim > 0.3:
                    label = self.style.SUCCESS("GOOD    (%.4f)" % sim)
                elif sim > 0.1:
                    label = self.style.WARNING("MODERATE (%.4f)" % sim)
                else:
                    label = self.style.ERROR("LOW      (%.4f) <- possible mismatch!" % sim)
                self.stdout.write("     Query: %-55s -> sim: %s" % (("'%s'" % q)[:55], label))

        # --- Step 3: All ORDER_LINK chunks overview ---
        self.stdout.write("\n" + SEP)
        self.stdout.write("STEP 3: All ORDER_LINK chunks overview")
        self.stdout.write(SEP)
        order_chunks = DocumentChunk.objects.filter(document__doc_type="ORDER_LINK")
        self.stdout.write("  Total ORDER_LINK chunks: %d" % order_chunks.count())
        for c in order_chunks:
            has_form = "NAMA FORM:" in c.content
            has_link = "Link:" in c.content or "url:" in c.content.lower()
            status_str = "OK" if (has_form and has_link) else "INCOMPLETE (missing NAMA FORM or Link)"
            self.stdout.write("  ID %4d | len=%4d | %s" % (c.id, len(c.content), status_str))
            if has_form:
                m = re.search(r'NAMA FORM:\s*(.+)', c.content)
                if m:
                    self.stdout.write("           NAMA FORM: %s" % m.group(1).strip())

        self.stdout.write("\n" + SEP)
        self.stdout.write("DIAGNOSIS COMPLETE")
        self.stdout.write(SEP)
        self.stdout.write(
            "If all chunks are INCOMPLETE -> Re-upload documents via the dashboard.\n"
            "If similarity is near 0 despite correct content -> Embedding model mismatch.\n"
            "   Fix: ensure dashboard upload view passes get_embedding_service(),\n"
            "        then run: python manage.py reembed_all\n"
        )
