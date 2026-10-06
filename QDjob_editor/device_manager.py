"""
真实设备数据管理。

- 设备档案保存在工作目录 `devices.json`，可添加多组、自定义命名
- 设备信息与软件版本分离：设备只存硬件/指纹，版本另存 `versions.json`
- 支持从抓包 curl / HAR 文件解析设备参数（解析 ibex 得到真实设备指纹）
- 登录时由 `compose_login_phone()` 把「设备 + 版本」合成为 Login 所需的字典

设备字段说明（对应 Login.init_device_info）：
    brand / model / board / cpu_abi / device_name   -> phone_data
    android_version / build_id                       -> 系统信息
    resolution {width,height}                        -> 分辨率
    qid / qidth                                      -> 设备ID
    phone_security / phone_security_over             -> 设备指纹(qid_36 / qid_36_over)
    ibex_plain                                       -> ibex 明文模板（{TS} 为时间戳占位）
    android_id / jpush_id                            -> 可选
"""

import base64
import gzip
import json
import os
import re
from urllib.parse import parse_qsl, urlsplit

import web_config as wc

DEVICES_FILE = "devices.json"
VERSIONS_FILE = "versions.json"

# 登录所需的最小字段（缺失会给出告警）
REQUIRED_FIELDS = ["brand", "model", "qid", "phone_security"]

DEFAULT_RESOLUTION = {"width": 1080, "height": 2400}
DEFAULT_ANDROID_VERSION = 12
DEFAULT_SDKVERSION = "401"


# ==================== 设备档案存储 ====================
def devices_path():
    return os.path.join(wc.get_workdir(), DEVICES_FILE)


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return default
        return json.loads(content)
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path, data):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_devices():
    data = _read_json(devices_path(), {"devices": []})
    if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
        return []
    return data["devices"]


def save_devices(devices):
    _write_json(devices_path(), {"devices": devices})


def get_device(name):
    for d in load_devices():
        if d.get("name") == name:
            return d
    return None


def upsert_device(name, device, note="", source="manual", version=None):
    """新增或更新设备档案（可附带解析到的软件版本）。返回 (ok, message)。"""
    name = (name or "").strip()
    if not name:
        return False, "设备名称不能为空"
    if len(name) > 40:
        return False, "设备名称过长（最多 40 字符）"
    devices = load_devices()
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    version = _normalize_version(version) if isinstance(version, dict) else None
    existing = get_device(name)
    if existing:
        existing["device"] = device
        existing["note"] = note
        existing["source"] = source
        existing["version"] = version
        existing["updated"] = now
    else:
        devices.append({
            "name": name,
            "note": note,
            "source": source,
            "version": version,
            "created": now,
            "updated": now,
            "device": device,
        })
    save_devices(devices)
    return True, f"设备「{name}」已保存"


def delete_device(name):
    devices = load_devices()
    new = [d for d in devices if d.get("name") != name]
    if len(new) == len(devices):
        return False, f"设备「{name}」不存在"
    save_devices(new)
    return True, f"设备「{name}」已删除"


# ==================== 版本表 ====================
def _versions_candidates():
    candidates = [os.path.join(os.path.dirname(os.path.abspath(__file__)), VERSIONS_FILE)]
    try:
        import sys
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), VERSIONS_FILE))
    except Exception:  # noqa: BLE001
        pass
    candidates.append(os.path.join(wc.get_workdir(), VERSIONS_FILE))
    return candidates


def user_versions_path():
    return os.path.join(wc.get_workdir(), VERSIONS_FILE)


def _normalize_version(v):
    if not isinstance(v, dict):
        return None
    version = str(v.get("version", "")).strip()
    versioncode = str(v.get("versioncode", "")).strip()
    sdkversion = str(v.get("sdkversion", DEFAULT_SDKVERSION)).strip() or DEFAULT_SDKVERSION
    if not version or not versioncode:
        return None
    return {"version": version, "versioncode": versioncode, "sdkversion": sdkversion}


