import sqlite3
import io

def search():
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(os.path.join(base_dir, 'memory.db'))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, summary, keywords, raw_q, raw_a 
        FROM memories 
        WHERE summary LIKE '%主控%' 
           OR summary LIKE '%通信%'
           OR raw_q LIKE '%主控%'
           OR raw_a LIKE '%主控%'
           OR raw_a LIKE '%通信%'
           OR raw_a LIKE '%C_HttpServer%'
     """)
    rows = cursor.fetchall()
    
    with io.open(os.path.join(base_dir, 'search_results_utf8.txt'), 'w', encoding='utf-8') as f:
        f.write(f"Found {len(rows)} matching memories:\n")
        for row in rows:
            mid, summary, keywords, raw_q, raw_a = row
            f.write("="*80 + "\n")
            f.write(f"ID: {mid}\n")
            f.write(f"Keywords: {keywords}\n")
            f.write(f"Summary: {summary}\n")
            f.write(f"Question: {raw_q}\n")
            f.write(f"Answer:\n{raw_a}\n")
    conn.close()

if __name__ == '__main__':
    search()
