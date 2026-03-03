import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

print("=" * 60)
print("USER DATABASE CHECK")
print("=" * 60)

admin_users = User.objects.filter(username='admin')
print(f"\nUsers with username='admin': {admin_users.count()}")
for user in admin_users:
    print(f"  Username: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  Is staff: {user.is_staff}")
    print(f"  Is superuser: {user.is_superuser}")
    print(f"  Is active: {user.is_active}")

email_users = User.objects.filter(email='admin')
print(f"\nUsers with email='admin': {email_users.count()}")

print(f"\nAll users ({User.objects.count()} total):")
for user in User.objects.all()[:10]:
    print(f"  {user.id}: {user.username} - {user.email} (staff={user.is_staff}, active={user.is_active})")
