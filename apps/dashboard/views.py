from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
import json

from apps.chatbot.models import Conversation, Message
from apps.users.models import User
from apps.core.models import ActivityLog # Document dihapus dari import core

# --- PERBAIKAN IMPORT MODEL RAG ---
# Sekarang kita menggunakan Document dari RAG sebagai sumber kebenaran utama
from apps.rag.models import Document, DocumentChunk

# Import ingestion service untuk chunking yang lebih baik
from apps.rag.services.ingestion_service import category_aware_chunking, ingest_document

# Optional import - will skip embedding if not available
try:
    from apps.rag.services.embedding import EmbeddingService
    HAS_EMBEDDING_SERVICE = True
except ImportError:
    HAS_EMBEDDING_SERVICE = False


def is_admin_or_staff(user):
    """Check if user is admin or staff"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_admin_or_staff)
def dashboard_home(request):
    """Dashboard homepage dengan overview statistik lengkap"""
    
    # Statistik Dasar
    total_users = User.objects.count()
    total_conversations = Conversation.objects.count()
    total_messages = Message.objects.count()
    total_documents = Document.objects.count()
    
    # Statistik Hari Ini
    today = timezone.now().date()
    conversations_today = Conversation.objects.filter(created_at__date=today).count()
    messages_today = Message.objects.filter(created_at__date=today).count()
    users_today = User.objects.filter(last_login__date=today).count()
    
    # Statistik 7 Hari & 30 Hari
    seven_days_ago = timezone.now() - timedelta(days=7)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    conversations_week = Conversation.objects.filter(created_at__gte=seven_days_ago).count()
    conversations_month = Conversation.objects.filter(created_at__gte=thirty_days_ago).count()
    
    # Avg response time (simulated)
    avg_response_time = 0.45  # dalam detik, ini bisa dari custom metric
    
    # System health
    documents_processed = Document.objects.count()
    documents_pending = 0
    
    # Top Conversations (Most Messages)
    top_conversations = Conversation.objects.annotate(
        message_count=Count('message_set')
    ).order_by('-message_count')[:5]
    
    # Recent Conversations
    recent_conversations = Conversation.objects.select_related('user').order_by(
        '-updated_at'
    )[:10]
    
    # Recent Activity
    recent_activity = ActivityLog.objects.order_by('-created_at')[:8]
    
    # Penggunaan per hari (7 hari terakhir)
    daily_stats = []
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        conv_count = Conversation.objects.filter(created_at__date=date).count()
        msg_count = Message.objects.filter(created_at__date=date).count()
        daily_stats.append({
            'date': date.strftime('%a'),
            'date_iso': date.isoformat(),
            'count': conv_count,
            'messages': msg_count
        })
    
    context = {
        'total_users': total_users,
        'total_conversations': total_conversations,
        'total_messages': total_messages,
        'total_documents': total_documents,
        'conversations_today': conversations_today,
        'messages_today': messages_today,
        'users_today': users_today,
        'conversations_week': conversations_week,
        'conversations_month': conversations_month,
        'avg_response_time': avg_response_time,
        'documents_processed': documents_processed,
        'documents_pending': documents_pending,
        'top_conversations': top_conversations,
        'recent_conversations': recent_conversations,
        'recent_activity': recent_activity,
        'daily_stats': json.dumps(daily_stats),
    }
    
    return render(request, 'dashboard/index.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def conversations_management(request):
    """Manajemen conversations dengan monitoring detail"""
    
    conversations = Conversation.objects.select_related('user').annotate(
        message_count=Count('message_set')
    ).order_by('-created_at')
    
    # Filter & Search
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search', '')
    
    if status_filter == 'archived':
        conversations = conversations.filter(is_archived=True)
    elif status_filter == 'active':
        conversations = conversations.filter(is_archived=False)
    
    if search_query:
        conversations = conversations.filter(
            Q(title__icontains=search_query) | 
            Q(user__username__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(conversations, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_conversations': conversations.count(),
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'dashboard/conversations.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def chat_detail(request, conversation_id):
    """View detail conversation dengan semua messages"""
    
    conversation = get_object_or_404(Conversation, id=conversation_id)
    messages = conversation.message_set.all().order_by('created_at')
    
    context = {
        'conversation': conversation,
        'messages': messages,
        'user': conversation.user,
    }
    
    return render(request, 'dashboard/chat_detail.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def users_management(request):
    """Manajemen users dengan statistik engagement"""
    
    users = User.objects.annotate(
        conversation_count=Count('conversations'),
        message_count=Count('conversations__message_set')
    ).order_by('-date_joined')
    
    # Filter
    role_filter = request.GET.get('role')
    if role_filter == 'staff':
        users = users.filter(is_staff=True)
    elif role_filter == 'admin':
        users = users.filter(is_superuser=True)
    elif role_filter == 'users':
        users = users.filter(is_staff=False, is_superuser=False)
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_users': users.count(),
        'role_filter': role_filter,
    }
    
    return render(request, 'dashboard/users.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def documents_management(request):
    """Manajemen documents/SOP"""
    
    documents = Document.objects.select_related('uploaded_by').order_by('-created_at')
    
    # Filter
    status_filter = request.GET.get('status')
    
    # Pagination
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    stats = {
        'total': Document.objects.count(),
        'processed': Document.objects.count(),
        'pending': 0,
    }
    
    context = {
        'page_obj': page_obj,
        'total_documents': documents.count(),
        'status_filter': status_filter,
        'stats': stats,
    }
    
    return render(request, 'dashboard/documents.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
@require_http_methods(["GET"])
def analytics(request):
    """Analytics & reporting comprehensive"""
    
    period = request.GET.get('period', '30')
    days = int(period) if period.isdigit() else 30
    
    start_date = timezone.now() - timedelta(days=days)
    
    # Conversations per day
    conversations_data = []
    for i in range(days, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        count = Conversation.objects.filter(created_at__date=date).count()
        conversations_data.append({
            'date': date.isoformat(),
            'count': count
        })
    
    # Messages per conversation (average)
    avg_messages_per_conv = Message.objects.filter(
        created_at__gte=start_date
    ).values('conversation').annotate(
        count=Count('id')
    ).aggregate(avg=Avg('count'))['avg'] or 0
    
    # Top users by conversation count
    top_users = User.objects.annotate(
        conv_count=Count('conversations')
    ).filter(
        conversations__created_at__gte=start_date
    ).order_by('-conv_count')[:10]
    
    # Most active hours
    message_stats = {
        'total_messages': Message.objects.filter(created_at__gte=start_date).count(),
        'total_conversations': Conversation.objects.filter(created_at__gte=start_date).count(),
        'avg_messages_per_conv': round(avg_messages_per_conv, 2),
    }
    
    context = {
        'period': period,
        'conversations_data': json.dumps(conversations_data),
        'message_stats': message_stats,
        'top_users': top_users,
    }
    
    return render(request, 'dashboard/analytics.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def knowledge_base(request):
    """Knowledge Base Manager - untuk manage SOP/Dokumen"""
    
    documents = Document.objects.select_related('uploaded_by').order_by('-created_at')
    
    paginator = Paginator(documents, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    stats = {
        'total': Document.objects.count(),
        'processed': Document.objects.count(),
        'pending': 0,
        'today': Document.objects.filter(created_at__date=timezone.now().date()).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
    }
    
    return render(request, 'dashboard/knowledge_base.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def chat_monitoring(request):
    """Real-time Chat Monitoring"""
    
    conversations = Conversation.objects.select_related('user').annotate(
        message_count=Count('message_set')
    ).order_by('-updated_at')[:50]
    
    stats = {
        'active_conversations': Conversation.objects.filter(is_archived=False).count(),
        'total_messages_today': Message.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'avg_messages_per_conv': Message.objects.values('conversation').annotate(
            count=Count('id')
        ).aggregate(avg=Avg('count'))['avg'] or 0,
    }
    
    context = {
        'conversations': conversations,
        'stats': stats,
    }
    
    return render(request, 'dashboard/chat_monitoring.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def audit_trail(request):
    """Activity Audit Trail - semua aktivitas user"""
    
    activity_logs = ActivityLog.objects.order_by('-created_at')
    
    # Filter berdasarkan action
    action_filter = request.GET.get('action')
    if action_filter:
        activity_logs = activity_logs.filter(action=action_filter)
    
    # Filter berdasarkan tanggal
    date_filter = request.GET.get('date')
    if date_filter:
        activity_logs = activity_logs.filter(created_at__date=date_filter)
    
    paginator = Paginator(activity_logs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    stats = {
        'total_logs': ActivityLog.objects.count(),
        'logs_today': ActivityLog.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'date_filter': date_filter,
        'stats': stats,
    }
    
    return render(request, 'dashboard/audit_trail.html', context)


@login_required
@user_passes_test(is_admin_or_staff)
def system_settings(request):
    """System Settings & Configuration"""
    
    # Placeholder settings - bisa diperluas dengan database model
    settings_data = {
        'system_name': 'SITI',
        'system_version': '1.0.0',
        'model': 'Llama 3 (8B Parameters)',
        'deployment': 'On-Premise',
        'database': 'MSSQL',
        'rag_enabled': True,
        'max_document_size': '50MB',
        'supported_formats': ['PDF', 'DOCX', 'TXT', 'MD'],
        'auto_refresh_interval': 30,  # seconds
    }
    
    context = {
        'settings': settings_data,
    }
    
    return render(request, 'dashboard/system_settings.html', context)


# ==================== API ENDPOINTS ====================

@login_required
@user_passes_test(is_admin_or_staff)
@require_http_methods(["GET"])
def dashboard_api_stats(request):
    """API untuk mendapatkan stats real-time (JSON)"""
    
    today = timezone.now().date()
    
    return JsonResponse({
        'status': 'success',
        'data': {
            'total_users': User.objects.count(),
            'total_conversations': Conversation.objects.count(),
            'total_messages': Message.objects.count(),
            'total_documents': Document.objects.count(),
            'conversations_today': Conversation.objects.filter(created_at__date=today).count(),
            'messages_today': Message.objects.filter(created_at__date=today).count(),
            'active_conversations': Conversation.objects.filter(is_archived=False).count(),
        }
    })


@login_required(login_url='/auth/login/')
@user_passes_test(is_admin_or_staff)
@require_http_methods(["POST"])
def api_upload_document(request):
    """API untuk upload document/SOP dengan RAG processing yang disatukan"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f'Upload request from user: {request.user.username}')
    logger.info(f'Request FILES: {list(request.FILES.keys())}')
    
    if 'file' not in request.FILES:
        logger.warning('No file provided in request')
        return JsonResponse({'status': 'error', 'message': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    # Ambil doc_type dari form dropdown HTML (default ke TROUBLESHOOT jika tidak ada)
    doc_type = request.POST.get('doc_type', 'TROUBLESHOOT')
    
    logger.info(f'File received: {file.name}, size: {file.size} bytes, type: {doc_type}')
    
    # Validasi file size
    max_size = 50 * 1024 * 1024  # 50MB
    if file.size > max_size:
        logger.warning(f'File too large: {file.size} bytes')
        return JsonResponse({'status': 'error', 'message': 'File too large'}, status=400)
    
    # Validasi file type
    allowed_extensions = ['txt', 'pdf', 'docx', 'md']
    file_ext = file.name.split('.')[-1].lower()
    if file_ext not in allowed_extensions:
        logger.warning(f'Invalid file type: {file_ext}')
        return JsonResponse({'status': 'error', 'message': f'File type not allowed. Allowed: {", ".join(allowed_extensions)}'}, status=400)
    
    logger.info(f'File validation passed. Extension: {file_ext}')
    
    try:
        # Read file content
        try:
            if file_ext == 'txt' or file_ext == 'md':
                content = file.read().decode('utf-8')
            else:
                # For now, just read as text for PDF/DOCX (you can enhance with pdf2image, python-docx later)
                content = file.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Could not read file: {str(e)}'}, status=400)
        
        # --- PERUBAHAN UTAMA: Hanya membuat SATU document record di tabel RAG ---
        doc = Document.objects.create(
            file_name=file.name,
            file_size=file.size,
            file=file,
            uploaded_by=request.user,
            content=content,
            category='Dashboard Upload',
            doc_type=doc_type,
            is_active=True
        )

        # Process document menggunakan ingestion_service yang lengkap
        # Ini akan melakukan chunking, embedding, dan menyimpan chunks
        try:
            ingest_document(doc)
            chunks_created = doc.chunks.count()
            logger.info(f'Document processed successfully with {chunks_created} chunks')
        except Exception as e:
            logger.error(f'Failed to process document: {e}')
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to process document: {str(e)}'
            }, status=500)
        logger.info(f'Document uploaded successfully: {file.name}, Doc ID: {doc.id}, Chunks: {chunks_created}')
        
        return JsonResponse({
            'status': 'success',
            'message': f'Document uploaded successfully ({chunks_created} chunks)',
            'document_id': doc.id,
            'chunks_created': chunks_created
        })
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f'Upload error: {error_msg}')
        logger.error(f'Traceback: {error_trace}')
        return JsonResponse({
            'status': 'error', 
            'message': f'Upload failed: {error_msg}'
        }, status=500)


@login_required
@user_passes_test(is_admin_or_staff)
@require_http_methods(["DELETE"])
def api_delete_document(request, doc_id):
    """API untuk delete document"""
    try:
        # Menghapus langsung dari model RAG (DocumentChunk akan terhapus otomatis via CASCADE)
        document = Document.objects.get(id=doc_id)
        file_name = document.file_name
        document.delete()
        
        # Log activity
        ActivityLog.objects.create(
            action='DELETE',
            description=f'Deleted document: {file_name}',
            user_id=request.user.id,
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Document deleted successfully'
        })
    except Document.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)