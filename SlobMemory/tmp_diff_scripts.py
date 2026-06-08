import difflib

def compare():
    with open('D:/soft/cp_update.py', 'r', encoding='utf-8', errors='ignore') as f1:
        lines1 = f1.readlines()
    with open('D:/soft/cp_update-test.py', 'r', encoding='utf-8', errors='ignore') as f2:
        lines2 = f2.readlines()
        
    diff = difflib.unified_diff(lines2, lines1, fromfile='cp_update-test.py', tofile='cp_update.py')
    
    with open('C:/memory_skill_v3/diff_result.txt', 'w', encoding='utf-8') as out:
        out.writelines(diff)
    print("Diff complete. Written to C:/memory_skill_v3/diff_result.txt")

if __name__ == '__main__':
    compare()
