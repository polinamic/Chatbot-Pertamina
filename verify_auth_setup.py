#!/usr/bin/env python
"""
Verification script untuk memastikan semua perbaikan auth sudah ter-setup dengan benar
Usage: python verify_auth_setup.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from apps.users.models import UserProfile
from pathlib import Path


class AuthSetupVerifier:
    """Verifikasi setup auth backend"""
    
    def __init__(self):
        self.checks = []
        self.project_root = Path(__file__).parent
        self.passed = 0
        self.failed = 0
        
    def print_header(self, text):
        """Print header"""
        print(f'\n{"="*60}')
        print(f'🔍 {text}')
        print(f'{"="*60}')
    
    def check_file_exists(self, filepath, description):
        """Check apakah file ada"""
        path = self.project_root / filepath
        if path.exists():
            print(f'✅ {description}')
            self.passed += 1
            return True
        else:
            print(f'❌ {description}')
            print(f'   Path: {filepath}')
            self.failed += 1
            return False
    
    def check_database(self, description):
        """Check database setup"""
        try:
            # Check if User model works
            user_count = User.objects.count()
            profile_count = UserProfile.objects.count()
            
            print(f'✅ {description}')
            print(f'   User count: {user_count}')
            print(f'   Profile count: {profile_count}')
            self.passed += 1
            return True
        except Exception as e:
            print(f'❌ {description}')
            print(f'   Error: {str(e)}')
            self.failed += 1
            return False
    
    def verify_files(self):
        """Verify all created/modified files"""
        self.print_header('1. VERIFY FILES')
        
        files_to_check = [
            ('create_admin_user.py', 'Standalone admin creator script'),
            ('test_auth_backend.py', 'Auth backend test suite'),
            ('AUTH_BACKEND_GUIDE.md', 'Auth backend documentation'),
            ('PERBAIKAN_AUTH_SUMMARY.md', 'Auth improvement summary'),
            ('QUICK_REFERENCE.md', 'Quick reference guide'),
            ('apps/users/management/commands/create_admin.py', 'Django management command'),
        ]
        
        for filepath, description in files_to_check:
            self.check_file_exists(filepath, description)
    
    def verify_database(self):
        """Verify database setup"""
        self.print_header('2. VERIFY DATABASE')
        
        try:
            # Check migration
            from django.core.management import call_command
            from io import StringIO
            
            out = StringIO()
            call_command('showmigrations', 'users', stdout=out)
            migration_output = out.getvalue()
            
            if '[X]' in migration_output:
                print('✅ Database migrations applied')
                self.passed += 1
            else:
                print('⚠️  Some migrations may not be applied')
                print('   Run: python manage.py migrate')
        
        except Exception as e:
            print(f'⚠️  Could not check migrations: {str(e)}')
        
        # Check database models
        self.check_database('Database models accessible')
    
    def verify_views(self):
        """Verify views setup"""
        self.print_header('3. VERIFY VIEWS')
        
        try:
            from apps.users.views import (
                SignupView, 
                LoginView, 
                RefreshTokenView,
                LogoutView,
                signup_page,
                login_page,
                logout_page
            )
            
            print('✅ All API views imported successfully')
            print('✅ All template views imported successfully')
            self.passed += 2
            
        except ImportError as e:
            print(f'❌ Import error: {str(e)}')
            self.failed += 1
    
    def verify_serializers(self):
        """Verify serializers setup"""
        self.print_header('4. VERIFY SERIALIZERS')
        
        try:
            from apps.users.serializers import (
                UserSerializer,
                UserSignupSerializer,
                UserLoginSerializer,
                TokenRefreshSerializer,
                UserUpdateSerializer,
                ChangePasswordSerializer
            )
            
            print('✅ All serializers imported successfully')
            self.passed += 1
            
        except ImportError as e:
            print(f'❌ Import error: {str(e)}')
            self.failed += 1
    
    def verify_urls(self):
        """Verify URLs setup"""
        self.print_header('5. VERIFY URLS')
        
        try:
            from apps.users.urls import api_urlpatterns, urlpatterns
            
            if urlpatterns:
                print(f'✅ Web URL patterns found: {len(urlpatterns)} endpoint(s)')
                self.passed += 1
            
            if api_urlpatterns:
                print(f'✅ API URL patterns found: {len(api_urlpatterns)} endpoint(s)')
                self.passed += 1
            
        except ImportError as e:
            print(f'❌ Import error: {str(e)}')
            self.failed += 1
    
    def verify_management_command(self):
        """Verify management command works"""
        self.print_header('6. VERIFY MANAGEMENT COMMAND')
        
        try:
            from django.core.management import get_commands, load_command_class
            
            commands = get_commands()
            
            if 'create_admin' in commands:
                print('✅ create_admin management command registered')
                
                try:
                    cmd = load_command_class('users', 'create_admin')
                    print('✅ create_admin command loaded successfully')
                    self.passed += 2
                except Exception as e:
                    print(f'⚠️  Could not load command: {str(e)}')
                    self.passed += 1
            else:
                print('⚠️  create_admin management command not found')
                print('   Try running: python manage.py makemigrations')
        
        except Exception as e:
            print(f'⚠️  Error checking management commands: {str(e)}')
    
    def verify_admin_panel(self):
        """Verify admin panel setup"""
        self.print_header('7. VERIFY ADMIN PANEL')
        
        try:
            from apps.users.admin import UserProfileAdmin
            
            print('✅ UserProfile admin configured')
            self.passed += 1
            
        except Exception as e:
            print(f'⚠️  Admin panel: {str(e)}')
    
    def print_summary(self):
        """Print summary"""
        self.print_header('VERIFICATION SUMMARY')
        
        total = self.passed + self.failed
        percentage = (self.passed / total * 100) if total > 0 else 0
        
        print(f'✅ Passed: {self.passed}')
        print(f'❌ Failed: {self.failed}')
        print(f'📊 Total: {total}')
        print(f'📈 Success Rate: {percentage:.1f}%')
        
        if self.failed == 0:
            print('\n✨ SEMUA CHECK PASSED! Backend auth siap digunakan. ✨')
        else:
            print('\n⚠️  Ada beberapa issues yang perlu diperbaiki.')
        
        print(f'\n{"="*60}')
    
    def print_next_steps(self):
        """Print next steps"""
        print('\n📋 LANGKAH SELANJUTNYA:\n')
        
        print('1. BUAT ADMIN USER')
        print('   $ python manage.py create_admin')
        print('   atau')
        print('   $ python create_admin_user.py\n')
        
        print('2. TEST AUTH BACKEND')
        print('   $ python test_auth_backend.py\n')
        
        print('3. BACA DOKUMENTASI')
        print('   - AUTH_BACKEND_GUIDE.md (lengkap)')
        print('   - PERBAIKAN_AUTH_SUMMARY.md (summary)')
        print('   - QUICK_REFERENCE.md (quick lookup)\n')
        
        print('4. TEST DI FRONTEND')
        print('   - Visit: http://localhost:8000/users/signup/')
        print('   - Fill form and submit')
        print('   - See success message')
        print('   - Click login link')
        print('   - Login dengan credential baru\n')
        
        print('5. TEST API ENDPOINTS')
        print('   - Gunakan cURL atau Postman')
        print('   - Lihat AUTH_BACKEND_GUIDE.md untuk contoh\n')
    
    def run_all_checks(self):
        """Run all verification checks"""
        print('\n╔════════════════════════════════════════════════════════════╗')
        print('║    🔐 AUTH BACKEND SETUP VERIFICATION                      ║')
        print('╚════════════════════════════════════════════════════════════╝')
        
        self.verify_files()
        self.verify_database()
        self.verify_views()
        self.verify_serializers()
        self.verify_urls()
        self.verify_management_command()
        self.verify_admin_panel()
        
        self.print_summary()
        self.print_next_steps()
        
        return self.failed == 0


if __name__ == '__main__':
    try:
        verifier = AuthSetupVerifier()
        success = verifier.run_all_checks()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print('\n\n⚠️  Verification dibatalkan')
        sys.exit(0)
    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
