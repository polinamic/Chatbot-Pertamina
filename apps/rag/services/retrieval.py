from apps.rag.services.embedding import EmbeddingService

def retrieve_context(question, vector_store, embedding_service, top_k=5):

    query_vector = embedding_service.embed_text(question)

    results = vector_store.search(query_vector, top_k)

    return results