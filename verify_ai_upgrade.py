import sqlite3

def verify():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Check patients table
    cursor.execute("PRAGMA table_info(patients)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Columns in patients: {columns}")
    
    needed = ['risk_level', 'predicted_condition', 'created_at']
    missing = [c for c in needed if c not in columns]
    
    if not missing:
        print("SUCCESS: All new columns are present.")
    else:
        print(f"FAILURE: Missing columns: {missing}")
        
    # Check sample data for analytics
    cursor.execute("SELECT risk_level, predicted_condition, created_at FROM patients LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Sample data: {row}")
    else:
        print("No patients in DB yet.")
        
    conn.close()

if __name__ == '__main__':
    verify()
