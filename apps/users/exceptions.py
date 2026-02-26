"""
Custom exception handlers untuk REST API
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler untuk REST API
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        # Add custom format
        custom_response = {
            'success': False,
            'error': response.data,
            'status_code': response.status_code
        }
        
        response.data = custom_response
    else:
        # Unhandled exception
        logger.error(f"Unhandled exception: {exc}")
        response = Response({
            'success': False,
            'error': 'Terjadi kesalahan pada server',
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response
