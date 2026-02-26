# Custom SQL Query untuk MSSQL Database

## 📋 Dokumentasi Menjalankan Query SQL Custom

Jika Anda sudah membuat query SQL untuk membuat atau memodifikasi tabel database, ikuti langkah-langkah berikut:

## 🔧 Option 1: Via SQL Server Management Studio (GUI)

### Step 1: Buka SSMS
```
Start Menu → SQL Server Management Studio
```

### Step 2: Connect ke Database
```
Server Name: localhost
Authentication: Windows Authentication
Database: chatbot_pertamina
```

### Step 3: Execute Query
```
1. File → Open Query File (atau Ctrl+O)
2. Pilih file .sql Anda
3. Edit → Execute (F5)
4. Lihat hasil di "Messages" tab
```

## 🔧 Option 2: Via Command Line (sqlcmd)

### Windows Authentication
```bash
sqlcmd -S localhost -d chatbot_pertamina -i your_script.sql
```

### SQL Server Authentication
```bash
sqlcmd -S localhost -U sa -P your_password -d chatbot_pertamina -i your_script.sql
```

### Contoh dengan Output
```bash
sqlcmd -S localhost -d chatbot_pertamina -i create_tables.sql -O
```

## 🔧 Option 3: Via Python (pyodbc)

### Direct Query Execution
```python
import pyodbc

# Connect to database
conn = pyodbc.connect(
    'Driver={ODBC Driver 17 for SQL Server};'
    'Server=localhost;'
    'Database=chatbot_pertamina;'
    'Trusted_Connection=yes;'
)
cursor = conn.cursor()

# Read and execute SQL file
with open('your_script.sql', 'r') as f:
    sql_script = f.read()
    
# Execute (split by GO for batch processing)
batches = sql_script.split('GO')
for batch in batches:
    if batch.strip():
        cursor.execute(batch)
    
conn.commit()
print("✅ Query executed successfully!")
conn.close()
```

### Save as Script
```python
# run_sql_script.py
import pyodbc
import sys

def execute_sql_file(server, database, sql_file):
    try:
        conn = pyodbc.connect(
            f'Driver={{ODBC Driver 17 for SQL Server}};'
            f'Server={server};'
            f'Database={database};'
            f'Trusted_Connection=yes;'
        )
        cursor = conn.cursor()
        
        with open(sql_file, 'r') as f:
            sql_script = f.read()
        
        # Execute all batches
        for batch in sql_script.split('GO'):
            if batch.strip():
                cursor.execute(batch)
        
        conn.commit()
        print(f"✅ {sql_file} executed successfully!")
        
    except pyodbc.Error as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python run_sql_script.py <sql_file>")
        sys.exit(1)
    
    sql_file = sys.argv[1]
    execute_sql_file('localhost', 'chatbot_pertamina', sql_file)
```

**Jalankan dengan:**
```bash
python run_sql_script.py your_script.sql
```

## 📄 Template Query SQL untuk Signup/User Management

Jika Anda ingin membuat query custom, gunakan template berikut:

### Create Users Table (jika belum ada)
```sql
-- Users Table
CREATE TABLE [dbo].[users] (
    [id] INT PRIMARY KEY IDENTITY(1,1),
    [username] NVARCHAR(150) UNIQUE NOT NULL,
    [email] NVARCHAR(254) UNIQUE NOT NULL,
    [password] NVARCHAR(255) NOT NULL,
    [first_name] NVARCHAR(150),
    [last_name] NVARCHAR(150),
    [is_active] BIT DEFAULT 1,
    [created_at] DATETIME DEFAULT GETDATE(),
    [updated_at] DATETIME DEFAULT GETDATE()
);

-- User Profiles Table
CREATE TABLE [dbo].[user_profiles] (
    [id] INT PRIMARY KEY IDENTITY(1,1),
    [user_id] INT UNIQUE NOT NULL,
    [department] NVARCHAR(50),
    [company] NVARCHAR(100),
    [phone] NVARCHAR(15),
    [bio] NVARCHAR(MAX),
    [is_verified] BIT DEFAULT 0,
    [created_at] DATETIME DEFAULT GETDATE(),
    [updated_at] DATETIME DEFAULT GETDATE(),
    FOREIGN KEY ([user_id]) REFERENCES [dbo].[users]([id]) 
        ON DELETE CASCADE
);

-- Add Indexes
CREATE INDEX idx_users_email ON [dbo].[users]([email]);
CREATE INDEX idx_users_username ON [dbo].[users]([username]);
CREATE INDEX idx_user_profiles_user_id ON [dbo].[user_profiles]([user_id]);
```

