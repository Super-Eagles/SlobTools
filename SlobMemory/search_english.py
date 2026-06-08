import sqlite3

def search():
    conn = sqlite3.connect('C:/memory_skill_v3/memory.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, summary, keywords, raw_q, raw_a 
        FROM memories 
        WHERE raw_q LIKE '%MsgPrco%' 
           OR raw_a LIKE '%MsgPrco%'
           OR raw_a LIKE '%mongoose%'
           OR raw_a LIKE '%HttpServer%'
           OR keywords LIKE '%MsgPrco%'
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