def load_versions():
    """合并读取版本表：内置 versions.json + 工作目录 versions.json（后者覆盖/追加）。"""
    merged = {}
    order = []
    for path in _versions_candidates():
        data = _read_json(path, None)
        if not isinstance(data, dict):
            continue
        for item in data.get("versions", []) or []:
            v = _normalize_version(item)
            if not v:
                continue
            key = (v["version"], v["versioncode"])
            if key not in merged:
                order.append(key)
            merged[key] = v
    return [merged[k] for k in order]


def save_user_versions(versions):
    _write_json(user_versions_path(), {"versions": versions})


def read_user_versions():
    data = _read_json(user_versions_path(), {"versions": []})
    if isinstance(data, dict) and isinstance(data.get("versions"), list):
        return data["versions"]
    return []


def normalize_version(entry):
    """公开接口：规范化单个版本条目，非法返回 None。"""
    return _normalize_version(entry)


# ==================== 抓包解析 ====================
_PAIR_RE = re.compile(r"""['"]([A-Za-z0-9_\-]+)=([^'"]*)['"]""", re.S)
_OSVER_RE = re.compile(r'Android(\d+)_([\d.]+)_(\d+)')
_WS_RE = re.compile(r'\s+')
# ibex 明文中的 cpu_abi 特征段（如 arm64-v8a / armeabi-v7a / x86_64）
_CPUABI_RE = re.compile(r'^(?:arme?abi|arm64|x86_64|x86|mips64|mips)(?:[-_v0-9a-z]+)?$', re.I)
_QID_RE = re.compile(r'^[0-9a-fA-F]{16,}$')


def _extract_pairs(text):
    """从 curl 文本提取 `key=value` 参数（兼容 --data-urlencode / -d，单双引号）。"""
    pairs = {}
    for k, v in _PAIR_RE.findall(text or ""):
        v = v.strip()
        if k in ("ibex", "signature", "password", "QDSign"):
            v = _WS_RE.sub("", v)  # base64 可能被换行/空格打断
        pairs[k] = v
    return pairs


# curl 令牌解析：-H/-A/-b 头部与 -d/--data* 请求体（兼容单双引号与 --flag=value）
_CURL_URL_RE = re.compile(r'https?://[^\s\'"<>]+')
_CURL_FLAG_RE = re.compile(
    r'''(?<![\w-])(--data(?:-raw|-binary|-urlencode)?|-d|-H|--header|-A|--user-agent|-b|--cookie)'''
    r'''\s*(?:=\s*)?("([^"]*)"|'([^']*)')'''
)
_CURL_HEADERS = ("-H", "--header")
_CURL_UA = ("-A", "--user-agent")
_CURL_COOKIE = ("-b", "--cookie")


def _parse_curl_tokens(text):
    """从 curl 命令提取 (url, headers, datas, flag_spans)：headers 为 (小写名, 值) 列表。"""
    url, headers, datas = "", [], []
    flag_spans = []
    for m in _CURL_FLAG_RE.finditer(text):
        flag_spans.append((m.start(), m.end()))
        flag = m.group(1)
        value = m.group(3) if m.group(3) is not None else m.group(4)
        if flag in _CURL_HEADERS:
            name, sep, val = value.partition(":")
            if sep:
                headers.append((name.strip().lower(), val.strip()))
        elif flag in _CURL_UA:
            headers.append(("user-agent", value.strip()))
        elif flag in _CURL_COOKIE:
            headers.append(("cookie", value.strip()))
        else:
            datas.append(value)
    # 主 URL：取第一个不在任何 flag 值内的 http(s) 链接（避免误取 Referer 等）
    for m in _CURL_URL_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in flag_spans):
            url = m.group(0)
            break
    return url, headers, datas, flag_spans


def _collect_data_text(pairs, data):
    """把一段请求体文本（form / JSON）中的白名单参数并入 pairs。"""
    data = (data or "").strip()
    if not data:
        return
    if data.startswith("{"):
        try:
            body = json.loads(data)
        except json.JSONDecodeError:
            body = None
        if isinstance(body, dict):
            for k, v in body.items():
                if isinstance(v, (str, int, float)):
                    _collect_param(pairs, str(k), str(v))
            return
    for k, v in parse_qsl(data, keep_blank_values=True):
        _collect_param(pairs, k, v)


