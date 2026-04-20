import sqlite3

def check_db():
    conn = sqlite3.connect('telemedicine.db')
    conn.row_factory = sqlite3.Row
    patients = conn.execute('SELECT * FROM patients').fetchall()
    print(f"Total patients: {len(patients)}")
    for p in patients:
        print(f"ID: {p['id']}, Name: {p['patient_name']}, Specialty: {p['specialist_type']}, Priority: {p['priority']}, Status: {p['status']}, Specialist ID: {p['specialist_id']}")
    
    # List all users
    users = conn.execute('SELECT * FROM users').fetchall()
    print("\nUsers Table:")
    for u in users:
        print(f"ID: {u['id']}, Username: {u['username']}, Profession: {u['profession']}, Status: {u['status']}")
    
    # Check schema
    schema = conn.execute("PRAGMA table_info(patients)").fetchall()
    print("\nPatients Table Schema:")
    for col in schema:
        print(f"Col: {col['name']}, Type: {col['type']}")
    
    conn.close()

if __name__ == '__main__':
    check_db()
