import difflib

def compare():
    with open('D:/soft/cp_update.py', 'r', encoding='utf-8', errors='ignore') as f1:
        lines1 = f1.readlines()
    with open('D:/soft/cp_update-test.py', 'r', encoding='utf-8', errors='ignore') as f2:
        lines2 = f2.readlines()
        
    diff = difflib.unified_diff(lines2, lines1, fromfile='cp_update-test.py', tofile='cp_update.py')
    
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    diff_path = os.path.join(base_dir, 'diff_result.txt')
    with open(diff_path, 'w', encoding='utf-8') as out:
        out.writelines(diff)
    print(f"Diff complete. Written to {diff_path}")

if __name__ == '__main__':
    compare()