def parse_ibex_plain(plain):
    """从 ibex 明文提取设备字段，并生成带 {TS} 占位符的模板。

    兼容新版明文在末尾追加字段的情况：设备块相对位置不变（cpu_abi 之后隔
    2 段是 qid、再往后是 qidth），因此优先以 cpu_abi 特征段锚定设备块；
    锚定失败（特征缺失或 qid/qidth 校验不过）时回退旧的固定位置解析。
    """
    out = {}
    if not isinstance(plain, str) or not plain.startswith("1|"):
        return out
    parts = plain.split("|")
    if len(parts) < 16:
        return out

    ts = parts[1][:13]
    if ts.isdigit():
        # 把时间戳替换为占位符，保证登录时逐字节还原
        out["ibex_plain"] = plain[:2] + "{TS}" + plain[2 + 13:]

    # 以 cpu_abi 特征段锚定：model 在其前 5 段，qid/qidth 在其后 3/4 段
    anchor = None
    for i in range(len(parts) - 1, 6, -1):
        if (_CPUABI_RE.match(parts[i]) and i + 4 < len(parts)
                and _QID_RE.match(parts[i + 3]) and _QID_RE.match(parts[i + 4])):
            anchor = i
            break

    if anchor is not None:
        model_i = anchor - 5
        out["model"] = re.split(r"\s*\(", parts[model_i], 1)[0].strip()
        out["brand"] = parts[anchor - 4]
        out["board"] = parts[anchor - 3]
        out["build_id"] = parts[anchor - 1]
        out["cpu_abi"] = parts[anchor]
        out["qid"] = parts[anchor + 3]
        out["qidth"] = parts[anchor + 4]
        # model 之前的中段即设备指纹 phone_security（97 字符 / 46 段）
        ps = "|".join([parts[1][13:]] + parts[2:model_i] + [""])
        out["phone_security"] = ps
        out["phone_security_over"] = ps
        return out

    # 回退：旧版固定位置（设备块紧贴明文末尾）
    out["model"] = re.split(r"\s*\(", parts[-12], 1)[0].strip()
    out["brand"] = parts[-11]
    out["board"] = parts[-10]
    out["build_id"] = parts[-8]
    out["cpu_abi"] = parts[-7]
    out["qid"] = parts[-4]
    out["qidth"] = parts[-3]
    ps = "|".join([parts[1][13:]] + parts[2:-12] + [""])
    out["phone_security"] = ps
    out["phone_security_over"] = ps
    return out


def _device_from_pairs(pairs):
    """从参数字典提取设备字段，返回 (device, app_version, warnings)。"""
    dev = {}
    app_version = {}
    warnings = []
    if not pairs:
        return dev, app_version, warnings

    if pairs.get("devicename"):
        dev["device_name"] = pairs["devicename"]

    if pairs.get("devicetype"):
        dt = pairs["devicetype"]
        if "_" in dt:
            b, m = dt.split("_", 1)
            dev.setdefault("brand", b)
            dev.setdefault("model", m)
        else:
            dev.setdefault("model", dt)

    # 软件版本（与设备无关，单独返回）
    if pairs.get("osversion"):
        m = _OSVER_RE.search(pairs["osversion"])
        if m:
            dev["android_version"] = int(m.group(1))
            app_version["version"] = m.group(2)
            app_version["versioncode"] = m.group(3)
    if pairs.get("version"):
        app_version["versioncode"] = pairs["version"]
    if pairs.get("sdkversion"):
        app_version["sdkversion"] = pairs["sdkversion"]

    if pairs.get("ibex"):
        try:
            from enctrypt_qidian import decode_ibex
            plain = decode_ibex(_WS_RE.sub("", pairs["ibex"]))
            if isinstance(plain, (bytes, bytearray)):
                plain = plain.decode("utf-8", "replace")
            info = parse_ibex_plain(plain)
            if not info:
                warnings.append("ibex 明文结构无法识别（可能是未知格式）")
            for k, v in info.items():
                if v:
                    dev[k] = v
        except Exception as e:  # noqa: BLE001
            warnings.append(f"ibex 解析失败: {e}")
    else:
        warnings.append("未填写 ibex，无法获取真实设备指纹")

    if not dev.get("qid") and pairs.get("signature"):
        try:
            from enctrypt_qidian import decode_signature
            sig = str(decode_signature(_WS_RE.sub("", pairs["signature"])))
            qid = sig.split("|")[0].strip()
            if qid:
                dev["qid"] = qid
        except Exception as e:  # noqa: BLE001
            warnings.append(f"signature 解析失败: {e}")

    dev = normalize_device(dev)
    for field in REQUIRED_FIELDS:
        if not dev.get(field):
            warnings.append(f"未能提取字段: {field}（可在表单中手动补充）")
    return dev, app_version, warnings


