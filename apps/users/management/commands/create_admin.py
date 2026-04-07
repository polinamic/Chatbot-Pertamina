"""
Management command untuk create default admin user
Usage: python manage.py create_admin
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.users.models import UserProfile


class Command(BaseCommand):
    help = 'Create default admin user if not exists'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Admin username'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@pertamina.com',
            help='Admin email'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='AdminPassword123',
            help='Admin password'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        # Check if admin already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Admin user "{username}" sudah ada')
            )
            return

        try:
            # Create superuser
            admin_user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )

            # Create/Update profile dengan role Admin
            profile, created = UserProfile.objects.get_or_create(user=admin_user)
            profile.role = 'A'  # Admin role
            profile.company = 'Pertamina'
            profile.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Admin user "{username}" berhasil dibuat\n'
                    f'   Email: {email}\n'
                    f'   Password: {password}\n'
                    f'   Role: Admin (A)'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creating admin: {str(e)}')
            )
