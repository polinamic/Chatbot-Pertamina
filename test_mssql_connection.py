"""
Script untuk test koneksi ke MSSQL Server dan membuat tabel-tabel yang diperlukan
"""

import pyodbc
import sys

# Configuration
server = 'localhost'
database = 'chatbot_pertamina'
driver = 'ODBC Driver 17 for SQL Server'

def test_connection():
    """Test koneksi ke MSSQL Server"""
    try:
        # Coba connect dengan Windows Authentication
        conn_str = f'Driver={driver};Server={server};Database={database};Trusted_Connection=yes;'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        print("✅ Koneksi ke MSSQL Server BERHASIL!")
        print(f"   Server: {server}")
        print(f"   Database: {database}")
        
        # Get database info
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        print(f"   SQL Server Version: {version[0]}")
        
        # List existing tables
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        
        tables = cursor.fetchall()
        if tables:
            print(f"\n📊 Tabel-tabel yang ada ({len(tables)}):")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("\n⚠️  Belum ada tabel di database ini")
        
        conn.close()
        return True
        
    except pyodbc.Error as e:
        print(f"❌ MSSQL Connection Error: {e}")
        print("\n⚠️  Pastikan:")
        print("   1. SQL Server service sudah running")
        print("   2. Database 'chatbot_pertamina' sudah exist")
        print("   3. ODBC Driver 17 for SQL Server sudah terinstall")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def run_django_migrations():
    """Jalankan Django migrations untuk MSSQL"""
    print("\n" + "="*60)
    print("Menjalankan Django Migrations...")
    print("="*60)
    
    import os
    os.system("python manage.py migrate")


def main():
    print("="*60)
    print("MSSQL Connection & Database Setup Test")
    print("="*60 + "\n")
    
    # Test connection
    if test_connection():
        print("\n" + "="*60)
        print("Next Steps:")
        print("="*60)
        print("1. Jalankan Django migrations:")
        print("   python manage.py migrate")
        print("\n2. Create superuser:")
        print("   python manage.py createsuperuser")
        print("\n3. Jalankan development server:")
        print("   python manage.py runserver")
        print("\n4. Jalankan Ollama service (di terminal lain):")
        print("   ollama serve")
        print("\n5. Test Llama model:")
        print("   python test_llama.py")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