def parse_curl(text):
    """解析抓包 curl，返回 (ok, message, result)。

    支持 bash / Windows cmd（^ 续行）两种风格与 -H / -A / -b / -d / --data* 等
    常用参数；除设备参数外，同时提取可复用的 Cookies / User-Agent / 原始 ibex，
    供「手动填写 Cookies」逐步粘贴导入。
    """
    empty = {"device": {}, "app_version": {}, "warnings": [], "found": [],
             "user_agent": "", "ibex": "", "cookies": {}, "nickname": ""}
    # 续行符预处理（Windows cmd 的 ^ 与 bash 的 \）
    text = re.sub(r'\^\r?\n\s*', ' ', text or "")
    text = re.sub(r'\\\r?\n\s*', ' ', text)
    url, flag_headers, datas, flag_spans = _parse_curl_tokens(text)

    pairs = {}
    cookies = {}
    user_agent = ""
    for name, value in flag_headers:
        if name == "user-agent":
            if not user_agent:
                user_agent = value
        elif name == "cookie":
            _collect_cookie_text(cookies, value)
        elif name == "ibex":
            _collect_param(pairs, "ibex", value)

    if url:
        try:
            query = parse_qsl(urlsplit(url).query, keep_blank_values=True)
        except ValueError:
            query = []
        for k, v in query:
            _collect_param(pairs, k, v)

    for data in datas:
        _collect_data_text(pairs, data)

    # 兜底：引号内 k=v 正则，覆盖少见的参数书写方式。
    # 先把已识别的 flag 值区间抹成空格，避免把 "k1=v1&k2=v2" 整段误认为一个参数
    blanked = list(text)
    for s, e in flag_spans:
        for i in range(s, e):
            if blanked[i] != "\n":
                blanked[i] = " "
    for k, v in _extract_pairs("".join(blanked)).items():
        _collect_param(pairs, k, v)

    if not pairs and not cookies and not user_agent:
        return False, "未解析到任何参数，请确认粘贴的是完整 curl 命令", empty

    dev, app_version, warnings = _device_from_pairs(pairs)
    if not any(k in pairs for k in _DEVICE_PARAM_KEYS):
        warnings.append("未在 curl 中找到设备参数（ibex 等），已提取 Cookies / User-Agent")

    if not app_version.get("versioncode") and user_agent:
        m = _UA_VERSION_RE.search(user_agent)
        if m:
            app_version["version"] = m.group(1)
            app_version["versioncode"] = m.group(2)

    result = {
        "device": dev,
        "app_version": app_version,
        "warnings": warnings,
        "found": sorted(pairs.keys()),
        "user_agent": user_agent,
        "ibex": pairs.get("ibex", ""),
        "cookies": cookies,
        "nickname": "",
    }
    return True, "解析成功", result


def parse_fields(fields):
    """从「逐个填入的抓包参数」解析设备，返回 (ok, message, result)。"""
    empty = {"device": {}, "app_version": {}, "warnings": [], "found": []}
    if not isinstance(fields, dict):
        return False, "参数格式错误", empty
    pairs = {k: v for k, v in fields.items() if isinstance(v, str) and v.strip()}
    if not pairs:
        return False, "请至少填写 ibex（或其它抓包参数）", empty
    dev, app_version, warnings = _device_from_pairs(pairs)
    return True, "解析成功", {"device": dev, "app_version": app_version,
                             "warnings": warnings, "found": sorted(pairs.keys())}


