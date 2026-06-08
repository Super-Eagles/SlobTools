#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cp_update.py  --  兼容 Python 2.7 / Python 3，仅用标准库，无第三方依赖
密码注入原理：生成临时 askpass 脚本 + SSH_ASKPASS 环境变量 + setsid 脱离终端

新增：模式 3/4 完成后可自动重启进程
  启动模式参数：
    d / direct  直接后台启动（nohup ... > /dev/null 2>&1 &）
    t / term    终端会话启动（mate-terminal，保留虚拟终端，断开 SSH 不影响）
    不填 / n    仅做文件操作，不启动进程
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
import time  # [FIX] 移到顶层，不再在函数内部 import
import random

# ──────────────────────────────────────────────
#  Python 2 / 3 兼容
# ──────────────────────────────────────────────
PY3 = sys.version_info[0] >= 3

try:
    text_type = unicode
except NameError:
    text_type = str

try:
    binary_type = bytes
except NameError:
    binary_type = str


def _get_cli_encoding():
    try:
        enc = locale.getpreferredencoding(False)
    except TypeError:
        enc = locale.getpreferredencoding()
    return enc or sys.getfilesystemencoding() or "utf-8"


def _decode_cli_arg(arg):
    if isinstance(arg, text_type):
        return arg
    for enc in (_get_cli_encoding(), "utf-8", "gbk"):
        try:
            return arg.decode(enc)
        except Exception:
            pass
    return arg.decode("utf-8", "replace")


def _ensure_text(value):
    if isinstance(value, text_type):
        return value
    if isinstance(value, binary_type):
        return _decode_cli_arg(value)
    return text_type(value)


def _to_process_arg(value):
    if PY3 or isinstance(value, binary_type):
        return value
    value = _ensure_text(value)
    for enc in (_get_cli_encoding(), "utf-8"):
        try:
            return value.encode(enc)
        except Exception:
            pass
    return value.encode("utf-8", "replace")


def _shell_quote(value):
    value = _ensure_text(value)
    return "'%s'" % value.replace("'", "'\"'\"'")


def _to_bytes(s):
    if isinstance(s, binary_type):
        return s
    if isinstance(s, text_type):
        return s.encode("utf-8")
    return _ensure_text(s).encode("utf-8")


def _to_str(b):
    if isinstance(b, bytes):
        return b.decode("utf-8", errors="replace")
    return b


# ========== 配置变量 ==========
USERNAME = "yunda"
PASSWORD = "Aa123456"
IP_FILE  = "ip.txt"
PGM_FILE = "pgm.txt"
SSH_PORT = 22
PREFERRED_EXEC_PATH_KEYWORD = "YD_TDS"
START_ENV_KEYS = (
    "DISPLAY",
    "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
)
# ==============================

USAGE = """
用法:
  先编写好 ip.txt 将所有需要处理的 IP 地址写入（每行一个，# 开头为注释）
  需要查杀/按顺序重启的进程请登记到 pgm.txt（每行一个，# 开头为注释）
  模式 3 / 4 / 6 的实际查杀列表以 pgm.txt 为准
  模式 3 / 4 的重启顺序也以 pgm.txt 为准
  参数3建议填写主进程名：用于主进程路径识别，以及主进程未运行时的兜底启动路径

  pgm.txt 支持两种格式：
    1) 仅登记进程名：进程名
    2) 登记进程路径 + 启动模式：
       /绝对路径/进程名|启动模式|
    3) 登记进程名/路径 + 启动模式 + 启动命令：
       进程名或/绝对路径/进程名|启动模式|启动命令
       启动模式可填：d/direct/t/term/n/none
       第一列若带 / 路径，则 basename 作为进程名参与查杀，重启时优先使用这条路径
       启动命令为远端命令内容；若记录到了该进程的真实路径，或第一列提供了路径，则会先切到该路径所在目录再执行
       实际启动骨架为：
         d: cd <目录> && 恢复原进程桌面环境后执行 nohup setsid <命令> >/dev/null 2>&1 </dev/null &
         t: cd <目录> && 恢复原进程桌面环境后执行 nohup setsid mate-terminal -e <命令> >/dev/null 2>&1 </dev/null &
       例如：
          MainNodeV3
          /data/td/WorkerNode|d|
          WorkerNode|d|./WorkerNode --config worker.ini
          UiDaemon|t|./UiDaemon --profile prod

  python cp_update.py 参数1-路径 参数2-操作模式 [参数3-主进程名] [参数4-目标目录] [启动模式]

操作模式:
  0  查询远端文件是否存在，汇总显示结果
     示例：python cp_update.py /data/YD_TWS/aaa 0

  1  直接上传本地同路径文件覆盖远端
     单文件上传，不递归目录，不额外执行 chmod +x
     示例：python cp_update.py /data/YD_TWS/aaa 1

  2  先备份远端文件，再上传覆盖
     单文件上传，不递归目录，不额外执行 chmod +x
     示例：python cp_update.py /data/YD_TWS/aaa 2

  3  按 pgm.txt 顺序查杀进程 + 备份 + 单文件上传覆盖 + 按 pgm.txt 顺序重启
     参数1=本地文件路径，同时也是远端目标文件路径
     参数3=主进程名；若主进程当前未运行，则用参数1作为该主进程的兜底启动路径
     上传后仅当本地文件带 x 位时，远端才执行 chmod +x
     每个进程优先使用 pgm.txt 自己配置的启动模式/启动命令；未配置时回退到命令行给定的启动模式
     不重启：python cp_update.py /data/YD_TWS/aaa 3 MainNodeV3
     后台启：python cp_update.py /data/YD_TWS/aaa 3 MainNodeV3 d
     终端启：python cp_update.py /data/YD_TWS/aaa 3 MainNodeV3 t

  4  按 pgm.txt 顺序查杀进程 + 整个目录递归备份上传 + 按 pgm.txt 顺序重启
     参数1=本地目录；参数4=远端目标目录（必填）
     参数3=主进程名；若主进程当前未运行，则用 参数4/参数3 作为该主进程的兜底启动路径
     目录会递归上传所有普通文件，并保留相对目录结构；空目录不会单独创建
     上传后仅当本地文件带 x 位时，远端才执行 chmod +x
     每个进程优先使用 pgm.txt 自己配置的启动模式/启动命令；未配置时回退到命令行给定的启动模式
                                             本地目录  模式  主进程名     目标目录    启动模式
     不重启：python cp_update.py MainNode  4  MainNodeV3  /data/YD_TWS/MainNode
     后台启：python cp_update.py MainNode  4  MainNodeV3  /data/YD_TWS/MainNode  d
     终端启：python cp_update.py MainNode  4  MainNodeV3  /data/YD_TWS/MainNode  t

  5  检查进程是否在运行，没运行才启动，已在运行则跳过
     只检查参数3这个进程名，不读取 pgm.txt
     必填：参数1=可执行文件远端绝对路径  参数3=进程名  参数4=启动模式(d 或 t)
                                                 可执行路径                       模式  进程名       启动模式
     后台启：python cp_update.py /data/YD_TWS/MainNode/MainNodeV3  5  MainNodeV3  d
     终端启：python cp_update.py /data/YD_TWS/MainNode/MainNodeV3  5  MainNodeV3  t

  6  仅按 pgm.txt 顺序查杀进程，不上传、不启动
     实际查杀列表以 pgm.txt 为准；参数3建议填写主进程名，兼容旧用法
                              占位参数1  模式  主进程名
     示例：python cp_update.py .  6  MainNodeV3

  7  仅递归备份和上传目录（不杀进程、不启动）
     必填：参数1=本地目录  参数3=远端目标目录
     目录会递归上传所有普通文件，并保留相对目录结构；空目录不会单独创建
     上传后仅当本地文件带 x 位时，远端才执行 chmod +x
                                本地目录  模式  目标目录
     示例：python cp_update.py MainNode  7  /data/YD_TWS/MainNode

  启动模式说明（模式 3/4/5 有效）:
  d / direct   接近图形界面双击程序后选择“直接启动”
               实际命令形态：cd <目录> && 恢复 DISPLAY/XAUTHORITY/XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS 后执行 nohup setsid <命令> >/dev/null 2>&1 </dev/null &
  t / term     接近图形界面双击程序后选择“在终端中启动”
               实际命令形态：cd <目录> && 恢复 DISPLAY/XAUTHORITY/XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS 后执行 nohup setsid mate-terminal -e <命令> >/dev/null 2>&1 </dev/null &
  不填 / n     完成操作后不启动进程（模式 5 必须填 d 或 t）
"""

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "BatchMode=no",
    "-o", "PasswordAuthentication=yes",
    "-o", "ConnectTimeout=10",
    "-p", str(SSH_PORT),
]

