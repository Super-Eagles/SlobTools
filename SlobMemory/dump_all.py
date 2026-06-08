import sqlite3
import io

def dump_all():
    conn = sqlite3.connect('C:/memory_skill_v3/memory.db')
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(memories)")
    columns = [col[1] for col in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM memories")
    rows = cursor.fetchall()
    print(f"Dumping {len(rows)} memories...")
    
    with io.open('C:/memory_skill_v3/all_memories_utf8.txt', 'w', encoding='utf-8') as f:
        for row in rows:
            record = dict(zip(columns, row))
            f.write("="*80 + "\n")
            f.write(f"ID: {record.get('id')}\n")
            f.write(f"Session: {record.get('session_id')}\n")
            f.write(f"Summary: {record.get('summary')}\n")
            f.write(f"Keywords: {record.get('keywords')}\n")
            f.write(f"Raw Q: {record.get('raw_q')}\n")
            f.write(f"Raw A:\n{record.get('raw_a')}\n")
    conn.close()

if __name__ == '__main__':
    dump_all()