# ==================== HAR 抓包解析 ====================
# HAR 中仅关注起点/阅文域名的请求，避免采到 CDN 等无关流量
HAR_HOST_KEYWORDS = ("qidian", "yuewen")
# 从 query / POST 参数提取的抓包参数白名单（与 _device_from_pairs 消费的键对齐）
HAR_PARAM_KEYS = ("ibex", "signature", "devicetype", "devicename", "osversion",
                  "version", "sdkversion")
# 「手动填写 Cookies」依赖的关键 cookie，缺失时给出提示
HAR_CRITICAL_COOKIES = ("qid", "QDInfo", "ywguid", "ywkey")
# 判定"抓到了设备参数"的键（仅提取到 version/sdkversion 等版本参数不算）
_DEVICE_PARAM_KEYS = ("ibex", "signature", "devicetype", "devicename")
# 起点昵称（来自 getaccountpage / getprofile / 登录等接口的响应体）
_NICK_RE = re.compile(r'"(?:NickName|Nickname|nickName)"\s*:\s*"((?:[^"\\]|\\.)*)"')
# UA 中的版本信息（QidianClient 也是从 UA 解析版本的），用于 app_version 兜底
_UA_VERSION_RE = re.compile(r'QDReaderAndroid/(\d+\.\d+\.\d+)/(\d+)/')


def _collect_cookie(cookies, key, value):
    """合并单个 cookie，同名取最长值（部分请求可能带截断/置空值）。"""
    key = str(key or "").strip()
    value = str(value or "").strip()
    if key and value and len(value) > len(cookies.get(key, "")):
        cookies[key] = value


def _collect_cookie_text(cookies, raw):
    """解析 `k1=v1; k2=v2` 形式的 cookie 文本并合并。"""
    for part in str(raw or "").split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            _collect_cookie(cookies, k, v)


def _collect_param(pairs, key, value):
    """合并抓包参数（仅白名单键，同名取最长值）。"""
    key = str(key or "").strip()
    if key not in HAR_PARAM_KEYS:
        return
    value = str(value or "").strip()
    if not value:
        return
    if key in ("ibex", "signature"):
        value = _WS_RE.sub("", value)  # base64 可能被换行/空格打断
    if key == "version" and not re.fullmatch(r"\d{3,}", value):
        return  # 过滤同名但含义不同的参数（如 API version=1）
    if len(value) > len(pairs.get(key, "")):
        pairs[key] = value


def _collect_post_params(pairs, post):
    """从 HAR entry 的 postData 提取白名单参数（params / form text / JSON body）。"""
    params = post.get("params")
    if isinstance(params, list):
        for p in params:
            if isinstance(p, dict):
                _collect_param(pairs, p.get("name"), p.get("value"))
    post_text = str(post.get("text") or "").strip()
    if not post_text:
        return
    if post_text.startswith("{"):
        try:
            body_json = json.loads(post_text)
        except json.JSONDecodeError:
            body_json = None
        if isinstance(body_json, dict):
            for k, v in body_json.items():
                if isinstance(v, (str, int, float)):
                    _collect_param(pairs, k, v)
        return
    for k, v in parse_qsl(post_text, keep_blank_values=True):
        _collect_param(pairs, k, v)


def _har_response_text(entry):
    """解码 HAR 响应体（支持 base64 与 gzip），失败返回空串。"""
    content = (entry.get("response") or {}).get("content") or {}
    text = content.get("text") or ""
    if not text or len(text) > 4_000_000:  # 跳过超大响应体（图片等）
        return ""
    if (content.get("encoding") or "") == "base64":
        try:
            raw = base64.b64decode(text)
        except Exception:  # noqa: BLE001
            return ""
        try:
            raw = gzip.decompress(raw)
        except Exception:  # noqa: BLE001
            pass
        try:
            return raw.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return ""
    return text


def _pick_nickname(nick_counts):
    """出现次数最多的昵称（同频取先出现的）。"""
    if not nick_counts:
        return ""
    return max(nick_counts, key=nick_counts.get)


