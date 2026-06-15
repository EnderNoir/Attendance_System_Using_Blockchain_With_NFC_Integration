#!/usr/bin/env python3
"""
Simple script to add missing student table columns.
Attempts to connect using DATABASE_URL or local PostgreSQL.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

# Handle Railway/Heroku postgres:// prefix
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Default to localhost if not set
if not DATABASE_URL:
    DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/davs'

try:
    import psycopg2
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Columns to add
    columns_to_add = [
        ('first_name', "TEXT NOT NULL DEFAULT ''"),
        ('middle_initial', "TEXT NOT NULL DEFAULT ''"),
        ('last_name', "TEXT NOT NULL DEFAULT ''"),
    ]
    
    print("Connecting to database...")
    print(f"Database URL: {DATABASE_URL[:50]}...")
    print()
    
    for col_name, col_def in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE students ADD COLUMN {col_name} {col_def}")
            conn.commit()
            print(f"✓ Added column: {col_name}")
        except psycopg2.Error as e:
            if "already exists" in str(e):
                print(f"✓ Column {col_name} already exists (skipped)")
                conn.rollback()
            else:
                print(f"✗ Error adding {col_name}: {e}")
                conn.rollback()
    
    cursor.close()
    conn.close()
    print("\n✓ Migration complete!")
    
except ImportError:
    print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    print(f"\nTroubleshoot:")
    print("1. Ensure PostgreSQL is running")
    print("2. Check DATABASE_URL in .env or Railway dashboard")
    print("3. Verify connection credentials")
    sys.exit(1)