# 全局临时 askpass 脚本路径
_ASKPASS_PATH = None


# ──────────────────────────────────────────────
#  SSH askpass 机制
# ──────────────────────────────────────────────

def _get_askpass():
    """创建一次性 askpass 脚本（懒创建），返回其路径"""
    global _ASKPASS_PATH
    if _ASKPASS_PATH and os.path.isfile(_ASKPASS_PATH):
        return _ASKPASS_PATH
    fd, path = tempfile.mkstemp(prefix="askpass_", suffix=".sh")
    script = "#!/bin/sh\necho '%s'\n" % PASSWORD.replace("'", "'\\''")
    os.write(fd, _to_bytes(script))
    os.close(fd)
    os.chmod(path, stat.S_IRWXU)
    _ASKPASS_PATH = path
    return path


def _cleanup_askpass():
    global _ASKPASS_PATH
    if _ASKPASS_PATH and os.path.isfile(_ASKPASS_PATH):
        os.remove(_ASKPASS_PATH)
        _ASKPASS_PATH = None


def _make_env():
    """构造带 SSH_ASKPASS 的环境变量"""
    env = os.environ.copy()
    env["SSH_ASKPASS"] = _get_askpass()
    env["DISPLAY"]     = env.get("DISPLAY", ":0")   # SSH_ASKPASS 要求有 DISPLAY
    # OpenSSH 8.4+ 新增，强制使用 askpass
    env["SSH_ASKPASS_REQUIRE"] = "force"
    return env


# ──────────────────────────────────────────────
#  SSH / SCP 核心执行函数
# ──────────────────────────────────────────────

def run_ssh(ip, remote_cmd):
    """
    用 setsid 脱离终端后执行 ssh 命令，SSH 自动调用 SSH_ASKPASS 获取密码。
    返回 (returncode, stdout+stderr 合并字符串)
    """
    cmd = ["setsid", "ssh"] + SSH_OPTS + [
        "%s@%s" % (USERNAME, ip), remote_cmd
    ]
    cmd = [_to_process_arg(part) for part in cmd]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_make_env(),
    )
    out, err = proc.communicate()
    output = (_to_str(out) + _to_str(err)).strip()
    return proc.returncode, output





def run_scp(ip, local_path, remote_path):
    """
    通过 ssh stdin 先写入临时文件再原子 mv，防止上传中断导致远端文件损坏。
    返回 (returncode, 输出字符串)
    """
    with open(local_path, "rb") as f:
        file_data = f.read()

    tmp_path   = "%s.upload_tmp_%d_%d" % (
        remote_path, os.getpid(), random.randint(1000, 999999))
    remote_dir = posixpath.dirname(remote_path) or "."
    remote_cmd = "mkdir -p %s && cat > %s && mv %s %s" % (
        _shell_quote(remote_dir),
        _shell_quote(tmp_path),
        _shell_quote(tmp_path),
        _shell_quote(remote_path),
    )
    cmd = ["setsid", "ssh"] + SSH_OPTS + [
        "%s@%s" % (USERNAME, ip),
        remote_cmd,
    ]
    cmd = [_to_process_arg(part) for part in cmd]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_make_env(),
    )
    out, err = proc.communicate(input=file_data)
    output = (_to_str(out) + _to_str(err)).strip()
    return proc.returncode, output


# ──────────────────────────────────────────────
#  工具函数
# ──────────────────────────────────────────────

