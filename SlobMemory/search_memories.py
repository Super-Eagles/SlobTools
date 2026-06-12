import sqlite3
import sys

def search():
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(os.path.join(base_dir, 'memory.db'))
    cursor = conn.cursor()
    
    # We want to select rows where summary, raw_q, raw_a contain '主控', '通信', '教员', etc.
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
    print(f"Found {len(rows)} matching memories:")
    for row in rows:
        mid, summary, keywords, raw_q, raw_a = row
        print("="*80)
        print(f"ID: {mid}")
        print(f"Keywords: {keywords}")
        print(f"Summary: {summary}")
        print(f"Question: {raw_q}")
        print(f"Answer:\n{raw_a}")
    conn.close()

if __name__ == '__main__':
    search()
