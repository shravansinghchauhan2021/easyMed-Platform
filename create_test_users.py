import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = 'database.db'

def create_test_user():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create test rural doctor
    hashed_pw = generate_password_hash('password')
    try:
        cursor.execute("INSERT INTO users (username, password, profession) VALUES (?, ?, ?)", 
                       ('test_rural', hashed_pw, 'Rural Doctor'))
        print("Created test_rural user.")
    except sqlite3.IntegrityError:
        print("test_rural user already exists.")
        
    # Create test specialist
    try:
        cursor.execute("INSERT INTO users (username, password, profession) VALUES (?, ?, ?)", 
                       ('test_specialist', hashed_pw, 'Neurologist'))
        print("Created test_specialist user.")
    except sqlite3.IntegrityError:
        print("test_specialist user already exists.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_test_user()
