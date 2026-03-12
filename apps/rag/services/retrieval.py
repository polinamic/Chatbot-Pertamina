from apps.rag.services.embedding import EmbeddingService
from apps.rag.models import DocumentChunk


def retrieve_context(
    question,
    vector_store,
    embedding_service,
    doc_type=None,
    top_k=5
):
    """
    Retrieve context dari vector store dengan filter doc_type.

    doc_type:
        TROUBLESHOOT  -> solusi troubleshooting
        ESCALATION    -> panduan tiket / IT support
        None          -> semua dokumen
    """

    # generate embedding query
    query_vector = embedding_service.embed_text(question)

    # search vector index
    results = vector_store.search(query_vector, top_k)

    if not results:
        return []

    filtered_results = []

    for r in results:

        try:
            chunk = DocumentChunk.objects.get(id=r["document_chunk_id"])

            # filter berdasarkan tipe dokumen
            if doc_type:

                if not chunk.document.doc_type:
                    continue

                if chunk.document.doc_type != doc_type:
                    continue

            filtered_results.append({
                "document_chunk_id": chunk.id,
                "score": r["score"]
            })

        except DocumentChunk.DoesNotExist:
            continue

    return filtered_results