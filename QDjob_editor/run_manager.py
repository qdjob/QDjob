"""
运行管理器：统一查找并启动 QDjob 核心程序，以及日志读取。

设计要点（保证「打包版 / 容器版」同一套代码）：
- 就近查找 QDjob 可执行文件：当前程序所在目录 -> 本模块目录 -> 工作目录 -> PATH
- 执行时以工作目录为 cwd，使 QDjob 读写同一份 config.json / cookies / logs
"""

import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

import web_config as wc

SYSTEM = platform.system()
RUN_STATE_FILE = ".qdjob_run.json"
_ACTIVE_PROC = None
_ACTIVE_LOCK = threading.Lock()


def _candidate_dirs():
    dirs = []
    try:
        dirs.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    except Exception:  # noqa: BLE001
        pass
    dirs.append(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(wc.get_workdir())
    dirs.append(os.getcwd())
    # 去重保序
    seen = set()
    result = []
    for d in dirs:
        if d and d not in seen:
            seen.add(d)
            result.append(d)
    return result


def _candidate_names():
    if SYSTEM == "Windows":
        return ["QDjob.exe", "QDjob_windows.exe"]
    return ["QDjob", "QDjob_linux"]


def find_qdjob_executable():
    """返回 QDjob 可执行文件的绝对路径；找不到返回 None。"""
    names = _candidate_names()
    for directory in _candidate_dirs():
        for name in names:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return path
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _source_main_candidates():
    """源码运行时的 QDjob/main.py 候选路径。"""
    dirs = []
    dirs.extend(_candidate_dirs())
    wd = wc.get_workdir()
    dirs.append(os.path.dirname(wd))
    dirs.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "QDjob"))
    candidates = []
    override = os.environ.get("QDJOB_SOURCE_MAIN", "").strip()
    if override:
        candidates.append(override)
    for directory in dirs:
        if not directory:
            continue
        candidates.append(os.path.join(directory, "QDjob", "main.py"))
        candidates.append(os.path.join(directory, "main.py"))
    seen = set()
    result = []
    for path in candidates:
        p = os.path.abspath(path)
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def is_compiled():
    """判断当前是否为打包后运行（Nuitka / PyInstaller）。"""
    try:
        import __main__
        if getattr(__main__, "__compiled__", False):
            return True
    except Exception:  # noqa: BLE001
        pass
    return bool(getattr(sys, "frozen", False))


# ==================== 上一次运行进程清理（仅打包版启用）====================
def _state_path():
    return os.path.join(wc.get_workdir(), RUN_STATE_FILE)


def _append_run_log(text):
    """把进程管理日志追加到 logs/manual_run.log，失败时静默。"""
    try:
        wc.ensure_dirs()
        with open(os.path.join(wc.logs_dir(), "manual_run.log"), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
    except OSError:
        pass


def _read_state():
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(pid, exe):
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump({"pid": int(pid), "exe": os.path.abspath(exe), "started": time.time()}, f)
    except OSError:
        pass


def _clear_state(pid=None):
    """删除 PID 状态文件；指定 pid 时仅在匹配时删除，避免误删新进程状态。"""
    state = _read_state()
    if pid is not None and state.get("pid") not in (None, pid):
        return
    try:
        os.remove(_state_path())
    except OSError:
        pass


def _windows_process_path(pid):
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
            return None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return None


def _process_path(pid):
    if SYSTEM == "Windows":
        return _windows_process_path(pid)
    try:
        return os.readlink(f"/proc/{int(pid)}/exe")
    except OSError:
        return None


def _same_path(a, b):
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except (OSError, TypeError):
        return False


def _terminate_process(pid, expected_exe):
    """仅当 PID 对应可执行文件与 expected_exe 一致时才终止，避免误杀其他程序。"""
    if not pid or not expected_exe:
        return False
    actual_exe = _process_path(pid)
    if not actual_exe or not _same_path(actual_exe, expected_exe):
        return False

    _append_run_log(f"检测到上一次 QDjob 仍在运行（PID {pid}），正在终止")
    try:
        if SYSTEM == "Windows":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=creationflags, timeout=10,
            )
            return result.returncode == 0
        os.kill(pid, signal.SIGTERM)
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return True
            time.sleep(0.2)
        os.kill(pid, signal.SIGKILL)
        return True
    except Exception as e:  # noqa: BLE001
        _append_run_log(f"终止上一次 QDjob 失败（PID {pid}）: {e}")
        return False


def _is_source_command(cmd):
    if not cmd:
        return True
    name = os.path.basename(cmd[0]).lower()
    return name in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}


def _terminate_previous_qdjob(cmd):
    """
    打包版启动新任务前，先终止上一次仍在运行的 QDjob。
    源码运行（python main.py）不做此处理，避免误杀其他 Python 脚本。
    """
    global _ACTIVE_PROC
    if not is_compiled() or _is_source_command(cmd):
        return

    expected_exe = os.path.abspath(cmd[0])
    with _ACTIVE_LOCK:
        proc = _ACTIVE_PROC
        if proc is not None and proc.poll() is None:
            if not _terminate_process(proc.pid, expected_exe):
                try:
                    proc.kill()
                except OSError:
                    pass

        state = _read_state()
        state_pid = state.get("pid")
        if state_pid and not (proc is not None and state_pid == proc.pid):
            _terminate_process(state_pid, state.get("exe") or expected_exe)

        _ACTIVE_PROC = None
        _clear_state()


def _remember_process(proc, cmd):
    global _ACTIVE_PROC
    with _ACTIVE_LOCK:
        _ACTIVE_PROC = proc
    _write_state(proc.pid, cmd[0])


