"""
WebUI Flask 应用：页面路由 + JSON API + 口令鉴权。

- 页面：/  /users  /users/<name>  /run  /logs  /tools  /about  /login
- API ：/api/*
- 鉴权：访问口令（QDJOB_WEBUI_PASSWORD），会话 Cookie + CSRF Token
"""

import os
import platform
import secrets
import sys

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import app_info
import cron_manager
import device_manager
import lifecycle
import run_manager
import scheduler
import web_auth
import web_config as wc
import web_service


# ==================== 资源路径（兼容开发 / Nuitka）====================
def _resource_dir(name):
    candidates = []
    # 当前可执行文件/脚本所在目录（打包后即 exe 所在目录）
    try:
        candidates.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    except Exception:  # noqa: BLE001
        pass
    # 本模块所在目录（开发环境 / Nuitka onefile 解包目录）
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.getcwd())
    for directory in candidates:
        path = os.path.join(directory, name)
        if os.path.isdir(path):
            return path
    return os.path.join(candidates[0], name)


def _load_secret_key(workdir):
    """持久化会话密钥，保证重启后会话仍有效。"""
    path = os.path.join(workdir, ".webui_secret_key")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                key = f.read().strip()
            if key:
                return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(key)
    except OSError:
        pass
    return key


# ==================== 应用工厂 ====================
def create_app(workdir=None, password=None):
    if workdir:
        wc.set_workdir(workdir)
    workdir = wc.get_workdir()
    wc.ensure_dirs()

    app = Flask(
        __name__,
        template_folder=_resource_dir("web_templates"),
        static_folder=_resource_dir("web_static"),
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = _load_secret_key(workdir)
    # 口令来源优先级：启动参数 > 环境变量 > 口令文件 > 无
    cli_pw = password or ""
    env_pw = os.environ.get("QDJOB_WEBUI_PASSWORD") or ""
    if cli_pw:
        app.config["AUTH_SOURCE"] = "cli"
        app.config["PASSWORD"] = cli_pw
    elif env_pw:
        app.config["AUTH_SOURCE"] = "env"
        app.config["PASSWORD"] = env_pw
    elif web_auth.has_password():
        app.config["AUTH_SOURCE"] = "file"
        app.config["PASSWORD"] = ""
    else:
        app.config["AUTH_SOURCE"] = "none"
        app.config["PASSWORD"] = ""
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["WORKDIR"] = workdir

    # -------------------- 鉴权 --------------------
    PUBLIC_PATHS = {"/login", "/api/auth/login", "/api/auth/status", "/favicon.ico"}

    def _is_public(path):
        return path in PUBLIC_PATHS or path.startswith("/static/")

    def _password_required():
        return app.config["AUTH_SOURCE"] != "none"

    def _verify_password(candidate):
        src = app.config["AUTH_SOURCE"]
        if src == "file":
            return web_auth.verify(candidate)
        if src in ("cli", "env"):
            return (candidate or "") == app.config["PASSWORD"]
        return True

    def _authed():
        if not _password_required():
            return True
        return bool(session.get("auth"))

    def _get_csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_hex(16)
            session["csrf_token"] = token
        return token

    @app.before_request
    def _guard():
        path = request.path
        if _is_public(path):
            return None
        if not _authed():
            if path.startswith("/api/"):
                return jsonify({"ok": False, "message": "未登录", "data": None}), 401
            return redirect(url_for("page_login"))
        # CSRF 校验（仅针对写操作）
        if request.method in ("POST", "PUT", "DELETE", "PATCH") and path != "/api/auth/login":
            token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not token or token != session.get("csrf_token"):
                return jsonify({"ok": False, "message": "CSRF 校验失败，请刷新页面", "data": None}), 403
        return None

    # -------------------- 模板上下文 --------------------
    @app.context_processor
    def _inject():
        return {
            "version": app_info.VERSION,
            "author": app_info.AUTHOR,
            "project": app_info.PROJECT,
            "csrf_token": session.get("csrf_token", ""),
        }

    _register_pages(app, _get_csrf_token, _password_required)
    _register_api(app, _password_required, _verify_password)
    # 源码运行时启用进程内调度（其它环境由系统计划程序负责）
    scheduler.start_auto_scheduler()
    return app


# ==================== 页面路由 ====================
def _register_pages(app, get_csrf_token, password_required):
    def _ensure_csrf():
        # 页面加载时确保会话里存在 CSRF token，便于前端取用
        get_csrf_token()

    @app.route("/login", methods=["GET"])
    def page_login():
        _ensure_csrf()
        if not password_required() or session.get("auth"):
            return redirect(url_for("page_overview"))
        return render_template("login.html", meta=app_info.meta_dict())

    @app.route("/")
    def page_overview():
        _ensure_csrf()
        return render_template(
            "overview.html",
            active="overview",
            meta=app_info.meta_dict(),
            workdir=app.config["WORKDIR"],
            system=platform.system(),
        )

    @app.route("/users")
    def page_users():
        _ensure_csrf()
        return render_template("users.html", active="users", meta=app_info.meta_dict())

    @app.route("/users/<username>")
    def page_user_detail(username):
        _ensure_csrf()
        return render_template(
            "user_detail.html",
            active="users",
            meta=app_info.meta_dict(),
            username=username,
        )

    @app.route("/run")
    def page_run():
        _ensure_csrf()
        return render_template("run.html", active="run", meta=app_info.meta_dict())

    @app.route("/logs")
    def page_logs():
        _ensure_csrf()
        return render_template("logs.html", active="logs", meta=app_info.meta_dict())

    @app.route("/devices")
    def page_devices():
        _ensure_csrf()
        return render_template("devices.html", active="devices", meta=app_info.meta_dict())

    @app.route("/about")
    def page_about():
        _ensure_csrf()
        return render_template("about.html", active="about", meta=app_info.meta_dict())


# ==================== API 路由 ====================
def _register_api(app, password_required, verify_password):
    def body():
        if request.is_json:
            return request.get_json(silent=True) or {}
        return request.form.to_dict() or {}

    def resp(result):
        return jsonify(result)

    # -------------------- 鉴权 --------------------
    @app.route("/api/auth/status")
    def api_auth_status():
        return jsonify({
            "ok": True,
            "message": "",
            "data": {
                "required": password_required(),
                "authed": bool(session.get("auth")) or not password_required(),
                "source": app.config.get("AUTH_SOURCE", "none"),
            },
        })

    @app.route("/api/auth/login", methods=["POST"])
    def api_auth_login():
        data = body()
        if not password_required():
            session["auth"] = True
            session["csrf_token"] = secrets.token_hex(16)
            return jsonify({"ok": True, "message": "无需口令", "data": {"csrf_token": session["csrf_token"]}})
        if verify_password(data.get("password")):
            session["auth"] = True
            session["csrf_token"] = secrets.token_hex(16)
            return jsonify({"ok": True, "message": "登录成功", "data": {"csrf_token": session["csrf_token"]}})
        return jsonify({"ok": False, "message": "口令错误", "data": None}), 401

    @app.route("/api/auth/logout", methods=["POST"])
    def api_auth_logout():
        session.clear()
        return jsonify({"ok": True, "message": "已退出登录", "data": None})

    @app.route("/api/auth/settings")
    def api_auth_settings():
        return jsonify({
            "ok": True,
            "message": "",
            "data": {
                "required": password_required(),
                "source": app.config.get("AUTH_SOURCE", "none"),
                "managed": app.config.get("AUTH_SOURCE") in ("cli", "env"),
            },
        })

    @app.route("/api/auth/password", methods=["PUT"])
    def api_auth_set_password():
        data = body()
        source = app.config.get("AUTH_SOURCE", "none")
        if source in ("cli", "env"):
            tip = "环境变量 QDJOB_WEBUI_PASSWORD" if source == "env" else "启动参数 --password"
            return jsonify({"ok": False, "message": f"口令由{tip}管理，请在启动配置中修改", "data": None})
        if password_required() and not verify_password(data.get("current")):
            return jsonify({"ok": False, "message": "当前口令不正确", "data": None}), 401
        new_pw = data.get("new") or ""
        if new_pw != (data.get("confirm") or ""):
            return jsonify({"ok": False, "message": "两次输入的新口令不一致", "data": None})
        try:
            web_auth.set_password(new_pw)
        except ValueError as e:
            return jsonify({"ok": False, "message": str(e), "data": None})
        lifecycle.restart_process()
        return jsonify({"ok": True, "message": "口令已更新，程序正在重启以生效...", "data": {"restart": True}})

    @app.route("/api/auth/password", methods=["DELETE"])
    def api_auth_clear_password():
        data = body()
        source = app.config.get("AUTH_SOURCE", "none")
        if source in ("cli", "env"):
            tip = "环境变量 QDJOB_WEBUI_PASSWORD" if source == "env" else "启动参数 --password"
            return jsonify({"ok": False, "message": f"口令由{tip}管理，请在启动配置中修改", "data": None})
        if password_required() and not verify_password(data.get("current")):
            return jsonify({"ok": False, "message": "当前口令不正确", "data": None}), 401
        web_auth.clear_password()
        lifecycle.restart_process()
        return jsonify({"ok": True, "message": "已清除访问口令，程序正在重启...", "data": {"restart": True}})

    # -------------------- 元信息 --------------------
    @app.route("/api/meta")
    def api_meta():
        data = app_info.meta_dict()
        data["workdir"] = app.config["WORKDIR"]
        data["system"] = platform.system()
        data["max_users"] = wc.MAX_USERS
        data["task_names"] = wc.TASK_NAMES
        data["push_service_types"] = wc.PUSH_SERVICE_TYPES
        return resp({"ok": True, "message": "", "data": data})

    # -------------------- 全局配置 --------------------
    @app.route("/api/config", methods=["GET"])
    def api_config_get():
        cfg = wc.load_config()
        # 不回传整个 users（由用户接口负责），避免冗余
        return resp({
            "ok": True,
            "message": "",
            "data": {
                "default_user_agent": cfg.get("default_user_agent", ""),
                "log_level": cfg.get("log_level", "INFO"),
                "log_retention_days": cfg.get("log_retention_days", 7),
                "retry_attempts": cfg.get("retry_attempts", 3),
            },
        })

    @app.route("/api/config", methods=["PUT"])
    def api_config_put():
        data = body()
        cfg = wc.load_config()
        try:
            days = int(data.get("log_retention_days", cfg.get("log_retention_days", 7)))
            retry = int(data.get("retry_attempts", cfg.get("retry_attempts", 3)))
        except (ValueError, TypeError):
            return resp({"ok": False, "message": "日志保留天数/重试次数必须为整数", "data": None})
        if not (1 <= days <= 30):
            return resp({"ok": False, "message": "日志保留天数必须在 1-30 之间", "data": None})
        if not (1 <= retry <= 10):
            return resp({"ok": False, "message": "重试次数必须在 1-10 之间", "data": None})
        cfg["default_user_agent"] = data.get("default_user_agent", cfg.get("default_user_agent", ""))
        cfg["log_level"] = data.get("log_level", cfg.get("log_level", "INFO"))
        cfg["log_retention_days"] = days
        cfg["retry_attempts"] = retry
        wc.save_config(cfg)
        return resp({"ok": True, "message": "配置已保存", "data": None})

    # -------------------- 用户 --------------------
    def _user_summary(user):
        username = user.get("username", "")
        return {
            "username": username,
            "user_agent": user.get("user_agent", ""),
            "cookies_status": wc.cookies_status(username),
            "has_device": os.path.exists(wc.device_path_for(username)),
            "ibex_configured": bool(user.get("ibex")),
            "usertype": user.get("usertype", ""),
            "tokenid": user.get("tokenid", ""),
            "cookies_refresh_interval_days": user.get("cookies_refresh_interval_days", 20),
            "last_cookies_refresh_time": user.get("last_cookies_refresh_time", ""),
            "tasks_enabled": sum(1 for v in (user.get("tasks") or {}).values() if v),
            "push_services_count": len(user.get("push_services") or []),
        }

    @app.route("/api/users")
    def api_users_list():
        cfg = wc.load_config()
        users = [_user_summary(u) for u in cfg.get("users", [])]
        return resp({"ok": True, "message": "", "data": {"users": users, "max_users": wc.MAX_USERS}})

    @app.route("/api/users", methods=["POST"])
    def api_users_create():
        data = body()
        username = (data.get("username") or "").strip()
        ok, msg = wc.validate_username(username)
        if not ok:
            return resp({"ok": False, "message": msg, "data": None})
        cfg = wc.load_config()
        if wc.get_user(cfg, username):
            return resp({"ok": False, "message": "该用户名已存在", "data": None})
        if len(cfg.get("users", [])) >= wc.MAX_USERS:
            return resp({"ok": False, "message": f"最多只能添加 {wc.MAX_USERS} 个用户", "data": None})
        try:
            interval = int(data.get("cookies_refresh_interval_days", 20))
            if interval <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return resp({"ok": False, "message": "cookies 自动刷新间隔必须为正整数（天）", "data": None})
        user = {
            "username": username,
            "cookies_file": f"cookies/{username}.json",
            "usertype": data.get("usertype", "captcha"),
            "tokenid": data.get("tokenid", ""),
            "user_agent": data.get("user_agent", ""),
            "ibex": data.get("ibex", ""),
            "cookies_refresh_interval_days": interval,
            "last_cookies_refresh_time": "",
            "tasks": data.get("tasks") or wc.default_tasks(),
            "push_services": data.get("push_services") or [],
            "readtime_task_config": data.get("readtime_task_config") or {},
        }
        cfg.setdefault("users", []).append(user)
        wc.save_config(cfg)
        return resp({"ok": True, "message": "用户创建成功", "data": _user_summary(user)})

    @app.route("/api/users/<username>")
    def api_user_get(username):
        cfg = wc.load_config()
        user = wc.get_user(cfg, username)
        if not user:
            return resp({"ok": False, "message": f"用户 '{username}' 不存在", "data": None}), 404
        data = dict(user)
        data["cookies"] = wc.load_cookies(username) or {}
        data["has_device"] = os.path.exists(wc.device_path_for(username))
        return resp({"ok": True, "message": "", "data": data})

    @app.route("/api/users/<username>", methods=["PUT"])
    def api_user_update(username):
        data = body()
        cfg = wc.load_config()
        user = wc.get_user(cfg, username)
        if not user:
            return resp({"ok": False, "message": f"用户 '{username}' 不存在", "data": None}), 404
        new_username = (data.get("username", username) or "").strip()
        ok, msg = wc.validate_username(new_username)
        if not ok:
            return resp({"ok": False, "message": msg, "data": None})
        if new_username != username and wc.get_user(cfg, new_username):
            return resp({"ok": False, "message": "该用户名已存在", "data": None})
        try:
            interval = int(data.get("cookies_refresh_interval_days", user.get("cookies_refresh_interval_days", 20)))
            if interval <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return resp({"ok": False, "message": "cookies 自动刷新间隔必须为正整数（天）", "data": None})

        if new_username != username:
            wc.rename_user_artifacts(username, new_username)

        user["username"] = new_username
        user["cookies_file"] = f"cookies/{new_username}.json"
        user["usertype"] = data.get("usertype", user.get("usertype", "captcha"))
        user["tokenid"] = data.get("tokenid", user.get("tokenid", ""))
        user["user_agent"] = data.get("user_agent", user.get("user_agent", ""))
        user["ibex"] = data.get("ibex", user.get("ibex", ""))
        user["cookies_refresh_interval_days"] = interval
        if "tasks" in data and isinstance(data["tasks"], dict):
            user["tasks"] = data["tasks"]
        if "push_services" in data and isinstance(data["push_services"], list):
            user["push_services"] = data["push_services"]
        if "readtime_task_config" in data and isinstance(data["readtime_task_config"], dict):
            user["readtime_task_config"] = data["readtime_task_config"]
        user.setdefault("last_cookies_refresh_time", "")
        wc.save_config(cfg)
        return resp({"ok": True, "message": "用户信息已更新", "data": {"username": new_username}})

    @app.route("/api/users/<username>", methods=["DELETE"])
    def api_user_delete(username):
        cfg = wc.load_config()
        users = cfg.get("users", [])
        target = wc.get_user(cfg, username)
        if not target:
            return resp({"ok": False, "message": f"用户 '{username}' 不存在", "data": None}), 404
        users.remove(target)
        wc.delete_cookies(username)
        device = wc.device_path_for(username)
        if os.path.exists(device):
            try:
                os.remove(device)
            except OSError:
                pass
        wc.save_config(cfg)
        return resp({"ok": True, "message": f"用户 '{username}' 已删除", "data": None})

    # -------------------- cookies --------------------
    @app.route("/api/users/<username>/cookies", methods=["GET"])
    def api_user_cookies_get(username):
        if not wc.get_user(wc.load_config(), username):
            return resp({"ok": False, "message": "用户不存在", "data": None}), 404
        cookies = wc.load_cookies(username) or {}
        return resp({"ok": True, "message": "", "data": cookies})

    @app.route("/api/users/<username>/cookies", methods=["PUT"])
    def api_user_cookies_put(username):
        import json as _json
        data = body()
        cookies = data.get("cookies")
        if isinstance(cookies, str):
            try:
                cookies = _json.loads(cookies)
            except _json.JSONDecodeError as e:
                return resp({"ok": False, "message": f"cookies JSON 格式错误: {e}", "data": None})
        if not isinstance(cookies, dict):
            return resp({"ok": False, "message": "cookies 必须是 JSON 对象", "data": None})
        cfg = wc.load_config()
        user = wc.get_user(cfg, username)
        if not user:
            return resp({"ok": False, "message": "用户不存在", "data": None}), 404
        wc.save_cookies(username, cookies)
        if "user_agent" in data:
            user["user_agent"] = data.get("user_agent", "")
        if "ibex" in data:
            user["ibex"] = data.get("ibex", "")
        wc.save_config(cfg)
        return resp({"ok": True, "message": "Cookies 已保存", "data": None})

    # -------------------- 检测 / 刷新 --------------------
    @app.route("/api/users/<username>/check", methods=["POST"])
    def api_user_check(username):
        data = body()
        kind = data.get("type", "login")
        if not wc.get_user(wc.load_config(), username):
            return resp({"ok": False, "message": "用户不存在", "data": None}), 404
        if kind == "user":
            return resp(web_service.do_check_user_status(username))
        if kind == "risk":
            return resp(web_service.do_check_login_risk(username))
        return resp(web_service.do_check_login_status(username))

    @app.route("/api/users/<username>/refresh", methods=["POST"])
    def api_user_refresh(username):
        return resp(web_service.do_refresh_cookies(username))

    # -------------------- 登录：设备信息 --------------------
    @app.route("/api/login/device", methods=["POST"])
    def api_login_device():
        data = body()
        username = (data.get("username") or "").strip()
        return resp(web_service.do_get_device(username or None))

    @app.route("/api/login/device/<username>")
    def api_login_device_saved(username):
        return resp(web_service.do_load_device(username))

    @app.route("/api/login/device/<username>", methods=["PUT"])
    def api_login_device_save(username):
        data = body()
        device = data.get("device")
        if not isinstance(device, dict):
            return resp({"ok": False, "message": "设备信息必须是 JSON 对象", "data": None})
        return resp(web_service.do_save_device(username, device))

    # -------------------- 登录：手机验证码（两段式）--------------------
    @app.route("/api/login/phone/sendcode", methods=["POST"])
    def api_login_phone_sendcode():
        data = body()
        return resp(web_service.do_phone_sendcode(
            username=(data.get("username") or "").strip(),
            phone=(data.get("phone") or "").strip(),
            device=data.get("device"),
            session_key=data.get("session_key", ""),
            randstr=data.get("randstr", ""),
            ticket=data.get("ticket", ""),
        ))

    @app.route("/api/login/phone/verify", methods=["POST"])
    def api_login_phone_verify():
        data = body()
        return resp(web_service.do_phone_verify(
            username=(data.get("username") or "").strip(),
            phone=(data.get("phone") or "").strip(),
            device=data.get("device"),
            session_key=data.get("session_key", ""),
            code=(data.get("code") or "").strip(),
        ))

    # -------------------- 登录：账号密码（两段式）--------------------
    @app.route("/api/login/password", methods=["POST"])
    def api_login_password():
        data = body()
        username = (data.get("username") or "").strip()
        # 前端若准备了设备信息（真实设备/随机），先落盘，供密码登录使用
        device = data.get("device")
        if username and isinstance(device, dict) and device:
            wc.save_device(username, device)
        return resp(web_service.do_password_login(
            username=username,
            account=(data.get("account") or "").strip(),
            password=data.get("password") or "",
            session_key=data.get("session_key", ""),
            randstr=data.get("randstr", ""),
            ticket=data.get("ticket", ""),
        ))

    # -------------------- 登录：手动 cookies --------------------
    @app.route("/api/login/manual", methods=["POST"])
    def api_login_manual():
        data = body()
        return resp(web_service.do_manual_save(
            username=(data.get("username") or "").strip(),
            ua=data.get("user_agent", ""),
            ibex=data.get("ibex", ""),
            cookies=data.get("cookies"),
        ))

    # -------------------- 阅读时长上报 --------------------
    @app.route("/api/readtime/search_books", methods=["POST"])
    def api_readtime_search_books():
        data = body()
        return resp(web_service.do_search_books(
            (data.get("username") or "").strip(),
            (data.get("keyword") or "").strip(),
        ))

    @app.route("/api/readtime/chapters")
    def api_readtime_chapters():
        return resp(web_service.do_get_chapters(request.args.get("bookid", "").strip()))

    @app.route("/api/readtime/build", methods=["POST"])
    def api_readtime_build():
        data = body()
        return resp(web_service.do_build_records(
            bookid=(data.get("bookid") or "").strip(),
            chapter_ids=data.get("chapter_ids") or [],
            min_dur=data.get("min_dur", 5),
            max_dur=data.get("max_dur", 10),
            final_end_str=data.get("final_end", ""),
        ))

    @app.route("/api/readtime/report", methods=["POST"])
    def api_readtime_report():
        data = body()
        return resp(web_service.do_readtime_report(
            (data.get("username") or "").strip(),
            data.get("records") or [],
        ))

    # -------------------- 运行 / 定时 --------------------
    @app.route("/api/run/manual", methods=["POST"])
    def api_run_manual():
        return resp(run_manager.run_qdjob())

    @app.route("/api/run/info")
    def api_run_info():
        return resp({"ok": True, "message": "", "data": scheduler.status()})

    @app.route("/api/run/schedule", methods=["PUT"])
    def api_run_schedule():
        data = body()
        expr = data.get("expression")
        if not expr and data.get("kind"):
            expr = cron_manager.build_cron(
                data.get("kind"),
                data.get("hour", 12),
                data.get("minute", 0),
                data.get("weekday", 1),
                data.get("value", 1),
            )
            if not expr:
                return resp({"ok": False, "message": "无法根据所选参数生成 cron 表达式", "data": None})
        ok, message = scheduler.apply(expr or "")
        if not ok:
            return resp({"ok": False, "message": message, "data": None})
        info = scheduler.status()
        info["message"] = message
        return resp({"ok": True, "message": message, "data": info})

    @app.route("/api/run/schedule", methods=["DELETE"])
    def api_run_schedule_delete():
        ok, message = scheduler.remove()
        return resp({"ok": ok, "message": message, "data": scheduler.status()})

    # -------------------- 日志 --------------------
    @app.route("/api/logs")
    def api_logs_list():
        return resp({"ok": True, "message": "", "data": run_manager.list_logs()})

    @app.route("/api/logs/content")
    def api_logs_content():
        filename = request.args.get("file", "")
        lines = request.args.get("lines", "300")
        level = request.args.get("level", "")
        return resp(run_manager.tail_log(filename, lines, level))

    # -------------------- 真实设备 / 软件版本 --------------------
    @app.route("/api/devices")
    def api_devices_list():
        return resp({"ok": True, "message": "", "data": {
            "devices": device_manager.list_device_summaries(),
            "versions": device_manager.load_versions(),
        }})

    @app.route("/api/devices", methods=["POST"])
    def api_devices_save():
        data = body()
        name = (data.get("name") or "").strip()
        device = data.get("device") or {}
        if not isinstance(device, dict):
            return resp({"ok": False, "message": "设备数据格式错误", "data": None})
        device = device_manager.normalize_device(device)
        ok, message = device_manager.upsert_device(
            name, device, note=data.get("note", ""), source=data.get("source", "manual"),
            version=data.get("version"))
        if not ok:
            return resp({"ok": False, "message": message, "data": None})
        return resp({"ok": True, "message": message,
                     "data": {"warnings": device_manager.device_warnings(device)}})

    @app.route("/api/devices/<name>")
    def api_devices_get(name):
        d = device_manager.get_device(name)
        if not d:
            return resp({"ok": False, "message": f"设备「{name}」不存在", "data": None}), 404
        return resp({"ok": True, "message": "", "data": d})

    @app.route("/api/devices/<name>", methods=["DELETE"])
    def api_devices_delete(name):
        ok, message = device_manager.delete_device(name)
        return resp({"ok": ok, "message": message, "data": None})

    @app.route("/api/devices/parse", methods=["POST"])
    def api_devices_parse():
        data = body()
        ok, message, result = device_manager.parse_curl(data.get("text", ""))
        return resp({"ok": ok, "message": message, "data": result})

    @app.route("/api/devices/parse-fields", methods=["POST"])
    def api_devices_parse_fields():
        data = body()
        fields = data.get("fields") or {}
        ok, message, result = device_manager.parse_fields(fields)
        return resp({"ok": ok, "message": message, "data": result})

    @app.route("/api/devices/parse-har", methods=["POST"])
    def api_devices_parse_har():
        data = body()
        ok, message, result = device_manager.parse_har(data.get("text", ""))
        return resp({"ok": ok, "message": message, "data": result})

    @app.route("/api/devices/compose", methods=["POST"])
    def api_devices_compose():
        data = body()
        d = device_manager.get_device((data.get("name") or "").strip())
        if not d:
            return resp({"ok": False, "message": "设备不存在", "data": None})
        try:
            login_phone = device_manager.compose_login_phone(d.get("device") or {}, data.get("version"))
        except ValueError as e:
            return resp({"ok": False, "message": str(e), "data": None})
        return resp({"ok": True, "message": "已根据设备与版本生成登录设备信息", "data": login_phone})

    @app.route("/api/versions")
    def api_versions_list():
        return resp({"ok": True, "message": "", "data": device_manager.load_versions()})

    @app.route("/api/versions", methods=["PUT"])
    def api_versions_save():
        data = body()
        v = device_manager.normalize_version(data)
        if not v:
            return resp({"ok": False, "message": "version 与 versioncode 不能为空", "data": None})
        items = [i for i in device_manager.read_user_versions()
                 if not (str(i.get("version")) == v["version"]
                         and str(i.get("versioncode")) == v["versioncode"])]
        items.append(v)
        device_manager.save_user_versions(items)
        return resp({"ok": True, "message": f"版本 {v['version']}（{v['versioncode']}）已保存",
                     "data": device_manager.load_versions()})

    @app.route("/api/versions", methods=["DELETE"])
    def api_versions_delete():
        version = request.args.get("version", "").strip()
        versioncode = request.args.get("versioncode", "").strip()
        items = [i for i in device_manager.read_user_versions()
                 if not (str(i.get("version")) == version and str(i.get("versioncode")) == versioncode)]
        device_manager.save_user_versions(items)
        return resp({"ok": True, "message": "已删除（仅影响工作目录中的版本表）",
                     "data": device_manager.load_versions()})

    # -------------------- 工具 --------------------
    @app.route("/api/tools/cookies-convert", methods=["POST"])
    def api_tools_cookies_convert():
        import json as _json
        data = body()
        raw = data.get("text", "")
        if not raw or not raw.strip():
            return resp({"ok": False, "message": "请输入 cookies 字符串", "data": None})
        cookies = {}
        try:
            for pair in [p.strip() for p in raw.split(";") if p.strip()]:
                if "=" not in pair:
                    raise ValueError(f"无效的键值对: {pair}")
                key, value = pair.split("=", 1)
                cookies[key.strip()] = value.strip()
        except ValueError as e:
            return resp({"ok": False, "message": f"解析失败: {e}", "data": None})
        return resp({
            "ok": True,
            "message": "转换成功",
            "data": {"cookies": cookies, "json": _json.dumps(cookies, indent=2, ensure_ascii=False)},
        })





