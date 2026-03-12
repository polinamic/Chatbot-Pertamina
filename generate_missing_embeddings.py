"""
Script untuk generate embeddings untuk semua DocumentChunk yang embedding_vector-nya NULL
Run: python generate_missing_embeddings.py
"""

import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.rag.models import DocumentChunk
from apps.rag.services.embedding import EmbeddingService
import numpy as np

# Initialize embedding service
embedding_service = None

def init_embedding_service():
    """Initialize embedding service (lazy load)"""
    global embedding_service
    if embedding_service is None:
        print("[*] Loading embedding model...")
        embedding_service = EmbeddingService()
        print("[OK] Model loaded!\n")
    return embedding_service

def generate_missing_embeddings(batch_size=50):
    """
    Generate embeddings untuk semua DocumentChunk dengan NULL embedding_vector
    """
    # Initialize service
    service = init_embedding_service()
    
    # Query semua chunks yang NULL
    null_chunks = DocumentChunk.objects.filter(embedding_vector__isnull=True).order_by('id')
    total = null_chunks.count()
    
    if total == 0:
        print("✓ Semua chunks sudah memiliki embedding!")
        return
    
    print(f"[INFO] Total chunks dengan NULL embedding: {total}")
    print(f"[INFO] Batch size: {batch_size}\n")
    
    processed = 0
    failed = 0
    
    # Process dalam batch untuk efisiensi
    for i in range(0, total, batch_size):
        batch = null_chunks[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        print(f"[BATCH] {batch_num}/{total_batches}")
        
        # Extract texts untuk batch embedding
        texts = [chunk.content for chunk in batch if chunk.content]
        
        if texts:
            try:
                # Generate embeddings untuk seluruh batch sekaligus (lebih cepat)
                embeddings = service.embed_batch(texts)
                
                text_idx = 0
                for chunk in batch:
                    if chunk.content:
                        # Convert embedding ke bytes format untuk disimpan
                        embedding_bytes = EmbeddingService.to_bytes(embeddings[text_idx])
                        chunk.embedding_vector = embedding_bytes
                        chunk.save(update_fields=['embedding_vector'])
                        processed += 1
                        text_idx += 1
                        doc_title = chunk.document.title if hasattr(chunk.document, 'title') else str(chunk.document)[:40]
                        print(f"  [+] Chunk {chunk.id} - {doc_title}")
                    else:
                        failed += 1
                        print(f"  [-] Chunk {chunk.id} - Content kosong")
            except Exception as e:
                failed += len(texts)
                print(f"  [ERROR] Batch error: {str(e)[:50]}")
        else:
            failed += len(batch)
            print(f"  [SKIP] Batch tanpa content yang valid")
        
        print(f"  [PROGRESS] {min(i + batch_size, total)}/{total}\n")
    
    # Summary
    print("\n" + "="*60)
    print("[SUMMARY]")
    print("="*60)
    print(f"[+] Generated: {processed}")
    print(f"[-] Failed: {failed}")
    print(f"[%] Success rate: {(processed/(processed+failed)*100):.1f}%" if (processed + failed) > 0 else "0%")
    print("="*60)

def verify_embeddings():
    """
    Verify total embeddings yang ada di database
    """
    total = DocumentChunk.objects.count()
    with_embedding = DocumentChunk.objects.filter(embedding_vector__isnull=False).count()
    null_embedding = DocumentChunk.objects.filter(embedding_vector__isnull=True).count()
    empty_content = DocumentChunk.objects.filter(content__exact='').count()
    
    print("\n[VERIFICATION]")
    print("="*60)
    print(f"Total chunks: {total}")
    print(f"[+] With embedding: {with_embedding} ({(with_embedding/total*100) if total > 0 else 0:.1f}%)")
    print(f"[-] NULL embedding: {null_embedding}")
    print(f"  - Empty content: {empty_content}")
    print(f"  - Other: {null_embedding - empty_content}")
    print("="*60)

if __name__ == '__main__':
    print("\n[*] GENERATE MISSING EMBEDDINGS")
    print("="*60 + "\n")
    
    try:
        generate_missing_embeddings(batch_size=50)
        verify_embeddings()
        print("\n[OK] DONE!")
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
