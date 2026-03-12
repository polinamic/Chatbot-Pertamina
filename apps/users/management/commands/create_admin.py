"""
Management command untuk membuat admin user
Usage: python manage.py create_admin --username admin --email admin@pertamina.com --password Admin123!
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import IntegrityError
from apps.users.models import UserProfile
import getpass


class Command(BaseCommand):
    help = 'Membuat admin user baru'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username untuk admin user',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email untuk admin user',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password untuk admin user (jika tidak diberikan, akan diminta)',
            default=None,
        )
        parser.add_argument(
            '--firstname',
            type=str,
            default='Admin',
            help='First name untuk admin user (default: Admin)',
        )
        parser.add_argument(
            '--lastname',
            type=str,
            default='User',
            help='Last name untuk admin user (default: User)',
        )

    def handle(self, *args, **options):
        # Get username
        username = options.get('username')
        while not username:
            username = input('Masukkan username: ').strip()
            if not username:
                self.stdout.write(self.style.ERROR('Username tidak boleh kosong'))
                continue
            if len(username) < 3:
                self.stdout.write(self.style.ERROR('Username minimal 3 karakter'))
                username = None
                continue
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.ERROR('Username sudah digunakan'))
                username = None
                continue
            break

        # Get email
        email = options.get('email')
        while not email:
            email = input('Masukkan email: ').strip().lower()
            if not email:
                self.stdout.write(self.style.ERROR('Email tidak boleh kosong'))
                continue
            if User.objects.filter(email=email).exists():
                self.stdout.write(self.style.ERROR('Email sudah terdaftar'))
                email = None
                continue
            break

        # Get password
        password = options.get('password')
        while not password:
            password = getpass.getpass('Masukkan password (min 8 karakter, 1 huruf besar, 1 angka): ')
            if not password:
                self.stdout.write(self.style.ERROR('Password tidak boleh kosong'))
                continue
            
            # Validate password
            if len(password) < 8:
                self.stdout.write(self.style.ERROR('Password minimal 8 karakter'))
                password = None
                continue
            
            if not any(char.isupper() for char in password):
                self.stdout.write(self.style.ERROR('Password harus mengandung minimal 1 huruf besar'))
                password = None
                continue
            
            if not any(char.isdigit() for char in password):
                self.stdout.write(self.style.ERROR('Password harus mengandung minimal 1 angka'))
                password = None
                continue
            
            # Confirm password
            password_confirm = getpass.getpass('Konfirmasi password: ')
            if password != password_confirm:
                self.stdout.write(self.style.ERROR('Password tidak cocok'))
                password = None
                continue
            break

        # Get names
        first_name = options.get('firstname', 'Admin')
        last_name = options.get('lastname', 'User')

        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,
                is_superuser=True,
            )

            # Create user profile with admin role
            profile = UserProfile.objects.create(
                user=user,
                role='A',  # Admin
                company='Pertamina',
                is_verified=True
            )

            self.stdout.write(
                self.style.SUCCESS(f'✓ Admin user berhasil dibuat')
            )
            self.stdout.write(f'  Username: {username}')
            self.stdout.write(f'  Email: {email}')
            self.stdout.write(f'  Full Name: {first_name} {last_name}')
            self.stdout.write(f'  Role: Admin')
            self.stdout.write(self.style.WARNING('\nPeringatan: Jangan bagikan credentials ini'))

        except IntegrityError as e:
            raise CommandError(f'Gagal membuat admin user: {str(e)}')
        except Exception as e:
            raise CommandError(f'Terjadi error: {str(e)}')
