import sqlite3
import os

db_path = r'c:\Users\shravan singh\telemedicine_gravity\database.db'

def update_schema():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists to prevent errors on multiple runs
        cursor.execute("PRAGMA table_info(patients)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'patient_mobile' not in columns:
            cursor.execute("ALTER TABLE patients ADD COLUMN patient_mobile TEXT")
            print("Added column 'patient_mobile' to 'patients' table.")
        else:
            print("Column 'patient_mobile' already exists.")
            
        if 'patient_user_id' not in columns:
            cursor.execute("ALTER TABLE patients ADD COLUMN patient_user_id INTEGER")
            print("Added column 'patient_user_id' to 'patients' table.")
        else:
            print("Column 'patient_user_id' already exists.")
            
        conn.commit()
        print("Schema update completed successfully.")
        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    update_schema()
