import os
import sys
import json
import traceback

# Ensure project root is on path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from apps.rag.apps import get_embedding_service
from apps.rag.models import DocumentChunk
import numpy as np

result = {"status": "ok"}

try:
    es = get_embedding_service()
    if es is None:
        result.update({"error": "no_embedding_service"})
        print(json.dumps(result))
        sys.exit(0)

    q = es.embed_text('flashdisk')

    chunk = DocumentChunk.objects.filter(content__icontains='flashdisk').first()
    if not chunk:
        result.update({"error": "no_chunk_found"})
        print(json.dumps(result))
        sys.exit(0)

    try:
        stored = es.from_bytes(chunk.embedding_vector) if chunk.embedding_vector else None
    except Exception as e:
        result.update({"error": "from_bytes_failed", "exc": str(e)})
        print(json.dumps(result))
        sys.exit(0)

    if stored is None:
        result.update({"error": "no_stored_vector"})
        print(json.dumps(result))
        sys.exit(0)

    qn = q / (np.linalg.norm(q) + 1e-12)
    sn = stored / (np.linalg.norm(stored) + 1e-12)
    cosine = float(np.dot(qn, sn))

    result.update({
        "chunk_id": int(chunk.id),
        "cosine": float(cosine),
        "q_norm": float(np.linalg.norm(q)),
        "s_norm": float(np.linalg.norm(stored)),
    })

except Exception as e:
    result = {"error": "exception", "exc": str(e), "tb": traceback.format_exc()}

print(json.dumps(result))