def read_ip_list(ip_file):
    if not os.path.isfile(ip_file):
        print("[ERROR] 找不到 IP 列表文件: %s" % ip_file)
        sys.exit(1)
    ips = []
    with io.open(ip_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ips.append(line)
    return ips


def read_pgm_list(pgm_file):
    if not os.path.isfile(pgm_file):
        print("[ERROR] 找不到进程登记文件: %s" % pgm_file)
        sys.exit(1)

    proc_entries = []
    seen = set()
    with io.open(pgm_file, "r", encoding="utf-8") as f:
        for line in f:
            raw_line = line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue

            parts = [item.strip() for item in raw_line.split("|", 2)]
            raw_target = parts[0]
            if not raw_target:
                continue

            exec_path_hint = ""
            name = raw_target
            if "/" in raw_target:
                exec_path_hint = raw_target
                name = posixpath.basename(raw_target.rstrip("/"))
            if not name:
                continue
            if name in seen:
                continue

            entry = {
                "name": name,
                "exec_path_hint": exec_path_hint,
                "start_mode": "",
                "start_command": "",
            }

            if len(parts) >= 2 and parts[1]:
                mode = parts[1].lower()
                valid_modes = ("d", "direct", "t", "term", "n", "no", "none")
                if mode not in valid_modes:
                    print("[ERROR] pgm.txt 中进程 '%s' 的启动模式无效: %s" % (name, parts[1]))
                    sys.exit(1)
                entry["start_mode"] = parts[1]

            if len(parts) >= 3 and parts[2]:
                entry["start_command"] = parts[2]

            seen.add(name)
            proc_entries.append(entry)

    if not proc_entries:
        print("[ERROR] 进程登记文件为空，请检查 %s" % pgm_file)
        sys.exit(1)

    return proc_entries


def collect_local_files(local_dir):
    """
    递归收集目录下所有普通文件，并跟随符号链接目录。
    返回相对路径列表（统一使用 / 作为分隔符）。
    """
    if not os.path.isdir(local_dir):
        print("[ERROR] 本地目录不存在: %s" % local_dir)
        return None

    root_dir = os.path.abspath(local_dir)
    pending = [("", root_dir)]
    visited_dirs = set()
    files = []

    while pending:
        rel_dir, abs_dir = pending.pop()
        real_dir = os.path.realpath(abs_dir)
        if real_dir in visited_dirs:
            print("  [WARN] 检测到符号链接目录循环，跳过: %s" % abs_dir)
            continue
        visited_dirs.add(real_dir)

        try:
            names = sorted(os.listdir(abs_dir))
        except OSError as exc:
            print("[ERROR] 读取目录失败: %s (%s)" % (abs_dir, exc))
            return None

        for name in names:
            abs_path = os.path.join(abs_dir, name)
            rel_path = name if not rel_dir else rel_dir + "/" + name

            if os.path.isdir(abs_path):
                pending.append((rel_path, abs_path))
            elif os.path.isfile(abs_path):
                files.append(rel_path)
            elif os.path.islink(abs_path):
                print("  [WARN] 跳过失效符号链接: %s" % rel_path)

    files.sort()
    return files


def _local_file_path(local_dir, rel_path):
    return os.path.join(local_dir, rel_path.replace("/", os.sep))


def _remote_file_path(remote_dir, rel_path):
    return posixpath.join(remote_dir.rstrip("/") or "/", rel_path)


def _clean_proc_token(token):
    token = _ensure_text(token).strip()
    if not token:
        return ""
    return token.strip("'\";,")


def _proc_token_matches(proc_name, token):
    token = _clean_proc_token(token)
    target = _clean_proc_token(proc_name)
    if not token or not target:
        return False
    return token == target or posixpath.basename(token) == posixpath.basename(target)


def _is_exec_like_token(token):
    token = _clean_proc_token(token)
    if not token:
        return False
    base = posixpath.basename(token)
    if "/" in token or "\\" in token:
        return True
    if "." in base:
        return True
    return False


def _proc_matches(proc_name, comm, args):
    if _proc_token_matches(proc_name, comm):
        return True

    tokens = _ensure_text(args).split()
    for idx, token in enumerate(tokens):
        if not _proc_token_matches(proc_name, token):
            continue

        # 只把更像可执行文件/脚本路径的位置视为目标进程，避免误命中普通参数。
        if idx == 0 or _is_exec_like_token(token):
            return True

    return False


def _read_proc_exe(ip, pid):
    code, out = run_ssh(ip, "readlink /proc/%s/exe" % pid)
    if code != 0:
        return None

    raw_path = out.strip()
    if not raw_path:
        return None
    if raw_path.endswith(" (deleted)"):
        raw_path = raw_path.replace(" (deleted)", "")
    return raw_path


def _read_proc_start_env(ip, pid):
    """
    从 /proc/PID/environ 读取与桌面会话相关的关键环境变量，
    供后续重启时复用。
    """
    code, out = run_ssh(ip, "tr '\\000' '\\n' < /proc/%s/environ" % pid)
    if code != 0:
        return {}

    start_env = {}
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in START_ENV_KEYS and value:
            start_env[key] = value
    return start_env


def _build_start_env_prefix(start_env):
    start_env = start_env or {}

    display = _ensure_text(start_env.get("DISPLAY", "")).strip() or ":0"
    steps = [
        "DISPLAY=%s" % _shell_quote(display),
    ]

    xauthority = _ensure_text(start_env.get("XAUTHORITY", "")).strip()
    if xauthority:
        steps.append("XAUTHORITY=%s" % _shell_quote(xauthority))
    else:
        steps.append("XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}")

    xdg_runtime_dir = _ensure_text(start_env.get("XDG_RUNTIME_DIR", "")).strip()
    if xdg_runtime_dir:
        steps.append("XDG_RUNTIME_DIR=%s" % _shell_quote(xdg_runtime_dir))
    else:
        steps.append("XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}")

    dbus_addr = _ensure_text(start_env.get("DBUS_SESSION_BUS_ADDRESS", "")).strip()
    if dbus_addr:
        steps.append("DBUS_SESSION_BUS_ADDRESS=%s" % _shell_quote(dbus_addr))
    else:
        steps.append(
            "if [ -z \"$DBUS_SESSION_BUS_ADDRESS\" ] && [ -n \"$XDG_RUNTIME_DIR\" ] "
            "&& [ -S \"$XDG_RUNTIME_DIR/bus\" ]; then "
            "DBUS_SESSION_BUS_ADDRESS=\"unix:path=$XDG_RUNTIME_DIR/bus\"; fi"
        )

    steps.append("export DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS")
    return "; ".join(steps)


def make_backup_path(remote_path):
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_dir = posixpath.dirname(remote_path)
    remote_name = posixpath.basename(remote_path)
    backup_dir = posixpath.join(remote_dir, "BAK") if remote_dir else "BAK"
    backup_name = "%s.%s" % (remote_name, now)
    backup_path = posixpath.join(backup_dir, backup_name)
    return backup_dir, backup_path


def local_has_exec_bit(local_path):
    """
    按本地文件权限判断是否带执行位。
    仅根据 stat 的 x 位判断；没有 x 位时不在远端额外执行 chmod +x。
    """
    try:
        mode = os.stat(local_path).st_mode
    except OSError as exc:
        print("  [WARN] 读取本地文件权限失败，按无执行位处理: %s (%s)" % (local_path, exc))
        return False

    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def do_backup(ip, remote_path):
    """备份远端文件（仅当文件存在时执行）。若源文件存在但备份失败，返回 False。"""
    chk_code, chk_out = run_ssh(
        ip, "test -f %s && echo __EXISTS__ || echo __MISSING__" % _shell_quote(remote_path))
    if chk_code != 0:
        print("  [WARN] 检查远端文件是否存在失败: %s" % chk_out)
        return False
    if "__EXISTS__" not in chk_out and "__MISSING__" not in chk_out:
        print("  [WARN] 检查远端文件返回异常: %s" % chk_out)
        return False
    if "__EXISTS__" not in chk_out:
        print("  [INFO] 远端文件不存在，跳过备份")
        return True
    backup_dir, backup_path = make_backup_path(remote_path)
    code, out = run_ssh(
        ip,
        "mkdir -p %s && cp %s %s" % (
            _shell_quote(backup_dir),
            _shell_quote(remote_path),
            _shell_quote(backup_path),
        )
    )
    if code != 0:
        print("  [WARN] 备份失败: %s" % out)
        return False
    print("  [OK]  备份成功 -> %s" % backup_path)
    return True


def do_upload(ip, remote_path, local_path, make_exec=False):
    """
    上传本地文件到远端。
    make_exec=True 时按本地文件是否带 x 位决定是否执行 chmod +x。
    """
    code, out = run_scp(ip, local_path, remote_path)
    if code != 0:
        print("  [ERROR] 上传失败: %s" % out)
        return False
    print("  [OK]  上传成功: %s -> %s:%s" % (local_path, ip, remote_path))
    if make_exec:
        if local_has_exec_bit(local_path):
            x_code, x_out = run_ssh(ip, "chmod +x %s" % _shell_quote(remote_path))
            if x_code != 0:
                print("  [WARN] 设置可执行权限失败: %s" % x_out)
            else:
                print("  [OK]  已按本地权限设置可执行位: %s" % remote_path)
        else:
            print("  [INFO] 本地文件无执行位，跳过 chmod +x: %s" % local_path)
    return True


def find_process_records(ip, proc_name):
    """
    查找候选 PID，并仅保留 /proc/PID/exe 的最后一级文件名
    与登记进程名完全相等的真实进程。
    """
    if not proc_name:
        return []

    proc_name = _ensure_text(proc_name)
    code, out = run_ssh(ip, "ps -eww -o pid=,comm=,args=")
    if code != 0:
        return []

    records = []
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split(None, 2)
        if len(parts) < 2 or not parts[0].isdigit():
            continue

        pid = parts[0]
        comm = parts[1]
        args = parts[2] if len(parts) > 2 else ""
        if _proc_matches(proc_name, comm, args):
            exe_path = _read_proc_exe(ip, pid)
            if not exe_path:
                continue
            if posixpath.basename(exe_path) != proc_name:
                continue

            exists_code, _ = run_ssh(ip, "test -f %s" % _shell_quote(exe_path))
            records.append({
                "pid": pid,
                "comm": comm,
                "args": args,
                "exe_path": exe_path,
                "exe_exists": (exists_code == 0),
            })

    return records


def find_pids(ip, proc_name):
    return [item["pid"] for item in find_process_records(ip, proc_name)]


def do_kill(ip, proc_name):
    """
    检查并杀掉真实可执行路径 basename 等于 proc_name 的所有进程实例。
    返回 (kill_ok, exec_path_or_None)：
      exec_path 是遍历 PID 从 /proc/PID/exe 读到的真实有效可执行文件路径，
      如果所有路径都不存在或读取失败时为 None。
    """
    if not proc_name:
        return False, None, {}

    proc_name = _ensure_text(proc_name)

    # 1. 查找真实 PID：只有 /proc/PID/exe 最后一级文件名等于登记名的才允许进入
    records = find_process_records(ip, proc_name)
    pids = [item["pid"] for item in records]

    if not pids:
        print("  [INFO] 未发现真实路径匹配 '%s' 的运行中进程" % proc_name)
        return True, None, {}

    pids_str = " ".join(pids)
    print("  [INFO] 发现进程 '%s'，共 %d 个实例 (PID: %s)，正在获取可执行路径..." % (
        proc_name, len(pids), pids_str))

    # 2. 从真实 PID 中提取可用于后续重启的路径。
    #    优先用当前文件仍存在的路径；如果都不存在，仍保留真实路径供后续上传后重启使用。
    real_paths = [item["exe_path"] for item in records]
    valid_paths = [item["exe_path"] for item in records if item["exe_exists"]]
    candidate_paths = valid_paths or real_paths

    exec_path = None
    if candidate_paths:
        for path in candidate_paths:
            if PREFERRED_EXEC_PATH_KEYWORD in path:
                exec_path = path
                print("  [INFO] 优先选中包含 '%s' 的可执行路径: %s" % (
                    PREFERRED_EXEC_PATH_KEYWORD, exec_path))
                break
        if not exec_path:
            exec_path = candidate_paths[0]

    if exec_path:
        if exec_path in valid_paths:
            print("  [INFO] 成功获取并验证可执行路径: %s" % exec_path)
        else:
            print("  [WARN] 已记录真实可执行路径，但当前文件不存在: %s" % exec_path)
    else:
        print("  [WARN] 遍历了所有 PID，均未能提取到真实可执行路径，将使用兜底路径")

    # 3. 精准击杀：SIGTERM → 等待确认 → 仍存活则 SIGKILL
    start_env = {}
    env_pid = None
    if exec_path:
        for item in records:
            if item["exe_path"] == exec_path:
                env_pid = item["pid"]
                break
    if env_pid is None and records:
        env_pid = records[0]["pid"]
    if env_pid is not None:
        start_env = _read_proc_start_env(ip, env_pid)
        if start_env:
            env_keys = ", ".join(sorted(start_env.keys()))
            print("  [INFO] 已记录原进程启动环境: %s" % env_keys)
        else:
            print("  [INFO] 未从原进程读取到桌面环境变量，将使用默认启动环境")

    k_code, k_out = run_ssh(ip, "kill %s" % pids_str)
    if k_code == 0:
        time.sleep(2)

    still_alive = find_pids(ip, proc_name)
    if still_alive:
        if k_code != 0:
            print("  [WARN] SIGTERM 发送失败: %s，尝试 kill -9" % k_out)
        else:
            print("  [WARN] SIGTERM 后进程仍在运行 (PID: %s)，发送 SIGKILL" % " ".join(still_alive))

        k9_code, k9_out = run_ssh(ip, "kill -9 %s" % " ".join(still_alive))
        if k9_code != 0:
            print("  [ERROR] kill -9 发送失败: %s" % k9_out)
            return False, exec_path, start_env

        time.sleep(1)
        still_alive2 = find_pids(ip, proc_name)
        if still_alive2:
            print("  [ERROR] kill -9 后进程仍然存在，请手动处理 (PID: %s)" % " ".join(still_alive2))
            return False, exec_path, start_env
    print("  [OK]  进程已终止（共 %d 个实例）" % len(pids))
    return True, exec_path, start_env


def kill_registered_processes(ip, registered_proc_entries, target_proc_name=""):
    """
    循环 pgm.txt 中登记的全部进程名逐个查杀。
    如果 target_proc_name 未登记，则为了兼容旧用法额外补充一次查杀。
    返回 (all_ok, proc_order, proc_exec_paths)。
    """
    target_proc_name = _ensure_text(target_proc_name).strip() if target_proc_name else ""

    proc_entries = []
    seen = set()
    for entry in registered_proc_entries:
        text_name = _ensure_text(entry.get("name", "")).strip()
        if not text_name or text_name in seen:
            continue
        seen.add(text_name)
        proc_entries.append({
            "name": text_name,
            "exec_path_hint": _ensure_text(entry.get("exec_path_hint", "")).strip(),
            "start_mode": _ensure_text(entry.get("start_mode", "")).strip(),
            "start_command": _ensure_text(entry.get("start_command", "")).strip(),
        })

    if target_proc_name and target_proc_name not in seen:
        print("  [WARN] pgm.txt 未登记目标进程 '%s'，本次额外补充查杀" % target_proc_name)
        proc_entries.append({
            "name": target_proc_name,
            "exec_path_hint": "",
            "start_mode": "",
            "start_command": "",
        })

    all_ok = True
    proc_exec_paths = {}
    proc_start_envs = {}

    for entry in proc_entries:
        name = entry["name"]
        print("  [PROC] 查杀登记进程: %s" % name)
        kill_ok, exec_path, start_env = do_kill(ip, name)
        if not kill_ok:
            all_ok = False
        if exec_path and name not in proc_exec_paths:
            proc_exec_paths[name] = exec_path
        if start_env and name not in proc_start_envs:
            proc_start_envs[name] = start_env

    return all_ok, proc_entries, proc_exec_paths, proc_start_envs


def start_registered_processes(ip, proc_entries, proc_exec_paths, proc_start_envs, default_start_mode):
    """
    按 pgm.txt 顺序逐个启动已经记录到真实路径的进程。
    没有记录到路径的进程跳过。
    """
    for entry in proc_entries:
        name = entry["name"]
        exec_path_hint = entry.get("exec_path_hint", "")
        exec_path = exec_path_hint or proc_exec_paths.get(name)
        start_env = proc_start_envs.get(name, {})
        effective_mode = entry.get("start_mode", "") or default_start_mode
        start_command = entry.get("start_command", "")

        if (effective_mode or "").lower().strip() in ("", "n", "no", "none"):
            print("  [INFO] 进程 '%s' 配置为不启动，跳过" % name)
            continue
        if not exec_path and not start_command:
            print("  [INFO] 未记录到进程 '%s' 的真实路径且未配置启动命令，跳过启动" % name)
            continue
        if exec_path_hint:
            print("  [INFO] 进程 '%s' 优先使用 pgm.txt 指定路径: %s" % (name, exec_path_hint))
        do_start(ip, exec_path, name, effective_mode, start_command=start_command, start_env=start_env)


def _build_start_payload(exec_path, start_command):
    """
    生成启动时的工作目录和实际命令。
    - 有 start_command 时优先用它
    - 否则直接执行记录到的真实可执行文件
    """
    work_dir = exec_path.rsplit("/", 1)[0] if exec_path and "/" in exec_path else "."

    if start_command:
        return work_dir, start_command, _shell_quote(start_command), "自定义命令"

    if exec_path:
        exec_name = posixpath.basename(exec_path)
        run_cmd = _shell_quote("./" + exec_name)
        return work_dir, run_cmd, run_cmd, "可执行文件"

    return ".", "", "", "未知"


# ──────────────────────────────────────────────
#  窗口移主屏：纯 Python 2.7/3，ctypes + libX11
#  通过 SSH 将脚本 base64 编码后发到远端执行，
#  自动从 xrandr 读主屏偏移，无需 xdotool。
# ──────────────────────────────────────────────

_MOVE_WIN_SCRIPT = """\
from __future__ import print_function
import ctypes, subprocess, sys, os, re, time

def get_primary_origin():
    try:
        out = subprocess.check_output(['xrandr'], stderr=open(os.devnull, 'wb'))
        if isinstance(out, bytes):
            out = out.decode('utf-8', 'replace')
        for line in out.splitlines():
            if 'connected primary' in line:
                m = re.search(r'[0-9]+x[0-9]+\\+([0-9]+)\\+([0-9]+)', line)
                if m:
                    return int(m.group(1)), int(m.group(2))
        for line in out.splitlines():
            if ' connected ' in line:
                m = re.search(r'[0-9]+x[0-9]+\\+([0-9]+)\\+([0-9]+)', line)
                if m:
                    return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 0, 0

def main():
    if len(sys.argv) < 3:
        return
    match_mode = sys.argv[1].lower()
    match_value = sys.argv[2]
    title_fallback = sys.argv[3].lower() if len(sys.argv) > 3 else ''
    pid_set = set()
    if match_mode == 'pid':
        for item in match_value.split(','):
            item = item.strip()
            if item.isdigit():
                pid_set.add(int(item))
    elif match_mode == 'title':
        title_fallback = match_value.lower()
    primary_x, primary_y = get_primary_origin()

    try:
        xlib = ctypes.cdll.LoadLibrary('libX11.so.6')
    except OSError:
        return

    xlib.XOpenDisplay.restype  = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XDefaultRootWindow.restype  = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    xlib.XQueryTree.restype  = ctypes.c_int
    xlib.XQueryTree.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
        ctypes.POINTER(ctypes.c_uint),
    ]
    xlib.XFetchName.restype  = ctypes.c_int
    xlib.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                  ctypes.POINTER(ctypes.c_char_p)]
    xlib.XInternAtom.restype = ctypes.c_ulong
    xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    xlib.XGetWindowProperty.restype = ctypes.c_int
    xlib.XGetWindowProperty.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.c_long, ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))
    ]
    xlib.XMoveWindow.restype  = ctypes.c_int
    xlib.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                   ctypes.c_int, ctypes.c_int]
    xlib.XFree.restype  = ctypes.c_int
    xlib.XFree.argtypes = [ctypes.c_void_p]
    xlib.XSync.restype  = ctypes.c_int
    xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]

    dpy = xlib.XOpenDisplay(None)
    if not dpy:
        return
    root = xlib.XDefaultRootWindow(dpy)
    atom_name = b'_NET_WM_PID' if sys.version_info[0] >= 3 else '_NET_WM_PID'
    atom_pid = xlib.XInternAtom(dpy, atom_name, 0)

    def iter_windows(win, depth=0):
        if depth > 20:
            return
        r_win = ctypes.c_ulong()
        p_win = ctypes.c_ulong()
        ch_p  = ctypes.POINTER(ctypes.c_ulong)()
        nch   = ctypes.c_uint(0)
        if not xlib.XQueryTree(dpy, win,
                                ctypes.byref(r_win), ctypes.byref(p_win),
                                ctypes.byref(ch_p),  ctypes.byref(nch)):
            return
        children = [ch_p[i] for i in range(nch.value)]
        if ch_p:
            xlib.XFree(ch_p)
        for child in children:
            yield child
            for w in iter_windows(child, depth + 1):
                yield w

    def fetch_name(win):
        np = ctypes.c_char_p()
        if xlib.XFetchName(dpy, win, ctypes.byref(np)) and np.value:
            v = np.value
            xlib.XFree(ctypes.cast(np, ctypes.c_void_p))
            if isinstance(v, bytes):
                v = v.decode('utf-8', 'replace')
            return v
        return ''

    def fetch_pid(win):
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop = ctypes.POINTER(ctypes.c_ubyte)()
        status = xlib.XGetWindowProperty(
            dpy, win, atom_pid, 0, 1, 0, 0,
            ctypes.byref(actual_type), ctypes.byref(actual_format),
            ctypes.byref(nitems), ctypes.byref(bytes_after),
            ctypes.byref(prop)
        )
        if status != 0 or not prop or nitems.value == 0:
            return None
        try:
            if actual_format.value == 32:
                return int(ctypes.cast(prop, ctypes.POINTER(ctypes.c_ulong))[0])
        finally:
            xlib.XFree(prop)
        return None

    def matches(win):
        title = fetch_name(win).lower()
        if pid_set:
            try:
                if fetch_pid(win) in pid_set:
                    return True
            except Exception:
                pass
        if title_fallback and title_fallback in title:
            return True
        return False

    # 重试最多 15 秒，等待窗口出现
    for _ in range(15):
        moved = 0
        for w in iter_windows(root):
            try:
                if matches(w):
                    xlib.XMoveWindow(dpy, w, primary_x, primary_y)
                    moved += 1
            except Exception:
                pass
        if moved:
            xlib.XSync(dpy, 0)
            break
        time.sleep(1)

main()
"""


def _move_windows_to_primary(ip, match_mode, match_value, start_env=None, title_fallback=""):
    """
    将 _MOVE_WIN_SCRIPT 通过 base64 编码后发到远端，用 python 执行。
    纯标准库，Python 2.7/3 均可，不依赖 xdotool/wmctrl 等外部工具。
    """
    import base64
    b64 = base64.b64encode(_to_bytes(_MOVE_WIN_SCRIPT))
    if isinstance(b64, bytes):
        b64 = b64.decode("ascii")
    env_prefix = _build_start_env_prefix(start_env)
    cmd = "%s; echo %s | base64 -d | python - %s %s %s 2>/dev/null" % (
        env_prefix,
        _shell_quote(b64),
        _shell_quote(match_mode),
        _shell_quote(match_value),
        _shell_quote(title_fallback),
    )
    run_ssh(ip, cmd)


def do_start(ip, exec_path, proc_name, start_mode, start_command="", start_env=None):
    """
    按照 start_mode 在远端重启进程。

    exec_path   : 可执行文件的绝对路径（从 /proc/PID/exe 读取或兜底路径）
    start_mode  :
      'd' / 'direct' — nohup 直接后台启动，无终端，适合守护进程
      't' / 'term'   — mate-terminal 终端会话启动，SSH 断开后仍存活
      'n' / ''       — 不启动
    start_command:
      非空时，优先执行这个远端 shell 命令；若已知 exec_path，则先 cd 到其所在目录再执行
    """
    m = start_mode.lower().strip()
    if m in ("", "n", "no", "none"):
        return

    if not exec_path and not start_command:
        print("  [ERROR] 无法确定可执行文件路径，跳过启动"
              "（进程从未运行过，且未指定兜底路径）")
        return

    work_dir, direct_cmd, term_cmd, cmd_kind = _build_start_payload(exec_path, start_command)
    if not direct_cmd:
        print("  [ERROR] 启动命令为空，跳过启动")
        return

    env_prefix = _build_start_env_prefix(start_env)

    if m in ("d", "direct"):
        launch_cmd = "%s; nohup setsid %s >/dev/null 2>&1 </dev/null &" % (
            env_prefix, direct_cmd)
        label = "直接启动 (%s) : cd %s && %s" % (cmd_kind, work_dir, direct_cmd)
        move_mode = "pid"
        move_value = ""
        move_fallback = proc_name.lower()
    elif m in ("t", "term"):
        term_title = "cpupdate_%s_%d" % (
            proc_name.replace("/", "_").replace(" ", "_"),
            int(time.time())
        )
        launch_cmd = "%s; nohup setsid mate-terminal --title=%s -e %s >/dev/null 2>&1 </dev/null &" % (
            env_prefix, _shell_quote(term_title), term_cmd)
        label = "终端启动 (%s) : cd %s && mate-terminal --title=%s -e %s" % (
            cmd_kind, work_dir, term_title, term_cmd)
        move_mode = "title"
        move_value = term_title
        move_fallback = term_title.lower()
    else:
        print("  [WARN] 未知启动模式 '%s'，跳过启动（有效值: d/direct/t/term/n）" % start_mode)
        return

    remote_cmd = "cd %s && %s" % (_shell_quote(work_dir), launch_cmd)
    print("  [INFO] 正在启动进程: %s" % label)
    s_code, s_out = run_ssh(ip, remote_cmd)
    if s_code != 0:
        print("  [ERROR] 启动失败: %s" % s_out)
    else:
        time.sleep(2)
        v_pids = find_pids(ip, proc_name)
        if not v_pids:
            time.sleep(2)
            v_pids = find_pids(ip, proc_name)
        if v_pids:
            print("  [OK]  进程已启动 (PID: %s)" % " ".join(v_pids))
            print("  [INFO] 正在将窗口移到主屏...")
            if move_mode == "pid":
                move_value = ",".join(v_pids)
            _move_windows_to_primary(ip, move_mode, move_value, start_env=start_env, title_fallback=move_fallback)
        else:
            print("  [WARN] 命令已执行，但未能确认进程存在，请手动检查")


# ──────────────────────────────────────────────
#  模式 0：查询文件是否存在
# ──────────────────────────────────────────────

def mode_check(ip_list, remote_path):
    results = []
    for ip in ip_list:
        print("  检查 %s ..." % ip)
        code, out = run_ssh(
            ip,
            "test -f %s && echo __EXISTS__ || echo __MISSING__" % _shell_quote(remote_path)
        )
        if "__EXISTS__" not in out and "__MISSING__" not in out:
            results.append((ip, "连接失败", "-"))
            continue
        exists = "__EXISTS__" in out
        if exists:
            _, stat_out = run_ssh(
                ip, "stat -c '%%s bytes | %%y' %s" % _shell_quote(remote_path))
            lines = [l for l in stat_out.splitlines() if l.strip()]
            detail = lines[0] if lines else "已存在"
        else:
            detail = "-"
        results.append((ip, "存在" if exists else "不存在", detail))

    if not results:
        print("  [WARN] 没有任何结果（IP 列表为空？）")
        return

    col1 = max(len(r[0]) for r in results) + 2
    col2 = 8
    col3 = max(len(r[2]) for r in results) + 2
    sep = "+" + "-" * (col1 + 2) + "+" + "-" * (col2 + 2) + "+" + "-" * (col3 + 2) + "+"
    fmt = "| %%-%ds | %%-%ds | %%-%ds |" % (col1, col2, col3)

    print("")
    print("  查询路径: %s" % remote_path)
    print("  " + sep)
    print("  " + fmt % ("IP 地址", "状态", "文件信息"))
    print("  " + sep)
    for ip, status, detail in results:
        print("  " + fmt % (ip, status, detail))
    print("  " + sep)
    print("  合计: %d 台存在 / %d 台不存在 / %d 台连接失败\n" % (
        sum(1 for r in results if r[1] == "存在"),
        sum(1 for r in results if r[1] == "不存在"),
        sum(1 for r in results if r[1] == "连接失败"),
    ))


# ──────────────────────────────────────────────
#  模式 1：直接上传覆盖
# ──────────────────────────────────────────────

def mode_upload(ip_list, remote_path, local_path):
    for ip in ip_list:
        print("\n[%s]" % ip)
        do_upload(ip, remote_path, local_path)


# ──────────────────────────────────────────────
#  模式 2：备份 + 上传覆盖
# ──────────────────────────────────────────────

def mode_backup_upload(ip_list, remote_path, local_path):
    for ip in ip_list:
        print("\n[%s]" % ip)
        if do_backup(ip, remote_path):
            do_upload(ip, remote_path, local_path)
        else:
            print("  [WARN] 备份失败，禁止上传: %s" % remote_path)


# ──────────────────────────────────────────────
#  模式 3：杀进程 + 备份 + 上传覆盖 [+ 重启]
# ──────────────────────────────────────────────

def mode_kill_backup_upload(ip_list, remote_path, local_path, proc_name, start_mode, registered_proc_entries):
    for ip in ip_list:
        print("\n[%s]" % ip)
        kill_ok, proc_entries, proc_exec_paths, proc_start_envs = kill_registered_processes(
            ip, registered_proc_entries, proc_name)
        if not kill_ok:
            print("  [ERROR] 停止进程失败，终止本机部署")
            continue
        # 兜底：进程未运行时用上传的文件路径（模式3上传的就是这个可执行文件）
        if proc_name and proc_name not in proc_exec_paths:
            proc_exec_paths[proc_name] = remote_path
            print("  [INFO] 进程未运行，启动路径使用上传目标: %s" % remote_path)
        if not do_backup(ip, remote_path):
            print("  [WARN] 备份失败，禁止上传: %s" % remote_path)
            continue
        ok = do_upload(ip, remote_path, local_path, make_exec=True)
        if ok:
            start_registered_processes(ip, proc_entries, proc_exec_paths, proc_start_envs, start_mode)


# ──────────────────────────────────────────────
#  公共辅助：单台主机目录文件备份 + 上传
# ──────────────────────────────────────────────

def _backup_and_upload_files(ip, local_files, local_dir, remote_dir):
    """
    对单台主机，将 local_dir 下 local_files 列表内的文件逐个备份+上传到 remote_dir。
    返回 True 表示全部成功，False 表示至少一个文件失败。
    """
    all_ok = True
    for rel_path in local_files:
        remote_file = _remote_file_path(remote_dir, rel_path)
        local_file  = _local_file_path(local_dir, rel_path)
        print("  ---- %s ----" % rel_path)
        if not do_backup(ip, remote_file):
            print("  [WARN] 备份失败，禁止上传: %s" % remote_file)
            all_ok = False
            continue
        ok = do_upload(ip, remote_file, local_file, make_exec=True)
        if not ok:
            all_ok = False
    return all_ok


# ──────────────────────────────────────────────
#  模式 4：杀进程 + 目录所有文件备份 + 上传覆盖 [+ 重启]
# ──────────────────────────────────────────────

def mode_kill_backup_upload_dir(ip_list, local_dir, remote_dir, proc_name, start_mode, registered_proc_entries):
    """
    本地 local_dir 下所有文件递归上传到远端 remote_dir，二者可以不同。
    每个文件：远端有则先备份，然后覆盖上传并设置可执行权限。
    全部文件处理完毕后按 start_mode 重启进程。
    """
    local_files = collect_local_files(local_dir)
    if local_files is None:
        return
    if not local_files:
        print("[ERROR] 本地目录下没有任何文件: %s" % local_dir)
        return

    print("  本地目录: %s" % local_dir)
    print("  远端目录: %s" % remote_dir)
    print("  待上传文件 (%d 个): %s" % (len(local_files), ", ".join(local_files)))

    for ip in ip_list:
        print("\n[%s]" % ip)
        # 1. 杀进程，同时拿到真实可执行路径
        kill_ok, proc_entries, proc_exec_paths, proc_start_envs = kill_registered_processes(
            ip, registered_proc_entries, proc_name)
        if not kill_ok:
            print("  [ERROR] 停止进程失败，终止本机部署")
            continue
        if proc_name and proc_name not in proc_exec_paths:
            fallback_path = remote_dir.rstrip("/") + "/" + proc_name
            proc_exec_paths[proc_name] = fallback_path
            print("  [INFO] 进程未运行，启动路径使用推断值: %s" % fallback_path)
        # 2. 逐文件备份 + 上传
        all_ok = _backup_and_upload_files(ip, local_files, local_dir, remote_dir)
        # 3. 重启进程
        if all_ok:
            start_registered_processes(ip, proc_entries, proc_exec_paths, proc_start_envs, start_mode)
        else:
            print("  [WARN] 部分文件上传失败，跳过启动进程")


# ──────────────────────────────────────────────
#  模式 5：检查进程，未运行才启动
# ──────────────────────────────────────────────

def mode_start_if_dead(ip_list, exec_path, proc_name, start_mode):
    """
    对每台机器：
      - 进程已在运行 → 打印提示，跳过
      - 进程未运行   → 先校验远端可执行文件是否存在，再按 start_mode 启动
    """
    for ip in ip_list:
        print("\n[%s]" % ip)
        pids = find_pids(ip, proc_name)
        if pids:
            print("  [SKIP] 进程 '%s' 已在运行 (PID: %s)，跳过启动" % (
                proc_name, " ".join(pids)))
        else:
            chk_code, _ = run_ssh(ip, "test -f %s" % _shell_quote(exec_path))
            if chk_code != 0:
                print("  [ERROR] 远端可执行文件不存在，跳过启动: %s" % exec_path)
                continue
            print("  [INFO] 进程 '%s' 未运行，准备启动..." % proc_name)
            do_start(ip, exec_path, proc_name, start_mode)


# ──────────────────────────────────────────────
#  模式 6：仅杀进程
# ──────────────────────────────────────────────

def mode_kill_only(ip_list, proc_name, registered_proc_entries):
    """
    对每台机器循环 pgm.txt 中登记的全部进程名逐个查杀。
    """
    for ip in ip_list:
        print("\n[%s]" % ip)
        kill_ok, _, _, _ = kill_registered_processes(ip, registered_proc_entries, proc_name)
        if not kill_ok:
            print("  [ERROR] 部分登记进程停止失败，请检查上方日志")


# ──────────────────────────────────────────────
#  模式 7：仅备份 + 上传文件（整个目录，不杀进程不启动）
# ──────────────────────────────────────────────

def mode_backup_upload_dir(ip_list, local_dir, remote_dir):
    """
    本地 local_dir 下所有文件递归上传到远端 remote_dir。
    每个文件：远端有则先备份，然后覆盖上传并设置可执行权限。
    不涉及进程的杀死与启动。
    """
    local_files = collect_local_files(local_dir)
    if local_files is None:
        return
    if not local_files:
        print("[ERROR] 本地目录下没有任何文件: %s" % local_dir)
        return

    print("  本地目录: %s" % local_dir)
    print("  远端目录: %s" % remote_dir)
    print("  待上传文件 (%d 个): %s" % (len(local_files), ", ".join(local_files)))

    for ip in ip_list:
        print("\n[%s]" % ip)
        all_ok = _backup_and_upload_files(ip, local_files, local_dir, remote_dir)
        if all_ok:
            print("  [OK]  所有文件备份并上传完成")
        else:
            print("  [WARN] 部分文件上传失败，请检查日志")


# ──────────────────────────────────────────────
#  主入口
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)

    argv = [_decode_cli_arg(arg) for arg in sys.argv]

    remote_path = argv[1]
    mode        = argv[2]

    if mode not in ("0", "1", "2", "3", "4", "5", "6", "7"):
        print("[ERROR] 操作模式必须为 0 / 1 / 2 / 3 / 4 / 5 / 6 / 7")
        print(USAGE)
        sys.exit(1)

    # ── 参数解析 ──────────────────────────────
    proc_name  = ""
    remote_dir = None
    start_mode = "n"
    registered_proc_entries = None

    if mode in ("3", "4", "5", "6"):
        # 模式 3/4/5/6 都需要进程名（参数3）
        if len(argv) < 4:
            print("[ERROR] 模式 %s 必须提供参数3（进程名）" % mode)
            print(USAGE)
            sys.exit(1)
        proc_name = argv[3]

    if mode == "4":
        # 模式4: 参数4=目标目录（必填），参数5=启动模式（选填）
        if len(argv) < 5:
            print("[ERROR] 模式 4 必须提供参数4（远端目标目录）")
            print(USAGE)
            sys.exit(1)
        remote_dir = argv[4]
        start_mode = argv[5] if len(argv) >= 6 else "n"

    elif mode == "3":
        # 模式3: 参数4=启动模式（选填）
        start_mode = argv[4] if len(argv) >= 5 else "n"

    elif mode == "5":
        # 模式5: 参数4=启动模式（必填，必须是 d 或 t）
        if len(argv) < 5:
            print("[ERROR] 模式 5 必须提供参数4（启动模式：d 或 t）")
            print(USAGE)
            sys.exit(1)
        start_mode = argv[4]
        if start_mode.lower() not in ("d", "direct", "t", "term"):
            print("[ERROR] 模式 5 的启动模式必须是 d/direct 或 t/term，不能为空或 n")
            print(USAGE)
            sys.exit(1)

    elif mode == "7":
        # 模式7: 参数3=远端目标目录（必填），无进程名、无启动模式
        if len(argv) < 4:
            print("[ERROR] 模式 7 必须提供参数3（远端目标目录）")
            print(USAGE)
            sys.exit(1)
        remote_dir = argv[3]
        proc_name  = ""   # 模式7不需要进程名

    # 路径整理
    local_path = remote_path
    local_dir  = remote_path.rstrip("/")
    if remote_dir is None:
        remote_dir = local_dir

    # ── 本地路径校验 ──────────────────────────
    if mode in ("1", "2", "3") and not os.path.isfile(local_path):
        print("[ERROR] 本地文件不存在: %s" % local_path)
        sys.exit(1)

    if mode in ("4", "7") and not os.path.isdir(local_dir):
        print("[ERROR] 本地目录不存在: %s" % local_dir)
        sys.exit(1)

    # ── 启动模式校验 ──────────────────────────
    valid_start = ("", "n", "no", "none", "d", "direct", "t", "term")
    if start_mode.lower() not in valid_start:
        print("[ERROR] 启动模式无效: '%s'（有效值: d/direct/t/term/n）" % start_mode)
        sys.exit(1)

    ip_list = read_ip_list(IP_FILE)
    if not ip_list:
        print("[ERROR] IP 列表为空，请检查 %s" % IP_FILE)
        sys.exit(1)

    if mode in ("3", "4", "6"):
        registered_proc_entries = read_pgm_list(PGM_FILE)

    # ── 启动前摘要输出 ────────────────────────
    start_mode_desc = {
        "": "不启动", "n": "不启动", "no": "不启动", "none": "不启动",
        "d": "直接后台启动 (nohup)", "direct": "直接后台启动 (nohup)",
        "t": "终端会话启动 (mate-terminal)", "term": "终端会话启动 (mate-terminal)",
    }
    mode_desc = {
        "0": "查询文件是否存在",
        "1": "直接上传覆盖",
        "2": "备份 + 上传覆盖",
        "3": "杀进程 + 备份 + 上传覆盖",
        "4": "杀进程 + 目录所有文件备份 + 上传覆盖",
        "5": "检查进程，未运行才启动",
        "6": "仅杀进程",
        "7": "仅备份 + 上传文件（整个目录）",
    }

    print("=" * 55)
    if mode == "5":
        print("可执行路径 : %s" % remote_path)
    elif mode == "6":
        print("（参数1不使用）")
    else:
        print("远端路径   : %s" % remote_path)
    print("操作模式   : [%s] %s" % (mode, mode_desc[mode]))
    print("主机数量   : %d" % len(ip_list))
    if mode in ("3", "4", "5", "6"):
        print("进程名称   : %s" % proc_name)
    if mode in ("3", "4", "6"):
        print("登记文件   : %s (%d 个)" % (PGM_FILE, len(registered_proc_entries)))
    if mode in ("3", "4", "5"):
        print("启动模式   : %s" % start_mode_desc.get(start_mode.lower(), start_mode))
    if mode in ("4", "7"):
        print("本地目录   : %s" % local_dir)
        print("远端目录   : %s" % remote_dir)
    print("=" * 55)

    try:
        if   mode == "0": mode_check(ip_list, remote_path)
        elif mode == "1": mode_upload(ip_list, remote_path, local_path)
        elif mode == "2": mode_backup_upload(ip_list, remote_path, local_path)
        elif mode == "3": mode_kill_backup_upload(
            ip_list, remote_path, local_path, proc_name, start_mode, registered_proc_entries)
        elif mode == "4": mode_kill_backup_upload_dir(
            ip_list, local_dir, remote_dir, proc_name, start_mode, registered_proc_entries)
        elif mode == "5": mode_start_if_dead(
            ip_list, remote_path, proc_name, start_mode)
        elif mode == "6": mode_kill_only(ip_list, proc_name, registered_proc_entries)
        elif mode == "7": mode_backup_upload_dir(ip_list, local_dir, remote_dir)
    finally:
        _cleanup_askpass()

    print("\n[INFO] 全部处理完毕。")


if __name__ == "__main__":
    main()
