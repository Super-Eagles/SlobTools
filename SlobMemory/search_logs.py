import os
import glob
import json

def search():
    brain_dir = "C:/Users/Administrator/.gemini/antigravity/brain"
    paths = glob.glob(os.path.join(brain_dir, "*", ".system_generated", "logs", "overview.txt"))
    print(f"Searching in {len(paths)} overview files...")
    
    for path in paths:
        conv_id = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
        print(f"\n--- Checking Conversation {conv_id} ---")
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        for idx, line in enumerate(lines):
            if 'C_HttpServer' in line or 'MsgPrco' in line or 'ZKTHttpServer' in line or 'OnRequest' in line:
                try:
                    data = json.loads(line)
                    content = data.get('content', '')
                    if content and ('C_HttpServer' in content or 'MsgPrco' in content or 'OnRequest' in content or '教员' in content):
                        print(f"Line {idx}: {content[:1000]}")
                except Exception:
                    # If not JSON, just search the raw text
                    if any(term in line for term in ['C_HttpServer', 'MsgPrco', 'OnRequest']):
                        print(f"Line {idx} (raw): {line[:1000]}")

if __name__ == '__main__':
    search()
