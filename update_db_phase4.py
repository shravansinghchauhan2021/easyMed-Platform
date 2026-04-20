import sqlite3

def run_migration():
    print("Running DB migration for Phase 4...")
    conn = sqlite3.connect('telemedicine.db')
    
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS medical_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                file_path TEXT,
                modality TEXT,
                sequence_type TEXT,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("medical_images table ensured.")
    except Exception as e:
        print(f"Error creating medical_images table: {e}")
        
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    run_migration()