def parse_har(text):
    """解析 HAR 抓包文件内容，返回 (ok, message, result)。

    除设备参数外，同时提取可复用的 Cookies / User-Agent / 原始 ibex，
    供「手动填写 Cookies」一键导入。
    """
    empty = {"device": {}, "app_version": {}, "warnings": [], "found": [],
             "user_agent": "", "ibex": "", "cookies": {}, "stats": {}}
    try:
        har = json.loads(text or "")
    except json.JSONDecodeError as e:
        return False, f"HAR 内容不是有效的 JSON: {e}", empty

    entries = (har.get("log") or {}).get("entries") or []
    if not isinstance(entries, list) or not entries:
        return False, "HAR 中没有请求记录（log.entries 为空）", empty

    pairs = {}       # 抓包参数（ibex / devicetype / ...）
    cookies = {}     # cookie 名 -> 值
    ua_counts = {}   # user-agent -> 出现次数
    nick_counts = {}  # 起点昵称 -> 出现次数
    matched = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        req = entry.get("request") or {}
        url = str(req.get("url") or "")
        if not any(kw in url.lower() for kw in HAR_HOST_KEYWORDS):
            continue
        matched += 1

        headers = {}
        for h in req.get("headers") or []:
            if isinstance(h, dict) and h.get("name"):
                headers[str(h["name"]).lower()] = str(h.get("value") or "")

        ua = headers.get("user-agent", "").strip()
        if ua:
            ua_counts[ua] = ua_counts.get(ua, 0) + 1

        _collect_cookie_text(cookies, headers.get("cookie", ""))
        for c in req.get("cookies") or []:
            if isinstance(c, dict):
                _collect_cookie(cookies, c.get("name"), c.get("value"))

        resp = entry.get("response") or {}
        for h in resp.get("headers") or []:
            if isinstance(h, dict) and str(h.get("name") or "").lower() == "set-cookie":
                # Set-Cookie 一次只有一个 cookie，属性跟在第一个分号后
                _collect_cookie_text(cookies, str(h.get("value") or "").split(";", 1)[0])

        for q in req.get("queryString") or []:
            if isinstance(q, dict):
                _collect_param(pairs, q.get("name"), q.get("value"))
        _collect_post_params(pairs, req.get("postData") or {})

        # 起点昵称：从 getaccountpage / getprofile / 登录等接口的响应体提取
        body = _har_response_text(entry)
        if body:
            for m in _NICK_RE.finditer(body):
                raw = m.group(1)
                try:
                    value = json.loads('"' + raw + '"')  # 还原 \uXXXX 转义
                except Exception:  # noqa: BLE001
                    value = raw
                value = str(value).strip()
                if value:
                    nick_counts[value] = nick_counts.get(value, 0) + 1

    if not matched:
        return False, "HAR 中未找到起点/阅文域名的请求（qidian.com / yuewen.com）", empty

    user_agent = max(ua_counts, key=ua_counts.get) if ua_counts else ""
    dev, app_version, warnings = _device_from_pairs(pairs)

    if not any(k in pairs for k in _DEVICE_PARAM_KEYS):
        # _device_from_pairs 对空参数不产生告警，这里明确提示（常见于不含登录请求的抓包）
        warnings.append("未在请求参数中找到设备参数（ibex / devicetype 等），"
                        "请确认抓包包含登录或刷新请求")
    if not app_version.get("versioncode") and user_agent:
        m = _UA_VERSION_RE.search(user_agent)
        if m:
            app_version["version"] = m.group(1)
            app_version["versioncode"] = m.group(2)

    missing_cookies = [k for k in HAR_CRITICAL_COOKIES if not cookies.get(k)]
    if missing_cookies:
        warnings.append("未捕获到 cookie: " + "、".join(missing_cookies) +
                        "（请确认抓包时账号已登录）")

    result = {
        "device": dev,
        "app_version": app_version,
        "warnings": warnings,
        "found": sorted(pairs.keys()),
        "user_agent": user_agent,
        "ibex": pairs.get("ibex", ""),
        "cookies": cookies,
        "nickname": _pick_nickname(nick_counts),
        "stats": {"entries_total": len(entries), "entries_matched": matched},
    }
    return True, "解析成功", result


