import sqlite3

def test():
    conn = sqlite3.connect('C:/memory_skill_v3/memory.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(memories)")
    cols = cursor.fetchall()
    print("Columns:", [c[1] for c in cols])
    
    cursor.execute("SELECT * FROM memories LIMIT 1")
    row = cursor.fetchone()
    if row:
        print("First row values:", row)
    conn.close()

if __name__ == '__main__':
    test()
