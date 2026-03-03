from apps.rag.models import DocumentChunk
from apps.rag.services.embedding import EmbeddingService


def smart_chunking(content: str):
    """
    Split berbasis paragraf.
    Jika paragraf terlalu panjang, pecah lagi.
    """

    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    chunks = []

    for para in paragraphs:

        # Jika paragraf pendek, langsung pakai
        if len(para) <= 800:
            chunks.append(para)

        # Jika terlalu panjang, split lagi
        else:
            for i in range(0, len(para), 800):
                chunks.append(para[i:i+800])

    return chunks


def ingest_document(document):

    # Hapus chunk lama
    document.chunks.all().delete()

    if not document.content:
        return

    embedding_service = EmbeddingService()

    chunks = smart_chunking(document.content)

    for index, chunk_text in enumerate(chunks):

        vector = embedding_service.embed_text(chunk_text)

        DocumentChunk.objects.create(
            document=document,
            chunk_index=index,
            content=chunk_text,
            embedding_vector=embedding_service.to_bytes(vector)
        )