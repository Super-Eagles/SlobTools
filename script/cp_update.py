#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cp_update_concurrent_final.py  --  兼容 Python 2.7
新增：模式 8 (批量重启) & 本地上传结果日志记录 (upload_result.log)
"""

from __future__ import unicode_literals, print_function
import sys
import os
import stat
import tempfile
import subprocess
import datetime
import locale
import posixpath
import io
import time
import random
import threading

try:
    import Queue as queue
except ImportError:
    import queue

# ──────────────────────────────────────────────
#  并发与锁配置
# ──────────────────────────────────────────────
PRINT_LOCK = threading.Lock()
UPLOAD_LOG_LOCK = threading.Lock()
MAX_WORKERS = 10 
UPLOAD_LOG_FILE = "upload_result.log"

def safe_print(msg):
    """线程安全的日志输出"""
    with PRINT_LOCK:
        print(msg)

# ──────────────────────────────────────────────
#  Python 2 / 3 兼容工具
# ──────────────────────────────────────────────
PY3 = sys.version_info[0] >= 3
try: text_type = unicode
except NameError: text_type = str
try: binary_type = bytes
except NameError: binary_type = str

def _get_cli_encoding():
    try: enc = locale.getpreferredencoding(False)
    except TypeError: enc = locale.getpreferredencoding()
    return enc or sys.getfilesystemencoding() or "utf-8"

def _decode_cli_arg(arg):
    if isinstance(arg, text_type): return arg
    for enc in (_get_cli_encoding(), "utf-8", "gbk"):
        try: return arg.decode(enc)
        except: pass
    return arg.decode("utf-8", "replace")

def _ensure_text(value):
    if isinstance(value, text_type): return value
    if isinstance(value, binary_type): return _decode_cli_arg(value)
    return text_type(value)

def _to_process_arg(value):
    if PY3 or isinstance(value, binary_type): return value
    value = _ensure_text(value)
    for enc in (_get_cli_encoding(), "utf-8"):
        try: return value.encode(enc)
        except: pass
    return value.encode("utf-8", "replace")

def _shell_quote(value):
    value = _ensure_text(value)
    return "'%s'" % value.replace("'", "'\"'\"'")

def _to_bytes(s):
    if isinstance(s, binary_type): return s
    if isinstance(s, text_type): return s.encode("utf-8")
    return _ensure_text(s).encode("utf-8")

def _to_str(b):
    if isinstance(b, bytes): return b.decode("utf-8", errors="replace")
    return b

# ========== 配置变量 ==========
USERNAME = "yunda"
PASSWORD = "Aa123456"
IP_FILE  = "ip.txt"
PGM_FILE = "pgm.txt"
SSH_PORT = 22
START_ENV_KEYS = ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR")

# ──────────────────────────────────────────────
#  日志记录核心
# ──────────────────────────────────────────────
def log_upload_result(ip, local_path, remote_path, is_success):
    """记录上传的文件信息到本地结果文件"""
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        size = os.path.getsize(local_path)
        
        # 格式化文件大小
        if size >= 1048576:
            size_str = "%.2f MB" % (size / 1048576.0)
        else:
            size_str = "%.2f KB" % (size / 1024.0)
            
        # 提取文件原始日期
        mtime = os.path.getmtime(local_path)
        mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        status = "成功" if is_success else "失败"
        
        log_line = "[%s] | IP: %-15s | 文件: %-25s | 原始日期: %s | 大小: %10s | 状态: %s\n" % (
            now_str, ip, posixpath.basename(local_path), mtime_str, size_str, status
        )
        
        # 线程安全追加写入文件
        with UPLOAD_LOG_LOCK:
            with io.open(UPLOAD_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(_ensure_text(log_line))
    except Exception as e:
        safe_print("[WARN] 写入日志失败: %s" % str(e))

# ──────────────────────────────────────────────
#  SSH 核心逻辑 (修复并发冲突与时间同步)
# ──────────────────────────────────────────────
def _create_temp_askpass():
    t_id = threading.current_thread().ident
    fd, path = tempfile.mkstemp(prefix="askpass_%s_" % t_id, suffix=".sh")
    script = "#!/bin/sh\necho '%s'\n" % PASSWORD.replace("'", "'\\''")
    os.write(fd, _to_bytes(script))
    os.close(fd)
    os.chmod(path, stat.S_IRWXU)
    return path

def _run_ssh_core(ip, remote_cmd, stdin_data=None):
    askpass_path = _create_temp_askpass()
    try:
        env = os.environ.copy() 
        env["SSH_ASKPASS"] = askpass_path
        env["DISPLAY"] = env.get("DISPLAY", ":0")
        env["SSH_ASKPASS_REQUIRE"] = "force"
        
        cmd = ["setsid", "ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=no", 
               "-o", "PasswordAuthentication=yes", "-o", "ConnectTimeout=10", "-p", str(SSH_PORT),
               "%s@%s" % (USERNAME, ip), remote_cmd]
        
        cmd = [_to_process_arg(part) for part in cmd]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if stdin_data else None,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        out, err = proc.communicate(input=stdin_data)
        full_output = _to_str(out) + _to_str(err)
        # 过滤掉 sudo -S 产生的常见提示语，使输出更干净
        for prompt in ["[sudo] password for", "密码：", "输入密码"]:
            if prompt in full_output:
                lines = full_output.splitlines()
                full_output = "\n".join([l for l in lines if prompt not in l])
        return proc.returncode, full_output.strip()
    finally:
        if os.path.exists(askpass_path):
            try: os.remove(askpass_path)
            except: pass

def run_ssh(ip, remote_cmd):
    return _run_ssh_core(ip, remote_cmd)

def run_ssh_binary(ip, remote_cmd):
    """专门用于下载文件的二进制流获取"""
    askpass_path = _create_temp_askpass()
    try:
        env = os.environ.copy() 
        env["SSH_ASKPASS"] = askpass_path
        env["DISPLAY"] = env.get("DISPLAY", ":0")
        env["SSH_ASKPASS_REQUIRE"] = "force"
        cmd = ["setsid", "ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=no", 
               "-o", "PasswordAuthentication=yes", "-o", "ConnectTimeout=10", "-p", str(SSH_PORT),
               "%s@%s" % (USERNAME, ip), remote_cmd]
        cmd = [_to_process_arg(part) for part in cmd]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        out, err = proc.communicate()
        return proc.returncode, out, err
    finally:
        if os.path.exists(askpass_path):
            try: os.remove(askpass_path)
            except: pass

def run_scp(ip, local_path, remote_path):
    """上传文件，支持 sudo 提权并智能继承原文件或父目录的归属权"""
    try:
        mtime = os.path.getmtime(local_path)
        dt = datetime.datetime.fromtimestamp(mtime)
        touch_ts = dt.strftime("%Y%m%d%H%M.%S")
    except Exception:
        touch_ts = None

    with open(local_path, "rb") as f:
        file_data = f.read()
    
    # 临时文件放在 /tmp 下，保证当前用户 yunda 有权写入
    tmp_path = "/tmp/up_%d_%d" % (os.getpid(), random.randint(1000, 9999))
    remote_dir = posixpath.dirname(remote_path) or "."
    
    safe_pass = PASSWORD.replace("'", "'\\''")
    
    # 核心逻辑：
    # 1. 探测归属：如果目标文件存在则取目标文件，否则取父目录归属。
    # 2. 提权移动：使用 sudo 移动到目标位置。
    # 3. 归属恢复：将文件改回探测到的 Owner:Group。
    remote_cmd = (
        "OWNER=$(stat -c '%%U:%%G' %s 2>/dev/null || stat -c '%%U:%%G' %s 2>/dev/null || echo 'yunda:yunda'); "
        "cat > %s && "
        "echo '%s' | sudo -S mkdir -p %s && "
        "echo '%s' | sudo -S mv %s %s && "
        "echo '%s' | sudo -S chown $OWNER %s"
    ) % (
        _shell_quote(remote_path), _shell_quote(remote_dir),
        _shell_quote(tmp_path),
        safe_pass, _shell_quote(remote_dir),
        safe_pass, _shell_quote(tmp_path), _shell_quote(remote_path),
        safe_pass, _shell_quote(remote_path)
    )
    
    if touch_ts:
        remote_cmd += " && echo '%s' | sudo -S touch -t %s %s" % (safe_pass, touch_ts, _shell_quote(remote_path))
        
    return _run_ssh_core(ip, remote_cmd, stdin_data=file_data)

# ──────────────────────────────────────────────
#  业务功能函数
# ──────────────────────────────────────────────
def read_ip_list(ip_file):
    if not os.path.isfile(ip_file): return []
    ips = []
    with io.open(ip_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"): ips.append(line)
    return ips

def read_pgm_list(pgm_file):
    if not os.path.isfile(pgm_file): return []
    proc_entries = []; seen = set()
    with io.open(pgm_file, "r", encoding="utf-8") as f:
        for line in f:
            raw_line = line.strip()
            if not raw_line or raw_line.startswith("#"): continue
            parts = [item.strip() for item in raw_line.split("|", 2)]
            name = posixpath.basename(parts[0].rstrip("/"))
            if name and name not in seen:
                entry = {"name": name, "exec_path_hint": parts[0] if "/" in parts[0] else "",
                         "start_mode": parts[1] if len(parts)>=2 else "",
                         "start_command": parts[2] if len(parts)>=3 else ""}
                proc_entries.append(entry); seen.add(name)
    return proc_entries

def collect_local_files(local_dir):
    if not os.path.isdir(local_dir): return None
    files = []
    for root, dirs, filenames in os.walk(local_dir):
        for f in filenames:
            abs_p = os.path.join(root, f)
            rel_p = os.path.relpath(abs_p, local_dir).replace(os.sep, '/')
            files.append(rel_p)
    return sorted(files)

def find_process_records(ip, proc_name):
    if not proc_name: return []
    # 使用 sudo ps 以查看所有用户进程
    safe_pass = PASSWORD.replace("'", "'\\''")
    code, out = run_ssh(ip, "echo '%s' | sudo -S ps -eww -o pid=,comm=,args=" % safe_pass)
    if code != 0: return []
    records = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 2 or not parts[0].isdigit(): continue
        pid, comm = parts[0], parts[1]
        args = parts[2] if len(parts) > 2 else ""
        if comm == proc_name or proc_name in args:
            # 必须用 sudo readlink，否则无法读取 root 进程的 exe 路径
            code_l, out_l = run_ssh(ip, "echo '%s' | sudo -S readlink /proc/%s/exe" % (safe_pass, pid))
            exe_p = out_l.replace(" (deleted)", "").strip() if code_l == 0 else ""
            if exe_p and posixpath.basename(exe_p) == proc_name:
                records.append({"pid": pid, "exe_path": exe_p})
    return records

def do_kill(ip, proc_name):
    records = find_process_records(ip, proc_name)
    if not records: return True, None, {}
    pids = [r["pid"] for r in records]
    safe_pass = PASSWORD.replace("'", "'\\''")
    # 使用 sudo 读取环境变量
    env_code, env_out = run_ssh(ip, "echo '%s' | sudo -S tr '\\000' '\\n' < /proc/%s/environ" % (safe_pass, pids[0]))
    start_env = {}
    if env_code == 0:
        for line in env_out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k in START_ENV_KEYS: start_env[k] = v
    run_ssh(ip, "echo '%s' | sudo -S kill -9 %s" % (safe_pass, " ".join(pids)))
    return True, records[0]["exe_path"], start_env

def do_backup(ip, remote_path):
    code, _ = run_ssh(ip, "test -f %s" % _shell_quote(remote_path))
    if code != 0: return True
    b_dir = posixpath.join(posixpath.dirname(remote_path), "BAK")
    b_path = posixpath.join(b_dir, posixpath.basename(remote_path) + "." + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    safe_pass = PASSWORD.replace("'", "'\\''")
    # 使用 sudo 创建目录并执行带权限保留的备份
    run_ssh(ip, "echo '%s' | sudo -S mkdir -p %s && echo '%s' | sudo -S cp -p %s %s" % (
        safe_pass, _shell_quote(b_dir), safe_pass, _shell_quote(remote_path), _shell_quote(b_path)))
    return True

def do_upload(ip, remote_path, local_path, make_exec=False):
    """上传，设置权限，并生成上传日志"""
    code, _ = run_scp(ip, local_path, remote_path)
    is_success = (code == 0)
    
    if is_success and make_exec:
        # 即使文件带 x 位，也通过 sudo 执行 chmod 以确保权限应用成功
        if os.stat(local_path).st_mode & 0o111:
            safe_pass = PASSWORD.replace("'", "'\\''")
            run_ssh(ip, "echo '%s' | sudo -S chmod +x %s" % (safe_pass, _shell_quote(remote_path)))
            
    # 执行完文件传输后，记录到日志文件
    log_upload_result(ip, local_path, remote_path, is_success)
    if not is_success:
        safe_print("[%s] [ERROR] 上传失败: %s" % (ip, remote_path))
    return is_success

# ──────────────────────────────────────────────
#  并发引擎
# ──────────────────────────────────────────────
class ThreadPool(object):
    def __init__(self, n):
        self.q = queue.Queue()
        self.n = n
    def add_task(self, func, *args):
        self.q.put((func, args))
    def _worker(self):
        while True:
            try:
                func, args = self.q.get(block=False)
                func(*args)
                self.q.task_done()
            except queue.Empty: break
            except Exception as e:
                safe_print("[ERROR] Runtime: %s" % str(e))
                self.q.task_done()
    def wait(self):
        threads = []
        for _ in range(min(self.n, self.q.qsize() or self.n)):
            t = threading.Thread(target=self._worker)
            t.daemon = True 
            t.start(); threads.append(t)
        for t in threads: t.join()

# ──────────────────────────────────────────────
#  业务逻辑辅助函数
# ──────────────────────────────────────────────
def get_start_cmd(ip, entry, exe_p, fallback_mode, env_dict):
    """
    生成远端启动命令。
    优先使用 pgm.txt 中的 start_command，否则使用 ./basename。
    """
    mode = entry.get("start_mode") or fallback_mode
    work_dir = posixpath.dirname(exe_p)
    # 优先使用配置的启动命令，若无则使用 ./文件名
    cmd_body = entry.get("start_command") or ("./" + posixpath.basename(exe_p))
    
    # 环境变量恢复
    env_s = "export DISPLAY=%s; " % env_dict.get("DISPLAY", ":0")
    for k in ("XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"):
        if k in env_dict:
            env_s += "export %s=%s; " % (k, env_dict[k])

    if "t" in mode.lower():
        # 终端启动模式
        full_cmd = "cd %s && nohup setsid mate-terminal -e '%s' >/dev/null 2>&1 &" % (_shell_quote(work_dir), cmd_body)
    elif "d" in mode.lower() or "direct" in mode.lower():
        # 直接后台启动
        full_cmd = "cd %s && nohup setsid %s >/dev/null 2>&1 &" % (_shell_quote(work_dir), cmd_body)
    else:
        # 不启动或其他
        return None
        
    return env_s + full_cmd


# ──────────────────────────────────────────────
#  各个模式的并发任务封装
# ──────────────────────────────────────────────
def task_mode_0(ip, remote_path):
    safe_print("[%s] 执行模式 0 (文件存在性检查)..." % ip)
    code, _ = run_ssh(ip, "test -e %s" % _shell_quote(remote_path))
    status = "存在" if code == 0 else "不存在"
    safe_print("[%s] 远端路径 %s : %s" % (ip, remote_path, status))

def task_mode_1(ip, remote_path, local_path):
    safe_print("[%s] 执行模式 1 (直传)..." % ip)
    do_upload(ip, remote_path, local_path, False)

def task_mode_2(ip, remote_path, local_path):
    safe_print("[%s] 执行模式 2 (备份+上传)..." % ip)
    if do_backup(ip, remote_path):
        do_upload(ip, remote_path, local_path, False)

def task_mode_3(ip, remote_path, local_path, proc_name, start_mode, registered):
    safe_print("[%s] 执行模式 3 (单文件更新)..." % ip)
    paths, envs = {}, {}
    for entry in registered:
        _, p, e = do_kill(ip, entry["name"])
        if p: paths[entry["name"]] = p
        if e: envs[entry["name"]] = e
    if proc_name and proc_name not in paths: paths[proc_name] = remote_path
    
    if do_backup(ip, remote_path):
        if do_upload(ip, remote_path, local_path, True):
            for entry in registered:
                name = entry["name"]; exe_p = paths.get(name)
                if not exe_p: continue
                
                env_dict = envs.get(name, {})
                cmd = get_start_cmd(ip, entry, exe_p, start_mode, env_dict)
                if cmd:
                    run_ssh(ip, cmd)
            safe_print("[%s] 模式 3 部署完成。" % ip)

def task_mode_4(ip, local_dir, remote_dir, proc_name, start_mode, registered, local_files):
    safe_print("[%s] 执行模式 4 (目录级更新)..." % ip)
    paths, envs = {}, {}
    for entry in registered:
        _, p, e = do_kill(ip, entry["name"])
        if p: paths[entry["name"]] = p
        if e: envs[entry["name"]] = e
    if proc_name and proc_name not in paths: paths[proc_name] = posixpath.join(remote_dir, proc_name)
    
    all_ok = True
    for rel in local_files:
        if not do_backup(ip, posixpath.join(remote_dir, rel)): all_ok = False
        if not do_upload(ip, posixpath.join(remote_dir, rel), os.path.join(local_dir, rel), True): all_ok = False
    
    if all_ok:
        for entry in registered:
            name = entry["name"]; exe_p = paths.get(name)
            if not exe_p: continue
            
            env_dict = envs.get(name, {})
            cmd = get_start_cmd(ip, entry, exe_p, start_mode, env_dict)
            if cmd:
                run_ssh(ip, cmd)
        safe_print("[%s] 模式 4 部署完成。" % ip)

def task_mode_5(ip, exec_path, proc_name, start_mode):
    safe_print("[%s] 执行模式 5 (按需启动)..." % ip)
    if find_process_records(ip, proc_name):
        safe_print("[%s] 进程 %s 已在运行，跳过。" % (ip, proc_name))
        return
    code, _ = run_ssh(ip, "test -f %s" % _shell_quote(exec_path))
    if code == 0:
        entry = {"name": proc_name, "start_mode": start_mode}
        # 模式 5 无法通过 /proc 恢复环境，使用默认
        cmd = get_start_cmd(ip, entry, exec_path, start_mode, {})
        if cmd:
            run_ssh(ip, cmd)
        safe_print("[%s] 已发送启动指令。" % ip)

def task_mode_6(ip, proc_name, registered):
    safe_print("[%s] 执行模式 6 (纯查杀)..." % ip)
    for entry in registered: do_kill(ip, entry["name"])
    if proc_name: do_kill(ip, proc_name)

def task_mode_7(ip, local_dir, remote_dir, local_files):
    safe_print("[%s] 执行模式 7 (纯目录上传)..." % ip)
    for rel in local_files:
        if do_backup(ip, posixpath.join(remote_dir, rel)):
            do_upload(ip, posixpath.join(remote_dir, rel), os.path.join(local_dir, rel), True)

def task_mode_8(ip):
    """新增：模式 8 - 发送重启指令"""
    safe_print("[%s] 执行模式 8: 准备下发重启系统命令..." % ip)
    # 提供 sudo 和普通 reboot 双重兜底，SSH 断开的报错将被忽略
    cmd = "echo '%s' | sudo -S reboot || reboot" % PASSWORD.replace("'", "'\\''")
    run_ssh(ip, cmd)
    safe_print("[%s] 重启命令已下发 (如果该主机 SSH 连接已断开，说明重启已生效)。" % ip)

def task_mode_9(ip, command):
    """模式 9: 批量执行任意命令"""
    safe_print("[%s] 执行命令: %s" % (ip, command))
    safe_pass = PASSWORD.replace("'", "'\\''")
    # 使用 bash -c 以支持复杂的管道或重定向
    cmd = "echo '%s' | sudo -S bash -c %s" % (safe_pass, _shell_quote(command))
    code, out = run_ssh(ip, cmd)
    safe_print("[%s] 返回码: %d\n内容如下:\n%s\n%s" % (ip, code, out, "-"*40))

def task_mode_10(ip, remote_path):
    """模式 10: 批量删除 (支持 tmp* 等通配符)"""
    safe_print("[%s] 准备删除: %s" % (ip, remote_path))
    safe_pass = PASSWORD.replace("'", "'\\''")
    # 为了支持通配符扩展，通过 bash -c 执行 rm
    # 此时 remote_path 内部若有单引号需进行转义处理
    inner_cmd = "rm -rf %s" % remote_path
    cmd = "echo '%s' | sudo -S bash -c %s" % (safe_pass, _shell_quote(inner_cmd))
    code, out = run_ssh(ip, cmd)
    if code == 0:
        safe_print("[%s] 删除完成。" % ip)
    else:
        safe_print("[%s] 删除失败: %s" % (ip, out))

def task_mode_11(ip, remote_path, local_dir):
    """模式 11: 批量下载文件 (Fetch)"""
    safe_print("[%s] 正在下载: %s" % (ip, remote_path))
    if not os.path.exists(local_dir):
        try: os.makedirs(local_dir)
        except: pass
    
    fname = posixpath.basename(remote_path)
    local_path = os.path.join(local_dir, "%s.%s" % (fname, ip))
    
    safe_pass = PASSWORD.replace("'", "'\\''")
    # 使用 sudo cat 读取文件并重定向到本地
    cmd = "echo '%s' | sudo -S cat %s" % (safe_pass, _shell_quote(remote_path))
    code, out, err = run_ssh_binary(ip, cmd)
    
    if code == 0:
        with open(local_path, "wb") as f:
            f.write(out)
        safe_print("[%s] 下载成功 -> %s" % (ip, local_path))
    else:
        safe_print("[%s] 下载失败: %s" % (ip, _to_str(err)))

def task_mode_12(ip):
    """模式 12: 在线状态检查"""
    code, _ = run_ssh(ip, "echo ok")
    status = "【在线】" if code == 0 else "【无法连接】"
    safe_print("[%s] 状态: %s" % (ip, status))

# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print("用法: python cp_update.py 占位路径 模式[0-12] [进程名] [目标路径] [启动模式]")
        return
    
    argv = [_decode_cli_arg(arg) for arg in sys.argv]
    r_path, mode = argv[1], argv[2]
    proc_name = argv[3] if len(argv) > 3 else ""
    
    # --- 智能参数解析：根据模式决定参数含义 ---
    if mode in ("1", "2", "7", "10", "11"):
        # 路径优先模式：参数 3 即为目标路径/本地目录
        target_dir = argv[3] if len(argv) > 3 else r_path
        start_mode = "n"
    elif mode in ("3", "5"):
        # 进程优先模式(短)：参数 1=路径, 3=进程名, 4=启动模式
        target_dir = r_path
        start_mode = argv[4] if len(argv) > 4 else "n"
    elif mode == "4":
        # 进程优先模式(长)：参数 1=路径, 3=进程名, 4=目标目录, 5=启动模式
        target_dir = argv[4] if len(argv) > 4 else r_path
        start_mode = argv[5] if len(argv) > 5 else "n"
    else:
        # 其他模式 (0, 6, 8, 9, 12)
        target_dir = argv[4] if len(argv) > 4 else r_path
        start_mode = argv[5] if len(argv) > 5 else "n"

    ips = read_ip_list(IP_FILE)
    reg = read_pgm_list(PGM_FILE)
    if not ips: 
        print("ip.txt 为空或未找到！")
        return

    pool = ThreadPool(MAX_WORKERS)
    
    # 根据模式将任务推入并发池
    if mode == "0":
        for ip in ips: pool.add_task(task_mode_0, ip, r_path)
    elif mode == "1":
        for ip in ips: pool.add_task(task_mode_1, ip, r_path, r_path)
    elif mode == "2":
        for ip in ips: pool.add_task(task_mode_2, ip, r_path, r_path)
    elif mode == "3":
        for ip in ips: pool.add_task(task_mode_3, ip, r_path, r_path, proc_name, start_mode, reg)
    elif mode == "4":
        files = collect_local_files(r_path)
        for ip in ips: pool.add_task(task_mode_4, ip, r_path, target_dir, proc_name, start_mode, reg, files)
    elif mode == "5":
        for ip in ips: pool.add_task(task_mode_5, ip, r_path, proc_name, start_mode)
    elif mode == "6":
        for ip in ips: pool.add_task(task_mode_6, ip, proc_name, reg)
    elif mode == "7":
        files = collect_local_files(r_path)
        for ip in ips: pool.add_task(task_mode_7, ip, r_path, target_dir, files)
    elif mode == "8":
        for ip in ips: pool.add_task(task_mode_8, ip)
    elif mode == "9":
        for ip in ips: pool.add_task(task_mode_9, ip, r_path)
    elif mode == "10":
        for ip in ips: pool.add_task(task_mode_10, ip, r_path)
    elif mode == "11":
        # 如果参数 3 为空，则下载到当前目录的 downloads 文件夹
        target_local = proc_name if proc_name else "downloads"
        for ip in ips: pool.add_task(task_mode_11, ip, r_path, target_local)
    elif mode == "12":
        for ip in ips: pool.add_task(task_mode_12, ip)
    else:
        print("未知模式: %s，请使用 0-12。" % mode)
        return
        
    pool.wait()
    safe_print("\n[INFO] 全部并发处理完毕。")

if __name__ == "__main__":
    main()