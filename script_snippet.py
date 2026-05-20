from apps.rag.apps import get_embedding_service
from apps.rag.models import DocumentChunk
import numpy as np, sys
es=get_embedding_service()
q=es.embed_text('flashdisk')
chunk=DocumentChunk.objects.filter(content__icontains='flashdisk').first()
print('===FOUND_CHUNK_ID_START===')
print(getattr(chunk,'id',None))
print('===FOUND_CHUNK_ID_END===')
if not chunk:
    print('===NO_CHUNK===')
    sys.exit(0)
try:
    stored = es.from_bytes(chunk.embedding_vector) if chunk.embedding_vector else None
except Exception as e:
    print('===FROM_BYTES_ERROR===', e)
    sys.exit(0)
if stored is None:
    print('===NO_STORED_VECTOR===')
    sys.exit(0)
qn=q/(np.linalg.norm(q)+1e-12)
sn=stored/(np.linalg.norm(stored)+1e-12)
print('===COSINE===', float(np.dot(qn,sn)))
print('===Q_NORM===', float(np.linalg.norm(q)))
print('===S_NORM===', float(np.linalg.norm(stored)))