### Insert Sample Data
```sql
-- Insert sample user
INSERT INTO [dbo].[users] 
(username, email, password, first_name, last_name)
VALUES
('john.doe', 'john.doe@pertamina.com', 'hashed_password_here', 'John', 'Doe');

-- Get inserted user ID
DECLARE @userId INT;
SET @userId = SCOPE_IDENTITY();

-- Insert profile for user
INSERT INTO [dbo].[user_profiles]
(user_id, department, company, phone)
VALUES
(@userId, 'IT', 'Pertamina Regional', '08123456789');
```

### Query untuk Verify Data
```sql
-- Check users
SELECT * FROM [dbo].[users];

-- Check profiles
SELECT u.username, p.company, p.is_verified 
FROM [dbo].[users] u
JOIN [dbo].[user_profiles] p ON u.id = p.user_id;

-- Count by company
SELECT company, COUNT(*) as count 
FROM [dbo].[user_profiles]
GROUP BY company;

-- Check not verified users
SELECT u.username, u.email, p.is_verified
FROM [dbo].[users] u
LEFT JOIN [dbo].[user_profiles] p ON u.id = p.user_id
WHERE p.is_verified = 0;
```

## 🔄 Integrasi dengan Django Migration

Jika Anda sudah membuat tabel via custom SQL, Anda bisa:

### Option A: Generate Django Models dari Tabel
```bash
python manage.py inspectdb > apps/users/models.py
```

### Option B: Ignore Custom Tabel di Migrations
```python
# managers.py
class Meta:
    managed = False  # Django tidak akan manage tabel ini
    db_table = 'your_table_name'
```

## ✅ Verification

### Check Tabel Terbuat
```bash
python test_mssql_connection.py
```

**Output akan menunjukkan:**
```
📊 Tabel-tabel yang ada (N):
   - users
   - user_profiles
   - ...
```

### Check Data
```bash
python manage.py shell

from apps.users.models import User
User.objects.all()
```

## 📧 Import Query dari File

Jika Anda punya file SQL:

```bash
# Copy file ke project directory
copy C:\path\to\your_script.sql .

# Run dengan SQLCMD
sqlcmd -S localhost -d chatbot_pertamina -i your_script.sql -E
```

## 🚀 Best Practices

1. **Backup Database Sebelum Menjalankan Query**
   ```bash
   # Di SSMS: Right-click database → Tasks → Back Up
   ```

2. **Test Query di Development First**
   ```bash
   # Create test database
   CREATE DATABASE chatbot_pertamina_test;
   
   # Run query di test database dulu
   ```

3. **Keep Original .sql File**
   ```bash
   # Simpan versi original untuk reference
   backup_queries/create_tables.sql.bak
   ```

4. **Document Your Changes**
   ```sql
   -- Script untuk membuat tabel users
   -- Created: 2026-02-25
   -- Purpose: Store user authentication data
   -- Modified by: [Your Name]
   
   CREATE TABLE ...
   ```

## 📝 Jika Ada Error

```bash
# Error: Syntax Error di Query
Solution: Check SQL syntax menggunakan online SQL validator

# Error: Permission Denied
Solution: Pastikan user punya permission untuk create table
          Jalankan CREATE VIEW, ALTER TABLE dengan sa account

# Error: Object already exists
Solution: DROP TABLE dulu sebelum CREATE
          Atau gunakan: IF NOT EXISTS
          CREATE TABLE IF NOT EXISTS...
```

## 📞 Fast Help

| Pertanyaan | Solusi |
|-----------|--------|
| Syntax error? | Validate di [SQL Validator](https://www.sqlserver.info) |
| Forgot query? | Check SSMS Query History (Ctrl+Shift+H) |
| Want to undo? | Restore from backup atau DROP TABLE |
| Need templates? | Lihat section "Template Query SQL" |

---

**Tips:** Selalu backup database sebelum menjalankan query custom! 🔒

**Created**: February 25, 2026
