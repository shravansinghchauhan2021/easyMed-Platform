import sqlite3
import os

db_path = 'c:/Users/shravan singh/telemedicine_gravity/database.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Last 5 messages:")
query = """
SELECT m.id, u.username, u.profession, m.message, m.timestamp 
FROM messages m 
JOIN users u ON m.sender_id = u.id 
ORDER BY m.id DESC LIMIT 5
"""
cursor.execute(query)
rows = cursor.fetchall()

for row in rows:
    print(f"ID: {row['id']} | User: {row['username']} | Role: {row['profession']} | Msg: {row['message']} | Time: {row['timestamp']}")

conn.close()
