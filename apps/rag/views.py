from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from .models import Document, DocumentChunk
from .serializers import DocumentSerializer, DocumentListSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet untuk mengelola documents untuk RAG
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'process']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser()])
    def process(self, request, pk=None):
        """Process document and create embeddings"""
        document = self.get_object()
        
        # TODO: Implement document processing logic
        # 1. Split document into chunks
        # 2. Generate embeddings
        # 3. Store in Pinecone
        
        return Response(
            {'message': 'Document processing started'},
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated()])
    def search(self, request):
        """Search documents using RAG"""
        query = request.data.get('query')
        if not query:
            return Response(
                {'error': 'Query is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Implement RAG search logic
        # 1. Generate query embedding
        # 2. Search in Pinecone
        # 3. Retrieve relevant documents

        return Response({
            'query': query,
            'results': []
        })
