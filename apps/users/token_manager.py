"""
Authentication utilities untuk token generation dan verification
"""
import jwt
import datetime
from decouple import config


class TokenManager:
    """
    Manager untuk JWT token generation dan verification
    """
    SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
    ALGORITHM = 'HS256'
    ACCESS_TOKEN_EXPIRE_HOURS = 24
    REFRESH_TOKEN_EXPIRE_DAYS = 7

    @classmethod
    def generate_tokens(cls, user_id, email):
        """
        Generate access token dan refresh token
        
        Args:
            user_id: User ID
            email: User email
            
        Returns:
            dict dengan access_token dan refresh_token
        """
        now = datetime.datetime.utcnow()
        
        # Access Token - expires dalam 24 jam
        access_payload = {
            'user_id': user_id,
            'email': email,
            'type': 'access',
            'exp': now + datetime.timedelta(hours=cls.ACCESS_TOKEN_EXPIRE_HOURS),
            'iat': now
        }
        
        # Refresh Token - expires dalam 7 hari
        refresh_payload = {
            'user_id': user_id,
            'email': email,
            'type': 'refresh',
            'exp': now + datetime.timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS),
            'iat': now
        }
        
        access_token = jwt.encode(access_payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
        refresh_token = jwt.encode(refresh_payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'access_token_expires_in': cls.ACCESS_TOKEN_EXPIRE_HOURS * 3600,  # dalam detik
            'token_type': 'Bearer'
        }

    @classmethod
    def verify_token(cls, token):
        """
        Verify JWT token
        
        Args:
            token: JWT token
            
        Returns:
            dict dengan payload jika valid
            
        Raises:
            jwt.ExpiredSignatureError
            jwt.InvalidTokenError
        """
        return jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])

    @classmethod
    def refresh_access_token(cls, refresh_token):
        """
        Generate new access token dari refresh token
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            new access token
        """
        payload = cls.verify_token(refresh_token)
        
        if payload.get('type') != 'refresh':
            raise jwt.InvalidTokenError('Invalid refresh token')
        
        new_tokens = cls.generate_tokens(payload['user_id'], payload['email'])
        return new_tokens