# ==================== 规范化 / 合成 ====================
def normalize_device(dev):
    """把设备字段补齐/规范为可用的结构。"""
    if not isinstance(dev, dict):
        return {}
    out = dict(dev)

    def s(key):
        return str(out.get(key) or "").strip()

    out["brand"] = s("brand")
    out["model"] = s("model")
    out["board"] = s("board")
    out["cpu_abi"] = s("cpu_abi") or "arm64-v8a"
    out["device_name"] = s("device_name")
    out["build_id"] = s("build_id")
    out["qid"] = s("qid")
    out["qidth"] = s("qidth") or out["qid"]
    out["phone_security"] = str(out.get("phone_security") or "")
    out["phone_security_over"] = str(out.get("phone_security_over") or "") or out["phone_security"]
    out["ibex_plain"] = str(out.get("ibex_plain") or "")
    out["android_id"] = s("android_id")
    out["jpush_id"] = s("jpush_id")

    try:
        out["android_version"] = int(out.get("android_version") or DEFAULT_ANDROID_VERSION)
    except (ValueError, TypeError):
        out["android_version"] = DEFAULT_ANDROID_VERSION

    res = out.get("resolution")
    if not isinstance(res, dict):
        res = dict(DEFAULT_RESOLUTION)
    try:
        res = {"width": int(res.get("width") or DEFAULT_RESOLUTION["width"]),
               "height": int(res.get("height") or DEFAULT_RESOLUTION["height"])}
    except (ValueError, TypeError):
        res = dict(DEFAULT_RESOLUTION)
    out["resolution"] = res
    return out


def device_warnings(dev):
    """返回设备档案的完整性告警列表。"""
    warns = []
    dev = dev or {}
    for field in REQUIRED_FIELDS:
        if not dev.get(field):
            warns.append(f"缺少必要字段: {field}")
    if not dev.get("ibex_plain"):
        warns.append("缺少 ibex 设备指纹（建议通过抓包 curl 导入以获得真实指纹）")
    if not dev.get("device_name"):
        warns.append("缺少设备名称 device_name")
    return warns


def compose_login_phone(device, version):
    """
    把「设备档案 + 软件版本」合成为 Login.init_device_info 需要的字典。
    version: {version, versioncode, sdkversion}；为空时抛 ValueError。
    """
    if not isinstance(device, dict):
        raise ValueError("设备数据无效")
    if not isinstance(version, dict) or not version.get("version") or not version.get("versioncode"):
        raise ValueError("请先选择软件版本（version / versioncode）")

    dev = normalize_device(device)
    qid = dev["qid"]
    ps = dev["phone_security"]
    return {
        "app_data": {
            "version": str(version["version"]),
            "versioncode": str(version["versioncode"]),
            "sdkversion": str(version.get("sdkversion") or DEFAULT_SDKVERSION),
        },
        "resolution": dev["resolution"],
        "qid": qid,
        "qidth": dev["qidth"] or qid,
        "android_version": dev["android_version"],
        "build_id": dev["build_id"],
        "phone_data": {
            "model": dev["model"],
            "brand": dev["brand"],
            "board": dev["board"],
            "cpu_abi": dev["cpu_abi"],
            "device_name": dev["device_name"],
        },
        "phone_security": {
            "qidnum": len(qid) or 36,
            "qid_36": ps,
            "qid_36_over": dev["phone_security_over"] or ps,
        },
        "android_id": dev.get("android_id", ""),
        "jpush_id": dev.get("jpush_id", ""),
        # 供 Login.gener_ibex 使用：逐字节还原真实设备指纹
        "ibex_plain": dev.get("ibex_plain", ""),
    }


def list_device_summaries():
    """设备列表摘要（供页面展示）。"""
    out = []
    for d in load_devices():
        dev = normalize_device(d.get("device") or {})
        out.append({
            "name": d.get("name", ""),
            "note": d.get("note", ""),
            "source": d.get("source", ""),
            "created": d.get("created", ""),
            "updated": d.get("updated", ""),
            "brand": dev.get("brand", ""),
            "model": dev.get("model", ""),
            "device_name": dev.get("device_name", ""),
            "android_version": dev.get("android_version", ""),
            "has_ibex": bool(dev.get("ibex_plain")),
            "version": d.get("version") or None,
            "warnings": device_warnings(dev),
        })
    return out


