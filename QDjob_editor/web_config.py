"""
WebUI 存储层。

负责 config.json / cookies / 设备信息文件的读写，提供：
- 统一的工作目录（workdir）解析（默认取当前工作目录，可用环境变量 QDJOB_WORKDIR 覆盖）
- 原子写入 + 线程锁，避免并发写坏文件
- 与 GUI 完全一致的常量与数据校验规则

注意：本模块不依赖 tkinter，可被 WebUI、脚本或打包后的二进制复用。
"""

import json
import os
import re
import threading
import tempfile

# ==================== 常量（与 GUI.py 保持一致）====================
MAX_USERS = 3

# 任务名称（顺序与 GUI 保持一致）
TASK_NAMES = [
    "签到任务",
    "激励碎片任务",
    "章节卡任务",
    "广告加点任务",
    "天降福利任务",
    "游戏中心任务",
    "每日抽奖任务",
    "每周自动兑换章节卡",
    "章节卡信息推送",
    "阅读时长上报",
]

# 推送服务类型
PUSH_SERVICE_TYPES = ["feishu", "serverchan", "qiwei", "pushplus"]

# 默认 cookies 模板（与 GUI.ConfigEditor.DEFAULT_COOKIES_TEMPLATE 一致）
DEFAULT_COOKIES_TEMPLATE = {
    "appId": "",
    "areaId": "",
    "lang": "",
    "mode": "",
    "bar": "",
    "qidth": "",
    "qid": "",
    "ywkey": "",
    "ywguid": "",
    "cmfuToken": "",
    "QDInfo": "",
}

# 用户名规则：2-20 位，中文/字母/数字/下划线
_USERNAME_RE = re.compile(r'^[\u4e00-\u9fa5a-zA-Z0-9_]{2,20}$')

# ==================== 工作目录 ====================
_WORKDIR = None
_LOCK = threading.RLock()


def set_workdir(path):
    """设置工作目录（config.json / cookies / logs 所在目录）。"""
    global _WORKDIR
    with _LOCK:
        _WORKDIR = os.path.abspath(path)


def get_workdir():
    """获取工作目录。优先显式设置，其次环境变量 QDJOB_WORKDIR，最后当前目录。"""
    global _WORKDIR
    with _LOCK:
        if _WORKDIR:
            return _WORKDIR
        _WORKDIR = os.path.abspath(os.environ.get("QDJOB_WORKDIR") or os.getcwd())
        return _WORKDIR


def _p(*parts):
    return os.path.join(get_workdir(), *parts)


def config_path():
    return _p("config.json")


def cookies_dir():
    return _p("cookies")


def logs_dir():
    return _p("logs")


def cookies_path_for(username):
    """用户的 cookies 文件绝对路径（统一放在 cookies/<username>.json）。"""
    return os.path.join(cookies_dir(), f"{username}.json")


def device_path_for(username):
    """用户的设备信息文件绝对路径（login_phone_<username>.json）。"""
    return _p(f"login_phone_{username}.json")


def ensure_dirs():
    for d in (cookies_dir(), logs_dir()):
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)


def resolve_path(path):
    """把 config 中的相对路径解析为基于工作目录的绝对路径。"""
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return _p(path)


# ==================== 原子写入 ====================
def _atomic_write_json(path, data):
    """原子写 JSON：先写临时文件再替换，避免写一半损坏。"""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return default
        return json.loads(content)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError):
        return default


# ==================== config.json ====================
DEFAULT_CONFIG = {
    "default_user_agent": "",
    "log_level": "INFO",
    "log_retention_days": 7,
    "retry_attempts": 3,
    "users": [],
}


def load_config():
    """加载 config.json；不存在时返回默认结构（不写盘）。"""
    with _LOCK:
        cfg = _read_json(config_path(), None)
        if not isinstance(cfg, dict):
            cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        cfg.setdefault("users", [])
        if not isinstance(cfg["users"], list):
            cfg["users"] = []
        # 兼容旧配置：为每个用户补齐字段
        for user in cfg["users"]:
            if isinstance(user, dict):
                user.setdefault("user_agent", "")
                user.setdefault("ibex", "")
                user.setdefault("usertype", "captcha")
                user.setdefault("tokenid", "")
                user.setdefault("tasks", {t: True for t in TASK_NAMES})
                # 兼容旧配置：已存在的 tasks 字典也补齐新增任务（默认开启）
                if isinstance(user.get("tasks"), dict):
                    for task_name in TASK_NAMES:
                        user["tasks"].setdefault(task_name, True)
                user.setdefault("push_services", [])
                user.setdefault("cookies_refresh_interval_days", 20)
                user.setdefault("last_cookies_refresh_time", "")
        return cfg


def save_config(cfg):
    """保存 config.json（原子写入）。"""
    with _LOCK:
        _atomic_write_json(config_path(), cfg)


def get_user(cfg, username):
    for user in cfg.get("users", []):
        if isinstance(user, dict) and user.get("username") == username:
            return user
    return None


def default_tasks():
    return {task: True for task in TASK_NAMES}


def validate_username(username):
    """返回 (ok, message)，与 GUI 校验规则一致。"""
    if not username:
        return False, "用户名不能为空"
    if not _USERNAME_RE.match(username):
        return False, "用户名格式错误！要求：2-20 个字符，仅支持中文、字母、数字和下划线"
    return True, ""


# ==================== cookies ====================
def load_cookies(username):
    """读取用户 cookies；返回 dict 或 None。"""
    with _LOCK:
        data = _read_json(cookies_path_for(username), None)
        return data if isinstance(data, dict) else None


def cookies_status(username):
    """返回 cookies 状态文本：账号未配置 / 账号已配置 / 格式错误。"""
    path = cookies_path_for(username)
    if not os.path.exists(path):
        return "账号未配置"
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return "读取失败"
        try:
            data = json.loads(content) if content.strip() else {}
        except json.JSONDecodeError:
            return "格式错误"
        if isinstance(data, dict) and all(
            (not isinstance(v, str)) or v.strip() == "" for v in data.values()
        ):
            return "账号未配置"
        return "账号已配置"


def save_cookies(username, data):
    """保存用户 cookies。"""
    with _LOCK:
        ensure_dirs()
        _atomic_write_json(cookies_path_for(username), data)


def delete_cookies(username):
    path = cookies_path_for(username)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


# ==================== 设备信息 ====================
def load_device(username):
    with _LOCK:
        data = _read_json(device_path_for(username), None)
        return data if isinstance(data, dict) else None


def save_device(username, data):
    with _LOCK:
        _atomic_write_json(device_path_for(username), data)


def rename_user_artifacts(old_username, new_username):
    """修改用户名时同步重命名 cookies 与设备信息文件。"""
    with _LOCK:
        old_cookies = cookies_path_for(old_username)
        new_cookies = cookies_path_for(new_username)
        if os.path.exists(old_cookies) and old_cookies != new_cookies:
            os.makedirs(cookies_dir(), exist_ok=True)
            os.replace(old_cookies, new_cookies)

        old_device = device_path_for(old_username)
        new_device = device_path_for(new_username)
        if os.path.exists(old_device) and old_device != new_device:
            os.replace(old_device, new_device)
