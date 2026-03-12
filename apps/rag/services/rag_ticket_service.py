from apps.rag.services.retrieval import retrieve_context
from apps.rag.models import DocumentChunk


def get_chunk_text(chunk_id):

    try:
        chunk = DocumentChunk.objects.get(id=chunk_id)
        return chunk.content
    except:
        return ""


def get_ticket_guide(question, vector_store, embedding_service):

    results = retrieve_context(
        question,
        vector_store,
        embedding_service
    )

    if not results:
        return None

    texts = []

    for r in results[:3]:

        text = get_chunk_text(r["document_chunk_id"])

        if text:
            texts.append(text)

    return "\n\n".join(texts)