def _watch_process(proc):
    """后台等待非阻塞启动的进程结束，并清理 PID 状态文件。"""
    try:
        proc.wait()
    finally:
        _clear_state(proc.pid)


def find_qdjob_command():
    """
    返回启动 QDjob 的命令列表（list[str]），找不到返回 None。
    - 打包环境：优先同目录 QDjob 可执行文件
    - 源码环境：回退到 `python QDjob/main.py`
    """
    exe = find_qdjob_executable()
    if exe:
        return [exe]
    if not is_compiled():
        for main_py in _source_main_candidates():
            if os.path.isfile(main_py):
                return [sys.executable, main_py]
    return None


def describe_qdjob_command(cmd=None):
    """把命令列表转换为可展示的字符串。"""
    cmd = cmd if cmd is not None else find_qdjob_command()
    if not cmd:
        return None
    return " ".join(f'"{c}"' if " " in c else c for c in cmd)


def run_qdjob():
    """以工作目录为 cwd 启动 QDjob，输出追加到 logs/manual_run.log。"""
    cmd = find_qdjob_command()
    if not cmd:
        return {
            "ok": False,
            "message": "未找到 QDjob（可执行文件或源码），请将 QDjob 与编辑器放置于同一目录",
        }
    wc.ensure_dirs()
    log_file = os.path.join(wc.logs_dir(), "manual_run.log")
    header = (
        f"\n===== [{time.strftime('%Y-%m-%d %H:%M:%S')}] "
        f"手动执行: {os.path.basename(cmd[-1])} =====\n"
    )
    try:
        _terminate_previous_qdjob(cmd)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(header)
        creationflags = 0
        if SYSTEM == "Windows":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with open(log_file, "a", encoding="utf-8") as out:
            proc = subprocess.Popen(
                cmd,
                cwd=wc.get_workdir(),
                stdout=out,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        _remember_process(proc, cmd)
        threading.Thread(
            target=_watch_process, args=(proc,), daemon=True, name=f"qdjob-watch-{proc.pid}"
        ).start()
        return {"ok": True, "message": "已启动 QDjob", "data": {"pid": proc.pid}}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"启动 QDjob 失败: {e}"}


def run_qdjob_blocking(src="scheduled"):
    """阻塞式执行 QDjob（供进程内调度器使用），返回 (ok, message)。"""
    cmd = find_qdjob_command()
    if not cmd:
        return False, "未找到 QDjob"
    wc.ensure_dirs()
    log_file = os.path.join(wc.logs_dir(), "manual_run.log")
    try:
        _terminate_previous_qdjob(cmd)
        creationflags = 0
        if SYSTEM == "Windows":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with open(log_file, "a", encoding="utf-8") as out:
            out.write(f"\n===== [{time.strftime('%Y-%m-%d %H:%M:%S')}] {src} 执行 =====\n")
            out.flush()
            proc = subprocess.Popen(
                cmd, cwd=wc.get_workdir(), stdout=out, stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            _remember_process(proc, cmd)
            try:
                code = proc.wait()
            finally:
                _clear_state(proc.pid)
        return code == 0, f"退出码 {code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


# ==================== 日志 ====================
# 日志文件名形如：login.log、login.log.2026-09-23（末尾为该日志对应日期）
_LOG_NAME_RE = re.compile(r'^[A-Za-z0-9_\-]+\.log(?:\.\d{4}-\d{2}-\d{2})?$')
_LOG_DATE_RE = re.compile(r'\.log\.(\d{4}-\d{2}-\d{2})$')


def _safe_log_path(filename):
    """校验并返回日志文件路径（仅允许 logs 目录下的普通日志文件名）。"""
    if not filename:
        return None
    base = os.path.basename(filename)
    if base != filename or not _LOG_NAME_RE.match(base):
        return None
    path = os.path.join(wc.logs_dir(), base)
    if os.path.isfile(path):
        return path
    return None


def _describe_log(name, stat):
    """解析日志文件名，返回展示信息。"""
    date = None
    m = _LOG_DATE_RE.search(name)
    if m:
        date = m.group(1)
        base = name[: m.start()]
    else:
        base = name
    if date:
        label = f"{base}（{date}）"
    else:
        label = f"{base}（今天）"
    return {
        "name": name,
        "base": base,
        "date": date,
        "is_current": date is None,
        "label": label,
        "size": stat.st_size,
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
    }


def list_logs():
    """列出 logs 目录下所有日志（含轮转文件），当前日志优先，其余按日期倒序。"""
    result = []
    logs_dir = wc.logs_dir()
    if not os.path.isdir(logs_dir):
        return result
    for name in os.listdir(logs_dir):
        if not _LOG_NAME_RE.match(name):
            continue
        path = os.path.join(logs_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            result.append(_describe_log(name, os.stat(path)))
        except OSError:
            continue
    # 排序：当前日志优先；其余按 base 与日期倒序
    result.sort(key=lambda x: (x["base"], x["date"] or ""), reverse=True)
    result.sort(key=lambda x: 0 if x["is_current"] else 1)
    return result


_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def tail_log(filename, lines=300, level=None):
    """读取日志末尾若干行（支持轮转文件），可选按级别过滤。"""
    path = _safe_log_path(filename)
    if not path:
        return {"ok": False, "message": f"日志文件不存在: {filename}"}
    try:
        lines = max(1, min(int(lines), 5000))
    except (ValueError, TypeError):
        lines = 300
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except OSError as e:
        return {"ok": False, "message": f"读取日志失败: {e}"}
    selected = all_lines[-lines:]
    if level and level.upper() in _LEVELS:
        level = level.upper()
        selected = [ln for ln in selected if f" - {level} - " in ln]
    return {"ok": True, "message": "", "data": "".join(selected)}
