"""
Email service utility untuk mengirim email notifikasi
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service untuk mengirim berbagai jenis email
    """

    @staticmethod
    def send_password_reset_email(user_email, reset_link, token_expiry_minutes=15):
        """
        Kirim email password reset ke user

        Args:
            user_email: Email penerima
            reset_link: Link untuk reset password (format: https://domain/reset-password?token=xxx)
            token_expiry_minutes: Berapa menit token berlaku
        """
        try:
            subject = "Reset Password - SITI Chatbot Pertamina"
            
            # Prepare context untuk template
            context = {
                'reset_link': reset_link,
                'token_expiry_minutes': token_expiry_minutes,
                'app_name': 'SITI Chatbot Pertamina',
            }

            # Render HTML email
            html_message = render_to_string('emails/password_reset.html', context)
            plain_message = strip_tags(html_message)

            # Create email with both plain text and HTML
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email]
            )
            email.attach_alternative(html_message, "text/html")
            
            # Send email
            email.send(fail_silently=False)
            
            logger.info(f"Password reset email sent to {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send password reset email to {user_email}: {str(e)}")
            return False

    @staticmethod
    def send_password_changed_confirmation_email(user_email):
        """
        Kirim email konfirmasi password telah diubah

        Args:
            user_email: Email penerima
        """
        try:
            subject = "Password Berhasil Diubah - SITI Chatbot Pertamina"
            
            context = {
                'app_name': 'SITI Chatbot Pertamina',
            }

            html_message = render_to_string('emails/password_changed.html', context)
            plain_message = strip_tags(html_message)

            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email]
            )
            email.attach_alternative(html_message, "text/html")
            
            email.send(fail_silently=False)
            
            logger.info(f"Password changed confirmation email sent to {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send password changed confirmation to {user_email}: {str(e)}")
            return False

    @staticmethod
    def send_welcome_email(user_email, username):
        """
        Kirim email welcome ke user baru

        Args:
            user_email: Email penerima
            username: Nama pengguna
        """
        try:
            subject = "Selamat Datang di SITI Chatbot Pertamina"
            
            context = {
                'username': username,
                'app_name': 'SITI Chatbot Pertamina',
                'login_url': settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'https://localhost:3000',
            }

            html_message = render_to_string('emails/welcome.html', context)
            plain_message = strip_tags(html_message)

            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email]
            )
            email.attach_alternative(html_message, "text/html")
            
            email.send(fail_silently=False)
            
            logger.info(f"Welcome email sent to {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send welcome email to {user_email}: {str(e)}")
            return False
