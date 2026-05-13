import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os, re
import json
import time
import webbrowser, threading
from Login import QDLogin_PhoneCode, QDLogin_Password, get_random_phone
from utils import check_login_status, check_login_risk, check_user_status, readtime_report

from datetime import datetime
import sys, random
import os
import platform

__version__ = 'v1.3.5'

system = platform.system()
if system == "Windows":
    sys_run = 1
elif system == "Linux":
    sys_run = 2
else:
    sys_run = 3


def resource_path(relative_path):
    """ 获取资源的绝对路径。兼容开发环境、Nuitka 和 PyInstaller """
    if "__compiled__" in globals():
        # Nuitka 编译环境
        base_path = os.path.dirname(__file__)
    elif hasattr(sys, '_MEIPASS'):
        # PyInstaller 编译环境
        base_path = sys._MEIPASS
    else:
        # 开发环境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ConfigEditor:

    MAX_USERS = 3  # 类级常量，限制最大用户数
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
        "QDInfo": ""
    }

    def __init__(self, root):
        # 用于保存登录状态
        self.login_instance = None
        self.session_key = None

        self.root = root
        self.root.title("QDjob配置编辑器")

        # 设置窗口图标和初始尺寸
        # 根据屏幕分辨率设置窗口大小
        self.resolution_set = self.get_resolution_settings()

        main_width = self.resolution_set.get("main_width",1000)
        main_height = self.resolution_set.get("main_height",800)
        font_family = self.resolution_set.get("font_family", "微软雅黑")
        font_size_main = self.resolution_set.get("font_size_main",12)
        font_size_small = self.resolution_set.get("font_size_small",10)

        self.root.geometry(f"{main_width}x{main_height}")

        self.default_font = (font_family, font_size_main)
        self.label_font = (font_family, 20)
        self.small_font = (font_family, font_size_small)

        self.root.option_add("*Font", self.default_font)
        self.root.option_add("*Menu.font", self.default_font)  
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # 初始化主题样式
        self.init_styles()
        
        # 初始化配置数据
        self.config_data = self.load_config()
        self.users_data = self.config_data.get("users", [])
        for user in self.users_data:
            user.setdefault("ibex", "")
        
        # 创建主界面
        self.create_ui()

    def get_resolution_settings(self):
        """
        根据屏幕真实物理宽度配置UI，自动调整窗口大小和字体大小
        """
        screen_width = self.root.winfo_screenwidth()
        
        # 确定分辨率档位 (直接基于宽度判断更可靠)
        if screen_width <= 1280:      # 720p 及以下，或高缩放比例下的屏幕
            resolution_level = "720p"
        elif screen_width <= 1920:    # 1080p 级别
            resolution_level = "1080p"
        elif screen_width <= 2560:    # 2K 级别
            resolution_level = "2k"
        else:                         # 4K 及带鱼屏等更高分辨率
            resolution_level = "4k"
        
        # 根据分辨率档位设置UI参数
        # 注意：开启DPI感知后，这里的像素值是物理像素。
        # 因此高分屏下的尺寸和字体需要适当放大，以保证肉眼观看大小合适。
        if resolution_level == "720p":
            main_width, main_height = 800, 650
            userpage_width, userpage_height = 800, 650
            loginpage_width, loginpage_height = 800, 650
            pushpage_width, pushpage_height = 450, 500
            readtimepage_width, readtimepage_height = 800, 650
            font_size_main = 10
            font_size_small = 9
        elif resolution_level == "1080p":
            main_width, main_height = 1100, 870
            userpage_width, userpage_height = 1100, 870
            loginpage_width, loginpage_height = 900, 730
            pushpage_width, pushpage_height = 550, 630
            readtimepage_width, readtimepage_height = 1100, 850
            font_size_main = 12
            font_size_small = 10
        elif resolution_level == "2k":
            main_width, main_height = 1300, 1100
            userpage_width, userpage_height = 1300, 1100
            loginpage_width, loginpage_height = 1100, 850
            pushpage_width, pushpage_height = 700, 750
            readtimepage_width, readtimepage_height = 1300, 1000
            font_size_main = 14
            font_size_small = 12
        else:  # 4k
            main_width, main_height = 1800, 1400
            userpage_width, userpage_height = 1800, 1400
            loginpage_width, loginpage_height = 1400, 1100
            pushpage_width, pushpage_height = 900, 1000
            readtimepage_width, readtimepage_height = 1800, 1400
            font_size_main = 18   # 4K屏幕下字体必须足够大
            font_size_small = 14
        
        # 字体设定保持不变
        if sys_run == 1 or sys_run == 2:  # Win/Linux
            font_family = "微软雅黑"
        else:  # macOS
            font_family = "Helvetica"

        return {
            "main_width": main_width, "main_height": main_height,
            "userpage_width": userpage_width, "userpage_height": userpage_height,
            "loginpage_width": loginpage_width, "loginpage_height": loginpage_height,
            "pushpage_width": pushpage_width, "pushpage_height": pushpage_height,
            "readtimepage_width": readtimepage_width, "readtimepage_height": readtimepage_height,
            "font_family": font_family,
            "font_size_main": font_size_main, "font_size_small": font_size_small
        }

    def init_styles(self):
        """初始化主题样式"""
        style = ttk.Style()
        
        if sys_run == 1:  # Windows系统
            style.theme_use('vista')
        elif sys_run == 2:  # Linux系统
            style.theme_use('clam')
        else:  # macOS系统
            style.theme_use('default')
        # # 设置主题
        # style.theme_use('vista')
        
        # 配置Treeview样式
        style.configure("Treeview", 
                    rowheight=30, 
                    borderwidth=0,
                    font=self.default_font)
        style.configure("Treeview.Heading", 
                    font=(self.default_font[0], self.default_font[1], "bold"),
                    padding=(5, 5, 5, 5))
        
        # 配置按钮样式
        style.configure("Accent.TButton", 
                    padding=6,
                    relief="flat",
                    background="#4a90e2",
                    font=self.default_font)
        style.map("Accent.TButton",
                background=[('active', '#357abd')])
        
        # 配置输入框样式
        style.configure("Custom.TEntry", 
                    padding=5,
                    relief="flat",
                    borderwidth=1,
                    font=self.default_font)
        
        # 配置标签样式
        style.configure("Help.TLabel",
                    foreground="gray",
                    font=(self.default_font[0], self.default_font[1] - 1))
        
        # 配置复选框样式
        style.configure("TCheckbutton",
                    font=self.default_font)
        
        # 配置标签框架样式
        style.configure("TLabelFrame",
                    font=self.default_font)
        
        # 配置标签框架内部标签样式
        style.configure("TLabelFrame.Label",
                    font=self.default_font)
        
        # 配置Combobox样式
        style.configure("TCombobox", 
                    font=self.default_font,
                    padding=5)
        style.map("TCombobox",
                fieldbackground=[('readonly', 'white')])  # 固定背景色

    
    def load_config(self):
        """加载或初始化配置文件"""
        if not os.path.exists("config.json"):
            # 创建默认配置
            default_config = {
                "default_user_agent": "Mozilla/5.0 (Linux; Android 13; PDEM10 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/109.0.5414.86 MQQBrowser/6.2 TBS/047601 Mobile Safari/537.36 QDJSSDK/1.0  QDNightStyle_1  QDReaderAndroid/7.9.384/1466/1000032/OPPO/QDShowNativeLoading",
                "log_level": "INFO",
                "log_retention_days": 7,
                "retry_attempts": 3,
                "users": []
            }
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            os.makedirs("cookies", exist_ok=True)
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def create_ui(self):
        """创建主界面"""
        # 配置区域
        config_frame = ttk.LabelFrame(self.root, text="全局配置")
        config_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # 配置网格权重
        config_frame.grid_rowconfigure(0, weight=1)
        config_frame.grid_rowconfigure(1, weight=1)
        config_frame.grid_rowconfigure(2, weight=1)
        config_frame.grid_columnconfigure(1, weight=1)

        # default_user_agent
        ttk.Label(config_frame, text="默认User Agent:").grid(row=0, column=0, sticky="w", pady=10)
        self.ua_var = tk.StringVar(value=self.config_data["default_user_agent"])
        ua_entry = ttk.Entry(config_frame, 
                            textvariable=self.ua_var,
                            style="Custom.TEntry")
        ua_entry.grid(row=0, column=1, sticky="ew", pady=10)
        ttk.Label(config_frame, text="💡", style="Help.TLabel").grid(row=0, column=2, sticky="w", pady=10)
        ttk.Label(config_frame, text="浏览器标识字符串", style="Help.TLabel").grid(row=0, column=3, sticky="w", pady=10)

        # log_level
        ttk.Label(config_frame, text="日志等级:").grid(row=1, column=0, sticky="w", pady=10)
        self.log_level_var = tk.StringVar(value=self.config_data["log_level"])
        log_level_combo = ttk.Combobox(config_frame,
                                    textvariable=self.log_level_var,
                                    values=["INFO", "DEBUG", "ERROR"],
                                    state="readonly",
                                    width=10)
        log_level_combo.grid(row=1, column=1, sticky="w", pady=10)

        ttk.Label(config_frame, text="💡", style="Help.TLabel").grid(row=1, column=2, sticky="w", pady=10)
        ttk.Label(config_frame, text="日志输出等级", style="Help.TLabel").grid(
                    row=1, column=3, sticky="w", pady=10)

        # 数值配置
        num_frame = ttk.Frame(config_frame)
        num_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=10)
        
        # 配置网格权重
        num_frame.grid_columnconfigure(0, weight=0)  # 日志保留天数标签列
        num_frame.grid_columnconfigure(1, weight=1)  # Spinbox列
        num_frame.grid_columnconfigure(2, weight=0)  # 单位列
        num_frame.grid_columnconfigure(3, weight=0)  # 重试次数标签列
        num_frame.grid_columnconfigure(4, weight=1)  # Spinbox列
        num_frame.grid_columnconfigure(5, weight=0)  # 单位列

        # 日志保留天数
        ttk.Label(num_frame, text="日志保留天数:").grid(row=0, column=0, sticky="w", padx=0)
        self.log_days_var = tk.IntVar(value=self.config_data["log_retention_days"])

        # 使用 Frame 包裹 Spinbox 和单位标签
        days_container = ttk.Frame(num_frame)
        days_container.grid(row=0, column=1, sticky="w")
        ttk.Spinbox(days_container, from_=1, to=30, 
                    textvariable=self.log_days_var, width=5).pack(side="left")
        ttk.Label(days_container, text="天", style="Help.TLabel").pack(side="left", padx=2)

        # 重试次数
        ttk.Label(num_frame, text="失败重试次数:").grid(row=0, column=2, sticky="w", padx=0)
        self.retry_var = tk.IntVar(value=self.config_data["retry_attempts"])

        # 使用 Frame 包裹 Spinbox 和单位标签
        retries_container = ttk.Frame(num_frame)
        retries_container.grid(row=0, column=3, sticky="w")
        ttk.Spinbox(retries_container, from_=1, to=10, 
                    textvariable=self.retry_var, width=5).pack(side="left")
        ttk.Label(retries_container, text="次", style="Help.TLabel").pack(side="left", padx=2)
        
        # 用户管理
        user_frame = ttk.LabelFrame(self.root, text="用户管理")
        user_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # 配置网格权重
        user_frame.grid_columnconfigure(0, weight=1)
        user_frame.grid_rowconfigure(0, weight=1)

        # 用户列表
        columns = ("username", "user_agent", "cookies_status")
        self.user_list = ttk.Treeview(user_frame, columns=columns, show="headings")
        self.user_list.heading("username", text="用户名", anchor="center")
        self.user_list.heading("user_agent", text="User Agent", anchor="center")
        self.user_list.heading("cookies_status", text="Cookies状态", anchor="center")
        self.user_list.column("username", width=150, anchor="center")
        self.user_list.column("user_agent", width=200, anchor="center")
        self.user_list.column("cookies_status", width=150, anchor="center")
        self.user_list.pack(side="left", fill="both", expand=True)

        # 滚动条
        scrollbar = ttk.Scrollbar(user_frame, orient="vertical", command=self.user_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.user_list.configure(yscrollcommand=scrollbar.set)

        # 按钮区域
        btn_frame = ttk.Frame(user_frame)
        btn_frame.pack(side="bottom", fill="x", pady=5)

        ttk.Button(btn_frame, text="添加用户", style="Accent.TButton", 
                command=self.add_user).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="编辑用户", style="Accent.TButton",
                command=self.edit_user).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="删除用户", style="Accent.TButton",
                command=self.remove_user).pack(fill="x", pady=2)
        
        ttk.Button(btn_frame, text="tokenid状态", style="Accent.TButton",
            command=self.check_user_status_for_selected_user).pack(fill="x", pady=2)
        
        ttk.Button(btn_frame, text="检测登录状态", style="Accent.TButton",
            command=self.check_login_status_for_selected_user).pack(fill="x", pady=2)
        
        ttk.Button(btn_frame, text="检测风险状态", style="Accent.TButton",
            command=self.check_login_risk_for_selected_user).pack(fill="x", pady=2)
        
        ttk.Button(btn_frame, text="阅读时长上报", style="Accent.TButton",
            command=self.readtime_report_for_selected_user).pack(fill="x", pady=2)

        # 初始化用户列表显示
        self.refresh_user_list()

        # 创建按钮框架
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10, fill="x")

        # 保存配置按钮（保持与添加用户按钮相同的宽度）
        save_button = ttk.Button(
            button_frame,
            text="保存配置",
            style="Accent.TButton",
            command=self.save_config,
            width=20  # 固定宽度，与添加用户按钮一致
        )
        save_button.pack(side="left", padx=5, expand=True, fill="x")

        # 执行任务按钮
        execute_button = ttk.Button(
            button_frame,
            text="执行任务",
            style="Accent.TButton",
            command=self.execute_task,
            width=20  # 保持相同宽度
        )
        execute_button.pack(side="right", padx=5, expand=True, fill="x")

        # 创建作者信息框架
        author_frame = ttk.LabelFrame(self.root, text="项目信息")
        author_frame.pack(padx=10, pady=5, fill="x", expand=False)

        # 使用grid布局排列信息
        ttk.Label(author_frame, text=f"作者: JaniQuiz      项目: QDjob      版本: {__version__}", font=self.small_font).grid(
            row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(author_frame, text="本项目为个人项目，仅供学习交流使用，请勿用于非法用途，如有侵权，请联系删除。", font=self.small_font).grid(
            row=1, column=0, sticky="w", padx=5, pady=2)
        
        # 添加声明文本
        ttk.Label(author_frame, text="图形验证码自动处理功能需要获取tokenid，您可以在我的咸鱼上购买", font=self.small_font, ).grid(
            row=2, column=0, sticky="w", padx=5, pady=2)

        # 创建超链接标签
        github_link = ttk.Label(author_frame, text="GitHub: https://github.com/qdjob/QDjob",
                            foreground="blue", cursor="hand2", font=self.small_font)
        github_link.grid(row=3, column=0, sticky="w", padx=5, pady=2)
        
        telegram_link = ttk.Label(author_frame, text="Telegram: https://t.me/+6xMW_7YK0o1jMDE1",
                            foreground="blue", cursor="hand2", font=self.small_font)
        telegram_link.grid(row=3, column=1, sticky="w", padx=5, pady=2)

        xianyu_link = ttk.Label(author_frame, text="咸鱼: https://www.goofish.com/item?id=1000811249803",
                            foreground="blue", cursor="hand2", font=self.small_font)
        xianyu_link.grid(row=5, column=0, sticky="w", padx=5, pady=2)

        # 绑定超链接点击事件
        def callback(event):
            webbrowser.open_new(r"https://github.com/qdjob/QDjob")

        github_link.bind("<Button-1>", callback)

    def refresh_user_list(self):
        """刷新用户列表显示"""
        # 清空现有列表
        for item in self.user_list.get_children():
            self.user_list.delete(item)
        
        # 重新加载用户数据
        for user in self.users_data:
            # 检查Cookies文件状态
            cookies_path = user.get("cookies_file", "")
            
            if cookies_path and os.path.exists(cookies_path):
                try:
                    with open(cookies_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 解析JSON
                    try:
                        cookies_data = json.loads(content)
                        
                        # 检查是否所有字段都为空
                        if isinstance(cookies_data, dict) and all(
                            isinstance(v, str) and v.strip() == "" 
                            for v in cookies_data.values()
                        ):
                            cookies_status = "账号未配置"
                        else:
                            cookies_status = "账号已配置"
                    except json.JSONDecodeError:
                        cookies_status = "格式错误"
                except Exception as e:
                    cookies_status = "读取失败"
            else:
                cookies_status = "账号未配置"
                
            # Token状态检查
            token_status = "未验证" if not user.get("token") else "已验证"
            
            self.user_list.insert("", "end", values=(
                user["username"],
                # user["user_agent"] or "默认User Agent",
                user.get("user_agent", "默认User Agent"),
                cookies_status,
                token_status  # 新增Token状态
            ))

    def check_user_status_for_selected_user(self):
        """检查用户状态"""
        selected = self.user_list.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return
        
        index = self.user_list.index(selected[0])
        user = self.users_data[index]
        username = user["username"]
        
        # 检查tokenid状态
        tokenid = user.get("tokenid", "")
        if not tokenid:
            messagebox.showwarning("警告", f"用户 '{username}' 的tokenid未配置")
            return
        
        # 检测usertype状态
        usertype = user.get("usertype", "")
        if not usertype:
            messagebox.showwarning("警告", f"用户 '{username}' 的usertype未配置")
            return
        try:
            data = check_user_status(tokenid, usertype)
            if not data:
                messagebox.showwarning("警告", f"用户 '{username}' 的tokenid验证失败\n请检查日志")
                return
            expire_time = data.get("expire_time", "")
            remaining_calls = data.get("remaining_calls", "")
            if expire_time == "2099-01-01 00:00:00":
                expire_time = "无限制"
            if remaining_calls == -1:
                remaining_calls = "无限制"
            messagebox.showinfo("用户信息", f"用户 '{username}' 的tokenid已验证成功\n有效期: {expire_time}\n剩余调用次数: {remaining_calls}")
            return
        except Exception as e:
            messagebox.showwarning("警告", f"用户 '{username}' 的usertype验证失败: {e}")
            return
        


    def check_login_status_for_selected_user(self):
        """检测选中用户的登录状态"""
        selected = self.user_list.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return
        
        index = self.user_list.index(selected[0])
        user = self.users_data[index]
        username = user["username"]
        
        # 检查cookies状态
        cookies_file = user.get("cookies_file", "")
        if not cookies_file or not os.path.exists(cookies_file):
            messagebox.showwarning("警告", f"用户 '{username}' 的cookies未配置")
            return
        
        # 获取cookies
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查内容是否为空
            if not content.strip():
                messagebox.showwarning("警告", f"用户 '{username}' 的cookies文件为空")
                return
            
            cookies = json.loads(content)
        except json.JSONDecodeError as e:
            messagebox.showerror("错误", f"cookies文件格式错误: {str(e)}")
            return
        except Exception as e:
            messagebox.showerror("错误", f"无法读取cookies文件: {str(e)}")
            return
        
        # 获取user_agent
        user_agent = user.get("user_agent", "")
        if not user_agent:
            # 使用config.json中的默认UA
            user_agent = self.config_data["default_user_agent"]
            if not user_agent:
                # 如果config.json中也没有配置，默认使用一个基本格式
                user_agent = "Mozilla/5.0 (Linux; Android 13; PDEM10 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/109.0.5414.86 MQQBrowser/6.2 TBS/047601 Mobile Safari/537.36 QDJSSDK/1.0 QDNightStyle_1 QDReaderAndroid/7.9.384/1466/1000032/OPPO/QDShowNativeLoading"
        
        ibex = user.get("ibex", "")
        if not ibex:
            messagebox.showwarning("警告", f"用户 '{username}' 的ibex未配置")
            return

        try:
            is_main_logged_in = check_login_status(user_agent, cookies)
            is_adv_logged_in = check_login_risk(user_agent, cookies, ibex)
            main_status = "✅主页已登录" if is_main_logged_in else "❌主页未登录或者已过期"
            adv_status = "✅福利中心已登录" if is_adv_logged_in else "❌福利中心未登录或者已过期"
        except Exception as e:
            messagebox.showerror("错误", f"检测登录风险状态时出错: {str(e)}", icon='error')
        
        messagebox.showinfo("登录状态", f"用户 '{username}' 的登录状态:\n主页: {main_status}\n福利中心: {adv_status}", icon='info')

    def check_login_risk_for_selected_user(self):
        """检测选中用户的登录风险状态"""
        selected = self.user_list.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return
        
        index = self.user_list.index(selected[0])
        user = self.users_data[index]
        username = user["username"]
        
        # 检查cookies状态
        cookies_file = user.get("cookies_file", "")
        if not cookies_file or not os.path.exists(cookies_file):
            messagebox.showwarning("警告", f"用户 '{username}' 的cookies未配置")
            return
        
        # 获取cookies
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查内容是否为空
            if not content.strip():
                messagebox.showwarning("警告", f"用户 '{username}' 的cookies文件为空")
                return
            
            cookies = json.loads(content)
        except json.JSONDecodeError as e:
            messagebox.showerror("错误", f"cookies文件格式错误: {str(e)}")
            return
        except Exception as e:
            messagebox.showerror("错误", f"无法读取cookies文件: {str(e)}")
            return
        
        # 获取user_agent
        user_agent = user.get("user_agent", "")
        if not user_agent:
            # 使用config.json中的默认UA
            user_agent = self.config_data["default_user_agent"]
            if not user_agent:
                # 如果config.json中也没有配置，默认使用一个基本格式
                user_agent = "Mozilla/5.0 (Linux; Android 13; PDEM10 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/109.0.5414.86 MQQBrowser/6.2 TBS/047601 Mobile Safari/537.36 QDJSSDK/1.0 QDNightStyle_1 QDReaderAndroid/7.9.384/1466/1000032/OPPO/QDShowNativeLoading"
        
        ibex = user.get("ibex", "")
        if not ibex:
            messagebox.showwarning("警告", f"用户 '{username}' 的ibex未配置")
            return

        # 调用check_login_status函数
        try:
            is_logged_in = check_login_risk(user_agent, cookies, ibex)
            if is_logged_in==True:
                messagebox.showinfo("风险状态", f"用户 '{username}' 无风险情况", icon='info')
            elif is_logged_in==False:
                messagebox.showwarning("风险状态", f"用户 '{username}' 获取风险情况失败", icon='warning')
            else:
                messagebox.showwarning("风险状态", f"用户 '{username}' 有风险情况⚠️\n {str(is_logged_in)}", icon='warning')
        except Exception as e:
            messagebox.showerror("错误", f"检测风险状态时出错: {str(e)}", icon='error')

    def readtime_report_for_selected_user(self):
        """对选中用户进行阅读时长上报（仅批量生成）"""

        # --- 1. 预检查逻辑 ---
        selected = self.user_list.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return

        index = self.user_list.index(selected[0])
        user = self.users_data[index]
        username = user["username"]

        # 检查cookies
        cookies_file = user.get("cookies_file", "")
        if not cookies_file or not os.path.exists(cookies_file):
            messagebox.showwarning("警告", f"用户 '{username}' 的cookies未配置")
            return

        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if not content.strip():
                messagebox.showwarning("警告", f"用户 '{username}' 的cookies文件为空")
                return
            cookies = json.loads(content)
        except Exception as e:
            messagebox.showerror("错误", f"无法读取cookies: {str(e)}")
            return

        user_agent = user.get("user_agent", "")
        if not user_agent:
            user_agent = self.config_data["default_user_agent"]

        ibex = user.get("ibex", "")
        if not ibex:
            messagebox.showwarning("警告", f"用户 '{username}' 的ibex未配置")
            return

        # --- 2. 构建UI界面（仅批量配置）---
        readtimepage_width = self.resolution_set.get("readtimepage_width")
        readtimepage_height = self.resolution_set.get("readtimepage_height")

        dialog = tk.Toplevel(self.root)
        dialog.title(f"阅读时长上报 - {username}")
        if readtimepage_width and readtimepage_height:
            dialog.geometry(f"{readtimepage_width}x{readtimepage_height}")
        else:
            dialog.geometry("900x700")

        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill="both", expand=True)

        # ==================== 批量上报配置区域 ====================
        batch_frame = ttk.LabelFrame(main_frame, text="批量上报阅读记录配置", padding="10")
        batch_frame.pack(fill="x", pady=(0, 10))

        # 配置列权重：第0列标签，第1列输入框可拉伸，第2、3列按钮固定宽度
        batch_frame.grid_columnconfigure(1, weight=1)   # 输入框可拉伸
        batch_frame.grid_columnconfigure(2, weight=0)   # 搜索按钮不拉伸
        batch_frame.grid_columnconfigure(3, weight=0)   # 获取章节按钮不拉伸

        # 第0行：书籍ID输入 + 搜索按钮 + 获取章节列表按钮
        ttk.Label(batch_frame, text="书籍ID:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        book_id_combo = ttk.Combobox(batch_frame, style="Custom.TEntry", width=30)
        book_id_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        search_btn = ttk.Button(batch_frame, text="搜索", style="Accent.TButton",
                                command=lambda: self._search_books_popup(book_id_combo, user_agent, cookies, ibex))
        search_btn.grid(row=0, column=2, padx=5, pady=5)

        get_chapters_btn = ttk.Button(batch_frame, text="获取章节列表", style="Accent.TButton",
                                    command=lambda: self._get_chapters(book_id_combo, chapters_tree))
        get_chapters_btn.grid(row=0, column=3, padx=5, pady=5)

        # 第1行：章节列表（左侧） + 右侧随机选择面板
        batch_frame.grid_rowconfigure(1, weight=1)  # 章节列表行可拉伸

        # 章节列表框架（占左侧三列）
        chapters_frame = ttk.Frame(batch_frame)
        chapters_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        columns = ("name", "id")
        chapters_tree = ttk.Treeview(chapters_frame, columns=columns, show="headings", selectmode="extended", height=4)
        chapters_tree.heading("name", text="章节名称")
        chapters_tree.heading("id", text="章节ID")
        chapters_tree.column("name", width=300)
        chapters_tree.column("id", width=100)

        chapters_scrollbar = ttk.Scrollbar(chapters_frame, orient="vertical", command=chapters_tree.yview)
        chapters_tree.configure(yscrollcommand=chapters_scrollbar.set)
        chapters_tree.pack(side="left", fill="both", expand=True)
        chapters_scrollbar.pack(side="right", fill="y")

        # 右侧随机选择面板（重新布局：数量、按钮、提示）
        random_right_frame = ttk.Frame(batch_frame)
        random_right_frame.grid(row=1, column=3, sticky="n", padx=5, pady=5)  # 改为 sticky="n" 使内容贴顶
        random_right_frame.grid_columnconfigure(0, weight=1)  # 让内部元素水平居中

        # 随机数量选择（行0）
        random_count_frame = ttk.Frame(random_right_frame)
        random_count_frame.grid(row=0, column=0, pady=(0, 5))
        ttk.Label(random_count_frame, text="随机选择数量:").pack(side="left", padx=2)
        random_count_var = tk.IntVar(value=20)
        ttk.Spinbox(random_count_frame, from_=1, to=100, textvariable=random_count_var, width=5).pack(side="left", padx=2)

        # 随机选择按钮（行1）
        random_btn = ttk.Button(random_right_frame, text="随机选择章节", style="Accent.TButton",
                                command=lambda: self._random_select_chapters(chapters_tree, random_count_var.get()))
        random_btn.grid(row=1, column=0, pady=5)

        # 提示文字（行2）
        hint_label = ttk.Label(random_right_frame, text="按住 shift 或 ctrl 可以手动进行多选",
                            style="Help.TLabel", justify="center")
        hint_label.grid(row=2, column=0, pady=5)

        # 第2行：每章阅读时长范围
        range_frame = ttk.Frame(batch_frame)
        range_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        ttk.Label(range_frame, text="每章阅读时长范围(分钟):").pack(side="left", padx=5)
        min_duration_var = tk.IntVar(value=5)
        ttk.Spinbox(range_frame, from_=1, to=60, textvariable=min_duration_var, width=5).pack(side="left", padx=2)
        ttk.Label(range_frame, text="—").pack(side="left")
        max_duration_var = tk.IntVar(value=10)
        ttk.Spinbox(range_frame, from_=1, to=60, textvariable=max_duration_var, width=5).pack(side="left", padx=2)
        ttk.Label(range_frame, text="分钟").pack(side="left", padx=5)

        # 第3行：最终阅读结束时间
        final_end_frame = ttk.Frame(batch_frame)
        final_end_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        ttk.Label(final_end_frame, text="最终阅读结束时间:").pack(side="left", padx=5)
        default_end_ts = int(time.time() * 1000) - 3000
        default_end_str = datetime.fromtimestamp(default_end_ts / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
        final_end_var = tk.StringVar(value=default_end_str)
        final_end_entry = ttk.Entry(final_end_frame, textvariable=final_end_var, style="Custom.TEntry", width=20)
        final_end_entry.pack(side="left", padx=5)

        # 批量添加记录按钮（右侧，垂直居中于第2、3行）
        batch_btn_frame = ttk.Frame(batch_frame)
        batch_btn_frame.grid(row=2, column=3, rowspan=2, sticky="ns", padx=5)
        batch_btn_frame.grid_rowconfigure(0, weight=1)
        batch_add_btn = ttk.Button(batch_btn_frame, text="批量添加记录", style="Accent.TButton",
                                command=lambda: self._batch_add_records(
                                    chapters_tree, min_duration_var.get(), max_duration_var.get(),
                                    final_end_var.get(), tree, book_id_combo, update_total_duration))
        batch_add_btn.grid(row=1, column=0, pady=10)

        # ==================== 待上报列表（左树右控件布局）====================
        list_frame = ttk.LabelFrame(main_frame, text="待上报列表", padding="5")
        list_frame.pack(fill="both", expand=True, pady=5)

        # 左侧树形列表框架
        left_list_frame = ttk.Frame(list_frame)
        left_list_frame.pack(side="left", fill="both", expand=True)

        columns = ("bookid", "chapterid", "duration", "starttime", "endtime", "metadata")
        tree = ttk.Treeview(left_list_frame, columns=columns, show="headings", selectmode="extended", height=6)
        tree.heading("bookid", text="书籍ID")
        tree.heading("chapterid", text="章节ID")
        tree.heading("duration", text="时长(分)")
        tree.heading("starttime", text="开始时间")
        tree.heading("endtime", text="结束时间")
        tree.column("bookid", width=100)
        tree.column("chapterid", width=100)
        tree.column("duration", width=60)
        tree.column("starttime", width=150)
        tree.column("endtime", width=150)
        tree.column("metadata", width=0, stretch=False)

        scrollbar = ttk.Scrollbar(left_list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 右侧控件框架
        right_list_frame = ttk.Frame(list_frame, width=120)  # 固定宽度
        right_list_frame.pack(side="right", fill="y", padx=(5, 0))
        right_list_frame.pack_propagate(False)  # 防止收缩

        # 总时长标签
        total_duration_label = ttk.Label(right_list_frame, text="总时长:\n0 分钟", justify="center",
                                        font=(self.default_font[0], self.default_font[1], "bold"))
        total_duration_label.pack(pady=(10, 5))

        # 删除按钮
        def delete_selected():
            for item in tree.selection():
                tree.delete(item)
            update_total_duration()

        delete_btn = ttk.Button(right_list_frame, text="删除选中行", style="Accent.TButton", command=delete_selected)
        delete_btn.pack(pady=5)

        # 更新总时长的函数
        def update_total_duration():
            total_minutes = 0.0
            for item in tree.get_children():
                values = tree.item(item, "values")
                try:
                    duration = float(values[2])
                    total_minutes += duration
                except (ValueError, IndexError):
                    continue
            total_duration_label.config(text=f"总时长:\n{total_minutes:.2f} 分钟")

        # ==================== 底部操作区 ====================
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=10)

        def submit_report():
            items = tree.get_children()
            if not items:
                messagebox.showwarning("提示", "列表为空，请先添加记录")
                return

            chapter_info_list = []
            try:
                for item in items:
                    values = tree.item(item, "values")
                    bid = values[0]
                    cid = values[1]
                    metadata = values[5].split("|")
                    read_ms = int(metadata[0])
                    start_ts = int(metadata[1])
                    end_ts = int(metadata[2])

                    read_data = {
                        "readTime": read_ms,
                        "bookId": int(bid),
                        "chapterId": int(cid),
                        "startTime": start_ts,
                        "endTime": end_ts,
                        "bookType": 1,
                        "chapterVip": 1,
                        "scrollMode": 1,
                        "unlockStatus": -100,
                        "unlockReason": -100,
                        "sp": "",
                    }
                    chapter_info_list.append(read_data)

                success = readtime_report(user_agent, cookies, ibex, chapter_info_list)
                if success:
                    messagebox.showinfo("成功", f"成功上报 {len(chapter_info_list)} 条阅读记录")
                    dialog.destroy()
                else:
                    messagebox.showerror("失败", "上报失败，请检查日志或网络")
            except Exception as e:
                messagebox.showerror("错误", f"构建数据或上报过程中出错: {str(e)}")

        ttk.Button(action_frame, text="确认上报", style="Accent.TButton", command=submit_report).pack(side="right", padx=10)
        ttk.Button(action_frame, text="取消", style="Accent.TButton", command=dialog.destroy).pack(side="right", padx=10)

        # 初始化总时长
        update_total_duration()

    # ==================== 辅助方法（需放入ConfigEditor类中）====================
    def _search_books_popup(self, combo, user_agent, cookies, ibex):
        """搜索书籍并弹出选择窗口"""
        keyword = combo.get().strip()
        if not keyword:
            messagebox.showwarning("警告", "请输入搜索关键词")
            return
        try:
            from utils import search_books
            booklist = search_books(user_agent, cookies, ibex, keyword)
            if not booklist:
                messagebox.showinfo("提示", "未找到相关书籍")
                return

            # 创建弹窗
            popup = tk.Toplevel(self.root)
            popup.title("选择书籍")
            popup.geometry("600x400")
            popup.transient(self.root)
            popup.grab_set()

            # 表格显示书籍列表
            frame = ttk.Frame(popup, padding=10)
            frame.pack(fill="both", expand=True)

            columns = ("name", "author", "bookid")
            tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=8)
            tree.heading("name", text="书籍名")
            tree.heading("author", text="作者")
            tree.heading("bookid", text="书籍ID")
            tree.column("name", width=200)
            tree.column("author", width=150)
            tree.column("bookid", width=100)

            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # 插入数据
            for book in booklist:
                tree.insert("", "end", values=(book['BookName'], book['AuthorName'], book['BookId']))

            # 确认选择按钮
            def confirm():
                selected = tree.selection()
                if not selected:
                    messagebox.showwarning("警告", "请先选择一本书")
                    return
                item = tree.item(selected[0])
                book_id = item['values'][2]
                combo.set(str(book_id))
                popup.destroy()

            btn_frame = ttk.Frame(popup)
            btn_frame.pack(fill="x", pady=10)
            ttk.Button(btn_frame, text="确认", style="Accent.TButton", command=confirm).pack(side="left", padx=10, expand=True)
            ttk.Button(btn_frame, text="取消", style="Accent.TButton", command=popup.destroy).pack(side="right", padx=10, expand=True)

        except Exception as e:
            messagebox.showerror("错误", f"搜索失败: {str(e)}")

    def _get_chapters(self, book_id_combo, tree):
        """获取章节列表并填充到Treeview"""
        bookid = book_id_combo.get().strip()
        if not bookid:
            messagebox.showwarning("警告", "请输入书籍ID")
            return
        try:
            from utils import get_chapters
            chapterlist = get_chapters(bookid)
            if not chapterlist:
                messagebox.showinfo("提示", "未获取到章节列表")
                return
            # 清空并填充
            for item in tree.get_children():
                tree.delete(item)
            for ch in chapterlist:
                tree.insert("", "end", values=(ch['chapterName'], ch['chapterid']))
        except Exception as e:
            messagebox.showerror("错误", f"获取章节列表失败: {str(e)}")

    def _random_select_chapters(self, tree, count):
        """随机选择连续的count个章节"""
        items = tree.get_children()
        total = len(items)
        if total == 0:
            messagebox.showwarning("警告", "章节列表为空")
            return
        if count > total:
            count = total
        # 清除已有选中
        tree.selection_remove(tree.selection())
        start = random.randint(0, total - count)
        for i in range(start, start + count):
            tree.selection_add(items[i])

    def _batch_add_records(self, chapters_tree, min_dur, max_dur, final_end_str, target_tree, book_id_combo, update_callback=None):
        """批量生成阅读记录并添加到目标tree"""
        # 获取选中的章节
        selected = chapters_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先在章节列表中选择要上报的章节")
            return
        # 按列表顺序排序（索引从小到大）
        items = chapters_tree.get_children()
        selected_indices = [items.index(it) for it in selected]
        selected_indices.sort()
        selected_items = [items[i] for i in selected_indices]

        # 解析最终结束时间
        try:
            final_dt = datetime.strptime(final_end_str, '%Y-%m-%d %H:%M:%S')
            final_ts = int(final_dt.timestamp() * 1000)
        except ValueError:
            messagebox.showerror("错误", "最终结束时间格式错误，应为 YYYY-MM-DD HH:MM:SS")
            return

        if min_dur > max_dur:
            messagebox.showerror("错误", "最小时长不能大于最大时长")
            return

        # 从后向前生成记录
        current_end_ts = final_ts
        records = []
        for item in reversed(selected_items):
            ch_name, ch_id = chapters_tree.item(item, 'values')
            # 随机生成阅读时长（分钟）
            minutes = random.randint(min_dur, max_dur)
            read_ms = minutes * 60 * 1000
            # 开始时间 = 结束时间 - 阅读时长
            start_ts = current_end_ts - read_ms
            # 加入列表（顺序：后面插入的会排在前面，最终再反转）
            records.append({
                'bookid': '',  # 书籍ID需要从外部传入？这里先留空，后续从章节列表所在书籍获取？但批量添加时书籍ID是固定的，可以从book_id_combo获取
                'chapterid': ch_id,
                'read_ms': read_ms,
                'start_ts': start_ts,
                'end_ts': current_end_ts
            })
            # 为下一个（更早的）章节生成一个随机间隔（1-3秒）
            gap_ms = random.randint(1000, 3000)
            current_end_ts = start_ts - gap_ms

        # 反转记录，使其按时间正序（最早的在前）
        records.reverse()

        # 获取书籍ID（从批量区域的书籍ID输入框）
        bookid = book_id_combo.get().strip()
        if not bookid:
            messagebox.showwarning("警告", "请先在批量区域填写书籍ID")
            return

        for rec in records:
            start_str = datetime.fromtimestamp(rec['start_ts'] / 1000.0).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            end_str = datetime.fromtimestamp(rec['end_ts'] / 1000.0).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            target_tree.insert("", "end", values=(
                bookid,
                rec['chapterid'],
                f"{rec['read_ms']/60000:.2f}",
                start_str,
                end_str,
                f"{rec['read_ms']}|{rec['start_ts']}|{rec['end_ts']}"
            ))

        if update_callback:
            update_callback()  # 更新总时长

        messagebox.showinfo("成功", f"已生成 {len(records)} 条阅读记录，请核对后上报")
        
    def validate_username(self, username):
        """验证用户名是否符合格式要求"""
        if not username:
            return False, "用户名不能为空"
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]{2,20}$', username):
            return False, "用户名格式错误！\n要求：\n1. 2-20个字符\n2. 仅支持中文、字母、数字和下划线"
        return True, ""
    
    def get_user_cookies(self, username):
        """获取指定用户的cookies内容"""
        # 查找用户
        user = next((u for u in self.users_data if u["username"] == username), None)
        if not user:
            return None
        
        cookies_file = user.get("cookies_file", "")
        if not cookies_file or not os.path.exists(cookies_file):
            return None
        
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                content = f.read()
            cookies_data = json.loads(content)
            return cookies_data
        except Exception:
            return None
        
    def save_user_to_config(self, username, ua, ibex, cookies_file):
        """
        保存用户信息到config.json
        如果用户不存在则添加，存在则更新
        """
        # 检查用户是否存在
        user_exists = False
        for user in self.users_data:
            if user["username"] == username:
                user_exists = True
                # 更新现有用户
                user.update({
                    "user_agent": ua,
                    "ibex": ibex,
                    "cookies_file": cookies_file
                })
                break
        
        # 如果不存在，创建新用户
        if not user_exists:
            new_user = {
                "username": username,
                "cookies_file": cookies_file,
                "user_agent": ua,
                "ibex": ibex,
                "usertype": "captcha",  # 默认值
                "tokenid": "",  # 可能需要从其他地方获取
                "tasks": {
                    "签到任务": True,
                    "激励碎片任务": True,
                    "章节卡任务": True,
                    "游戏中心任务": True,
                    "每日抽奖任务": True,
                    "章节卡信息推送": True,
                },
                "push_services": []
            }
            self.users_data.append(new_user)
        
        # 保存配置
        self.save_users_config()
    
    def getdevice(self):
        """获取随机设备信息函数"""
        login_phone = get_random_phone()
        if not login_phone:
            return None
        return login_phone
    
    def show_phone_login_dialog(self, parent, username):
        """显示手机验证码登录对话框"""
        # 验证用户名
        is_valid, message = self.validate_username(username)
        if not is_valid:
            messagebox.showerror("错误", message)
            return

        loginpage_width = self.resolution_set.get("loginpage_width")
        loginpage_height = self.resolution_set.get("loginpage_height")

        dialog = tk.Toplevel(parent)
        dialog.title("手机验证码登录")
        if loginpage_width and loginpage_height:
            dialog.geometry(f"{loginpage_width}x{loginpage_height}")
        else:
            dialog.geometry("800x650")
        # dialog.geometry("800x650")
        # 关键设置：确保对话框是模态的
        dialog.transient(parent)  # 设置为临时窗口（关联到父窗口）
        dialog.grab_set()         # 捕获所有事件，使对话框成为模态
        dialog.focus_set()        # 将焦点设置到对话框
        dialog.lift()             # 确保对话框显示在最上层
        
        form_frame = ttk.Frame(dialog, padding="20 15 20 15")
        form_frame.pack(fill="both", expand=True)

        # 在创建对话框的底部添加状态提示区域（在原有代码基础上添加）
        status_frame = ttk.Frame(form_frame)
        status_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

        self.status_label = ttk.Label(status_frame, text="", font=self.default_font)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_rowconfigure(0, weight=1)
        self.status_label.pack(side="left", padx=5)
        
        # 手机号输入
        ttk.Label(form_frame, text="手机号:").grid(row=0, column=0, sticky="w", pady=5)
        phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=phone_var, style="Custom.TEntry", width=20).grid(row=0, column=1, sticky="w", pady=5)
        
        # 获取设备信息按钮
        def get_device_info():
            # 调用getdevice函数
            device_data = self.getdevice()
            if device_data:
                device_text.config(state="normal")
                device_text.delete("1.0", "end")
                device_text.insert("1.0", json.dumps(device_data, indent=2, ensure_ascii=False))
                device_text.config(state="disabled")
        
        ttk.Button(form_frame, text="获取随机设备信息", style="Accent.TButton",
                command=get_device_info).grid(row=0, column=2, sticky="w", padx=5, pady=5)

        # 获取验证码按钮
        def get_verification_code(phone_var, device_text):
            phone = phone_var.get().strip()
            if not phone:
                messagebox.showerror("错误", "请输入手机号")
                return
            
            # 检查设备信息输入框是否为空
            device_info = device_text.get("1.0", "end-1c").strip()
            if not device_info:
                messagebox.showerror("错误", "请先点击'获取随机设备信息'按钮获取设备信息")
                return
            
            # 尝试解析设备信息JSON
            try:
                login_phone = json.loads(device_info)
            except json.JSONDecodeError:
                messagebox.showerror("错误", "设备信息格式错误，请重新获取设备信息")
                return
            
            # 创建登录实例
            self.login_instance = QDLogin_PhoneCode(phonenum=phone)
            
            # 直接使用设备信息内容初始化
            if not self.login_instance.init_device_info(login_phone):
                messagebox.showerror("错误", "设备信息初始化失败")
                return
            
            # 显示加载状态
            self.status_label.config(text="获取验证码中……", foreground="blue")
            
            # 1. 先在主线程尝试发送验证码（可能不需要图形验证码）
            try:
                # 发送手机验证码
                status, data = self.login_instance.send_phonecode()
                
                # 2. 如果需要图形验证码，在主线程中处理
                if status == 'captcha':
                    self.session_key = data
                    self.status_label.config(text="需要图形验证码，请稍候...", foreground="blue")
                    
                    # 关键：在主线程中调用get_captcha（确保pywebview正常工作）
                    captcha_data = self.login_instance.get_captcha()
                    if not captcha_data:
                        self.status_label.config(text="获取图形验证码失败", foreground="red")
                        return
                        
                    # 使用图形验证码重新发送（仍在主线程）
                    status, data = self.login_instance.send_phonecode(
                        self.session_key, 
                        captcha_data['randstr'], 
                        captcha_data['ticket']
                    )
                    if status == 'captcha':
                        self.status_label.config(text="图形验证码验证失败", foreground="red")
                        return
                        
                    if status in [True, 'True']:
                        self.session_key = data
                        self.status_label.config(text="验证码已发送", foreground="green")
                    else:
                        self.status_label.config(text=f"验证码发送失败: {data}", foreground="red")
                elif status in [True, 'True']:
                    self.session_key = data
                    self.status_label.config(text="验证码已发送", foreground="green")
                else:
                    self.status_label.config(text=f"验证码发送失败: {data}", foreground="red")
            except Exception as e:
                self.status_label.config(text=f"验证码发送过程中出错: {str(e)}", foreground="red")
        
        # 获取验证码按钮
        ttk.Button(form_frame, text="获取验证码", style="Accent.TButton",
                command=lambda: get_verification_code(phone_var, device_text)
        ).grid(row=1, column=2, sticky="w", padx=5, pady=5)
    
        
        # 验证码输入
        ttk.Label(form_frame, text="验证码:").grid(row=1, column=0, sticky="w", pady=5)
        code_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=code_var, style="Custom.TEntry", width=20).grid(row=1, column=1, sticky="w", pady=5)
        
        # 登录按钮
        def login(phone_var, code_var, cookies_text, ua_var, ibex_var):
            phone = phone_var.get().strip()
            code = code_var.get().strip()
            if not phone or not code:
                messagebox.showerror("错误", "手机号和验证码不能为空")
                return
            
            # 显示加载状态
            self.status_label.config(text="登录中……", foreground="blue")
            
            # 在新线程中执行网络请求（不需要pywebview的部分）
            def login_thread():
                try:
                    # 验证手机验证码
                    status = self.login_instance.check_phonecode(self.session_key, code)
                    if not status:
                        self.root.after(0, lambda: self.status_label.config(
                            text="手机验证码验证失败", foreground="red"))
                        return
                    
                    # 完成登录
                    status = self.login_instance.login_druidv6()
                    if not status:
                        self.root.after(0, lambda: self.status_label.config(
                            text="登录druidv6.if.qidian.com失败", foreground="red"))
                        return
                    
                    # 获取cookies
                    cookies = self.login_instance.cookies
                    
                    # 通过主线程更新UI
                    self.root.after(0, lambda: _update_login_success(
                        cookies, cookies_text, ua_var, ibex_var))
                except Exception as e:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"登录过程中出错: {str(e)}", foreground="red"))
            
            threading.Thread(target=login_thread, daemon=True).start()

        def _update_login_success(cookies, cookies_text, ua_var, ibex_var):
            """在主线程中更新登录成功的UI"""
            # 更新cookies显示框
            cookies_text.config(state="normal")
            cookies_text.delete("1.0", "end")
            cookies_text.insert("1.0", json.dumps(cookies, indent=2, ensure_ascii=False))
            cookies_text.config(state="disabled")

            self.login_instance.gener_user_agent()
            
            # 更新User Agent和ibex显示
            ua_var.set(self.login_instance.user_agent)
            ibex_var.set(self.login_instance.gener_ibex_over(str(int(time.time() * 1000))))
            
            self.status_label.config(text="登录成功", foreground="green")
        
        # 修改登录按钮的绑定
        ttk.Button(form_frame, text="登录", style="Accent.TButton",
                command=lambda: login(phone_var, code_var, cookies_text, ua_var, ibex_var)
        ).grid(row=2, column=0, columnspan=3, pady=10)
        
        # 配置网格布局
        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_columnconfigure(2, weight=1)
        form_frame.grid_rowconfigure(4, weight=1)
        
        # Cookies和设备信息显示区域（同一行）
        info_frame = ttk.LabelFrame(form_frame, text="Cookies和设备信息:")
        info_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)

        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_columnconfigure(1, weight=1)
        
        # 左侧Cookies显示区域
        cookies_label = ttk.Label(info_frame, text="Cookies:")
        cookies_label.grid(row=0, column=0, sticky="w")
        
        cookies_text = tk.Text(info_frame, height=5, font=self.default_font, state="disabled")
        cookies_text.grid(row=1, column=0, sticky="nsew", padx=5)
        
        # 右侧设备信息显示区域
        device_label = ttk.Label(info_frame, text="设备信息:")
        device_label.grid(row=0, column=1, sticky="w")
        
        device_text = tk.Text(info_frame, height=10, font=self.default_font, state="disabled")
        device_text.grid(row=1, column=1, sticky="nsew", padx=5)

        # User Agent显示
        ttk.Label(form_frame, text="User Agent:").grid(row=4, column=0, sticky="w", pady=5)
        ua_var = tk.StringVar()
        ua_entry = ttk.Entry(form_frame, textvariable=ua_var, style="Custom.TEntry", state="readonly")
        ua_entry.grid(row=4, column=1, sticky="w", pady=5)

        # ibex显示
        ttk.Label(form_frame, text="ibex:").grid(row=5, column=0, sticky="w", pady=5)
        ibex_var = tk.StringVar()
        ibex_entry = ttk.Entry(form_frame, textvariable=ibex_var, style="Custom.TEntry", state="readonly")
        ibex_entry.grid(row=5, column=1, sticky="w", pady=5)
        
        # 按钮框架
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, sticky="e", pady=10)

        def load_existing_data():
            # 加载cookies
            cookies_data = self.get_user_cookies(username)
            if cookies_data:
                cookies_text.config(state="normal")
                cookies_text.delete("1.0", "end")
                cookies_text.insert("1.0", json.dumps(cookies_data, indent=2, ensure_ascii=False))
                cookies_text.config(state="disabled")
            else:
                # 使用默认模板
                cookies_text.config(state="normal")
                cookies_text.delete("1.0", "end")
                cookies_text.insert("1.0", json.dumps(self.__class__.DEFAULT_COOKIES_TEMPLATE, indent=2, ensure_ascii=False))
                cookies_text.config(state="disabled")
            
            # 加载设备信息
            device_file = f"login_phone_{username}.json"
            if os.path.exists(device_file):
                try:
                    with open(device_file, 'r', encoding='utf-8') as f:
                        device_data = json.load(f)
                    device_text.config(state="normal")
                    device_text.delete("1.0", "end")
                    device_text.insert("1.0", json.dumps(device_data, indent=2, ensure_ascii=False))
                    device_text.config(state="disabled")
                except Exception:
                    pass

            # 加载UA和ibex
            user = next((u for u in self.users_data if u["username"] == username), None)
            if user:
                ua_var.set(user.get("user_agent", ""))
                ibex_var.set(user.get("ibex", ""))

        # 在创建对话框后立即加载数据
        dialog.after(100, load_existing_data)
        
        def save_login_data():
            # 保存cookies和设备信息
            cookies_str = cookies_text.get("1.0", "end-1c")
            device_str = device_text.get("1.0", "end-1c")
            
            # 处理Cookies - 为空时使用默认模板
            if not cookies_str:
                cookies_data = self.__class__.DEFAULT_COOKIES_TEMPLATE
            else:
                try:
                    cookies_data = json.loads(cookies_str)
                except json.JSONDecodeError as e:
                    messagebox.showerror("错误", f"JSON格式错误：{str(e)}")
                    return
            
            # 保存cookies到cookies/用户名.json
            cookies_file = f"cookies/{username}.json"
            try:
                with open(cookies_file, 'w', encoding='utf-8') as f:
                    json.dump(cookies_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                messagebox.showerror("错误", f"无法保存Cookies文件：{str(e)}")
                return
            
            # 仅当设备信息非空时保存
            if device_str:
                try:
                    device_data = json.loads(device_str)
                    with open(f"login_phone_{username}.json", 'w', encoding='utf-8') as f:
                        json.dump(device_data, f, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    messagebox.showerror("错误", f"设备信息JSON格式错误：{str(e)}")
                    return
                except Exception as e:
                    messagebox.showerror("错误", f"无法保存设备信息：{str(e)}")
                    return
            
            # 保存用户信息到config
            cookies_file = f"cookies/{username}.json"
            self.save_user_to_config(username, ua_var.get(), ibex_var.get(), cookies_file)
            
            messagebox.showinfo("成功", "数据保存成功")
            dialog.destroy()
        
        ttk.Button(btn_frame, text="保存", style="Accent.TButton",
                command=save_login_data).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="取消", style="Accent.TButton",
                command=dialog.destroy).pack(side="left", padx=5)
        
    def login_password(self, account, password):
        """账号密码登录函数（待实现）"""
        # TODO: 实现登录逻辑
        # 返回False表示失败，返回cookies的JSON数据表示成功
        return False

    def show_password_login_dialog(self, parent, username):
        """显示账号密码登录对话框"""
        # 验证用户名
        is_valid, message = self.validate_username(username)
        if not is_valid:
            messagebox.showerror("错误", message)
            return
        
        # 新增：检查设备信息文件是否存在
        device_file = f"login_phone_{username}.json"
        if not os.path.exists(device_file):
            messagebox.showerror("错误", f"login_phone_{username}.json不存在\n本功能用于便捷更新过期cookies，需要先进行手机验证码成功登录后才能使用")
            return
        
        # 检测设备信息文件是否为空
        if os.path.getsize(device_file) == 0:
            messagebox.showerror("错误", f"login_phone_{username}.json内容为空\n本功能用于便捷更新过期cookies，需要先进行手机验证码成功登录后才能使用")
            return
        
        loginpage_width = self.resolution_set.get("loginpage_width")
        loginpage_height = self.resolution_set.get("loginpage_height")
        
        dialog = tk.Toplevel(parent)
        dialog.title("账号密码登录")
        if loginpage_width and loginpage_height:
            dialog.geometry(f"{loginpage_width}x{loginpage_height}")
        else:
            dialog.geometry("800x650")
        # dialog.geometry("800x650")

        # 关键模态设置
        dialog.transient(parent)
        dialog.grab_set()
        dialog.focus_set()
        dialog.lift()
        
        form_frame = ttk.Frame(dialog, padding="20 15 20 15")
        form_frame.pack(fill="both", expand=True)
        
        # 账号输入
        ttk.Label(form_frame, text="账号:").grid(row=0, column=0, sticky="w", pady=5)
        account_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=account_var, style="Custom.TEntry", width=20).grid(row=0, column=1, sticky="w", pady=5)
        
        # 密码输入
        ttk.Label(form_frame, text="密码:").grid(row=1, column=0, sticky="w", pady=5)
        password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=password_var, style="Custom.TEntry", show="*", width=20).grid(row=1, column=1, sticky="w", pady=5)

        # 在创建对话框的底部添加状态提示区域（在原有代码基础上添加）
        status_frame = ttk.Frame(form_frame)
        status_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

        self.status_label = ttk.Label(status_frame, text="", font=self.default_font)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_rowconfigure(0, weight=1)
        self.status_label.pack(side="left", padx=5)

        # # 获取设备信息按钮
        # def get_device_info():
        #     # 调用getdevice函数
        #     device_data = self.getdevice()
        #     if device_data:
        #         # 更新设备信息显示框
        #         device_text.config(state="normal")
        #         device_text.delete("1.0", "end")
        #         device_text.insert("1.0", json.dumps(device_data, indent=2, ensure_ascii=False))
        #         device_text.config(state="disabled")
        
        # ttk.Button(form_frame, text="获取随机设备信息", style="Accent.TButton",
        #         command=get_device_info).grid(row=1, column=2, sticky="w", padx=5, pady=5)
        
        # 登录按钮
        def login():
            device_info = device_text.get("1.0", "end-1c").strip()
            if not device_info:
                messagebox.showerror("错误", "设备信息为空，请先使用手机验证码登录成功并保存设备信息")
                return

            account = account_var.get().strip()
            password = password_var.get().strip()
            if not account or not password:
                messagebox.showerror("错误", "账号和密码不能为空")
                return
            
            # 尝试解析设备信息JSON
            try:
                login_phone = json.loads(device_info)
            except json.JSONDecodeError:
                messagebox.showerror("错误", "设备信息格式错误，请重新获取设备信息")
                return
            
            self.login_instance = QDLogin_Password(account=account, password=password)

            if not self.login_instance.init_device_info(login_phone):
                messagebox.showerror("错误", "设备信息初始化失败")
                return
            
            # 显示加载状态
            self.status_label.config(text="登录中……", foreground="blue")

            # 在新线程中执行网络请求
            def login_thread():
                try:
                    # 创建登录实例
                    self.login_instance = QDLogin_Password(account=account, password=password)
                    
                    # 检查设备信息文件
                    device_file = f"login_phone_{username}.json"
                    if not os.path.exists(device_file) or os.path.getsize(device_file) == 0:
                        self.root.after(0, lambda: messagebox.showerror("错误", "设备信息文件不存在或为空"))
                        return
                    
                    # 读取设备信息
                    with open(device_file, 'r') as f:
                        login_phone = json.load(f)
                    
                    if not self.login_instance.init_device_info(login_phone):
                        self.root.after(0, lambda: messagebox.showerror("错误", "设备信息初始化失败"))
                        return
                    
                    # 尝试静态登录
                    status, data = self.login_instance.static_login()
                    
                    # 处理需要图形验证码的情况
                    if status == 'captcha':
                        self.session_key = data
                        self.root.after(0, lambda: self.status_label.config(
                            text="需要图形验证码，请稍候...", foreground="blue"))
                        
                        # 关键：在主线程中调用get_captcha
                        captcha_data = None
                        event = threading.Event()
                        
                        def get_captcha_in_main_thread():
                            nonlocal captcha_data
                            captcha_data = self.login_instance.get_captcha()
                            event.set()  # 通知子线程继续
                        
                        self.root.after(0, get_captcha_in_main_thread)
                        
                        # 等待主线程完成get_captcha
                        event.wait()
                        
                        if not captcha_data:
                            self.root.after(0, lambda: self.status_label.config(
                                text="获取图形验证码失败", foreground="red"))
                            return
                        
                        # 使用图形验证码重新登录
                        status, data = self.login_instance.login_with_captcha(
                            self.session_key,
                            captcha_data['randstr'],
                            captcha_data['ticket']
                        )
                        
                        if status in [True, 'True']:
                            self.session_key = data
                            self.root.after(0, lambda: self.status_label.config(
                                text="登录成功", foreground="green"))
                        else:
                            self.root.after(0, lambda: self.status_label.config(
                                text=f"图形验证码校验失败: {data}", foreground="red"))
                            return
                    
                    elif status in [True, 'True']:
                        self.session_key = data
                        self.root.after(0, lambda: self.status_label.config(
                            text="登录成功", foreground="green"))
                    else:
                        self.root.after(0, lambda: self.status_label.config(
                            text=f"登录失败: {data}", foreground="red"))
                        return
                    
                    # 完成登录
                    status = self.login_instance.login_druidv6()
                    if not status:
                        self.root.after(0, lambda: self.status_label.config(
                            text="登录druidv6.if.qidian.com失败", foreground="red"))
                        return
                    
                    # 获取cookies
                    cookies = self.login_instance.cookies
                    
                    # 通过主线程更新UI
                    def update_ui():
                        # 更新cookies显示框
                        cookies_text.config(state="normal")
                        cookies_text.delete("1.0", "end")
                        cookies_text.insert("1.0", json.dumps(cookies, indent=2, ensure_ascii=False))
                        cookies_text.config(state="disabled")
                        
                        self.login_instance.gener_user_agent()
                        
                        # 更新User Agent和ibex显示
                        ua_var.set(self.login_instance.user_agent)
                        ibex_var.set(self.login_instance.gener_ibex_over(str(int(time.time() * 1000))))
                        
                        self.status_label.config(text="登录成功", foreground="green")
                    
                    self.root.after(0, update_ui)
                    
                except Exception as e:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"登录过程中出错: {str(e)}", foreground="red"))
            
            # 启动子线程
            threading.Thread(target=login_thread, daemon=True).start()
        
        ttk.Button(form_frame, text="登录", style="Accent.TButton",
                command=login).grid(row=2, column=0, columnspan=3, pady=10)
        
        # 配置网格布局
        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_columnconfigure(2, weight=1)
        form_frame.grid_rowconfigure(4, weight=1)
        
        # Cookies和设备信息显示区域（同一行）
        info_frame = ttk.LabelFrame(form_frame, text="Cookies和设备信息:")
        info_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)

        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_columnconfigure(1, weight=1)
        
        # 左侧Cookies显示区域
        cookies_label = ttk.Label(info_frame, text="Cookies:")
        cookies_label.grid(row=0, column=0, sticky="w")
        
        cookies_text = tk.Text(info_frame, height=5, font=self.default_font, state="disabled")
        cookies_text.grid(row=1, column=0, sticky="nsew", padx=5)
        
        # 右侧设备信息显示区域
        device_label = ttk.Label(info_frame, text="设备信息:")
        device_label.grid(row=0, column=1, sticky="w")
        
        device_text = tk.Text(info_frame, height=10, font=self.default_font, state="disabled")
        device_text.grid(row=1, column=1, sticky="nsew", padx=5)

        # User Agent输入
        ttk.Label(form_frame, text="User Agent:").grid(row=4, column=0, sticky="w", pady=5)
        ua_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=ua_var, style="Custom.TEntry", state="readonly").grid(
            row=4, column=1, sticky="ew", pady=5)

        # ibex输入
        ttk.Label(form_frame, text="ibex:").grid(row=5, column=0, sticky="w", pady=5)
        ibex_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=ibex_var, style="Custom.TEntry", state="readonly").grid(
            row=5, column=1, sticky="ew", pady=5)
        
        # 按钮框架
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, sticky="e", pady=10)

        def load_existing_data():
            # 加载cookies
            cookies_data = self.get_user_cookies(username)
            if cookies_data:
                cookies_text.config(state="normal")
                cookies_text.delete("1.0", "end")
                cookies_text.insert("1.0", json.dumps(cookies_data, indent=2, ensure_ascii=False))
                cookies_text.config(state="disabled")
            else:
                # 使用默认模板
                cookies_text.config(state="normal")
                cookies_text.delete("1.0", "end")
                cookies_text.insert("1.0", json.dumps(self.__class__.DEFAULT_COOKIES_TEMPLATE, indent=2, ensure_ascii=False))
                cookies_text.config(state="disabled")
            
            # 加载设备信息
            device_file = f"login_phone_{username}.json"
            if os.path.exists(device_file):
                try:
                    with open(device_file, 'r', encoding='utf-8') as f:
                        device_data = json.load(f)
                    device_text.config(state="normal")
                    device_text.delete("1.0", "end")
                    device_text.insert("1.0", json.dumps(device_data, indent=2, ensure_ascii=False))
                    device_text.config(state="disabled")
                except Exception:
                    pass

            # 加载UA和ibex
            user = next((u for u in self.users_data if u["username"] == username), None)
            if user:
                ua_var.set(user.get("user_agent", ""))
                ibex_var.set(user.get("ibex", ""))

        # 在创建对话框后立即加载数据
        dialog.after(100, load_existing_data)
        
        def save_login_data():
            # 保存cookies和设备信息
            cookies_str = cookies_text.get("1.0", "end-1c")
            device_str = device_text.get("1.0", "end-1c")
            
            # 处理Cookies - 为空时使用默认模板
            if not cookies_str:
                cookies_data = self.__class__.DEFAULT_COOKIES_TEMPLATE
            else:
                try:
                    cookies_data = json.loads(cookies_str)
                except json.JSONDecodeError as e:
                    messagebox.showerror("错误", f"JSON格式错误：{str(e)}")
                    return
            
            # 保存cookies到cookies/用户名.json
            cookies_file = f"cookies/{username}.json"
            try:
                with open(cookies_file, 'w', encoding='utf-8') as f:
                    json.dump(cookies_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                messagebox.showerror("错误", f"无法保存Cookies文件：{str(e)}")
                return
            
            # 仅当设备信息非空时保存
            if device_str:
                try:
                    device_data = json.loads(device_str)
                    with open(f"login_phone_{username}.json", 'w', encoding='utf-8') as f:
                        json.dump(device_data, f, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    messagebox.showerror("错误", f"设备信息JSON格式错误：{str(e)}")
                    return
                except Exception as e:
                    messagebox.showerror("错误", f"无法保存设备信息：{str(e)}")
                    return
                
            # 保存用户信息到config
            cookies_file = f"cookies/{username}.json"
            self.save_user_to_config(username, ua_var.get(), ibex_var.get(), cookies_file)
            
            messagebox.showinfo("成功", "数据保存成功")
            dialog.destroy()
        
        ttk.Button(btn_frame, text="保存", style="Accent.TButton",
                command=save_login_data).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="取消", style="Accent.TButton",
                command=dialog.destroy).pack(side="left", padx=5)
    
    def show_manual_cookies_dialog(self, parent, username):
        """显示手动输入cookies对话框"""
        # 验证用户名
        is_valid, message = self.validate_username(username)
        if not is_valid:
            messagebox.showerror("错误", message)
            return
        
        loginpage_width = self.resolution_set.get("loginpage_width")
        loginpage_height = self.resolution_set.get("loginpage_height")
        
        dialog = tk.Toplevel(parent)
        dialog.title("手动输入Cookies")
        if loginpage_width and loginpage_height:
            dialog.geometry(f"{loginpage_width}x{loginpage_height}")
        else:
            dialog.geometry("800x500")
        # dialog.geometry("800x500")

        # 关键模态设置
        dialog.transient(parent)
        dialog.grab_set()
        dialog.focus_set()
        dialog.lift()
        
        # 创建主框架并使用grid布局
        form_frame = ttk.Frame(dialog, padding="20 15 20 15")
        form_frame.grid(row=0, column=0, sticky="nsew")
        dialog.grid_rowconfigure(0, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        
        # 配置网格权重 - 关键修改
        form_frame.grid_rowconfigure(2, weight=1)  # cookies区域可拉伸
        form_frame.grid_columnconfigure(0, weight=0)  # 标签列不拉伸
        form_frame.grid_columnconfigure(1, weight=1)  # 输入框列可拉伸

         # User Agent输入
        ttk.Label(form_frame, text="User Agent:").grid(row=0, column=0, sticky="w", pady=5)
        ua_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=ua_var, style="Custom.TEntry").grid(
            row=0, column=1, sticky="ew", pady=5, padx=(5, 0))  # 修复间距问题
        
        # ibex输入
        ttk.Label(form_frame, text="ibex:").grid(row=1, column=0, sticky="w", pady=5)
        ibex_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=ibex_var, style="Custom.TEntry").grid(
            row=1, column=1, sticky="ew", pady=5, padx=(5, 0))  # 修复间距问题
        
        # 获取已有cookies
        cookies_data = self.get_user_cookies(username)
        if not cookies_data:
            cookies_data = self.__class__.DEFAULT_COOKIES_TEMPLATE
        
        # 创建带转换功能的Cookies配置区域
        converter_frame, cookies_text = self.create_cookies_converter(
            form_frame, 
            default_content= self.__class__.DEFAULT_COOKIES_TEMPLATE
        )
        converter_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        
        # 按钮框架 - 使用grid布局
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="e", pady=10)

        def load_existing_data():
            # 加载cookies
            cookies_data = self.get_user_cookies(username)
            if cookies_data:
                cookies_text.config(state="normal")
                cookies_text.delete("1.0", "end")
                cookies_text.insert("1.0", json.dumps(cookies_data, indent=2, ensure_ascii=False))
                # cookies_text.config(state="disabled")
            else:
                # 使用默认模板
                cookies_text.config(state="normal")
                cookies_text.delete("1.0", "end")
                cookies_text.insert("1.0", json.dumps(self.__class__.DEFAULT_COOKIES_TEMPLATE, indent=2, ensure_ascii=False))
                # cookies_text.config(state="disabled")
            
            # 加载UA和ibex
            user = next((u for u in self.users_data if u["username"] == username), None)
            if user:
                ua_var.set(user.get("user_agent", ""))
                ibex_var.set(user.get("ibex", ""))

        # 在创建对话框后立即加载数据
        dialog.after(100, load_existing_data)
    
        def save_cookies():
            """保存cookies"""
            cookies_str = cookies_text.get("1.0", "end-1c")
            
            # 处理Cookies - 为空时使用默认模板
            if not cookies_str:
                cookies_data = self.__class__.DEFAULT_COOKIES_TEMPLATE
            else:
                try:
                    cookies_data = json.loads(cookies_str)
                except json.JSONDecodeError as e:
                    messagebox.showerror("错误", f"JSON格式错误：{str(e)}")
                    return
            
            # 如果cookies文件夹不存在，则创建
            if not os.path.exists("cookies"):
                os.makedirs("cookies")
            
            # 保存cookies到cookies/用户名.json
            cookies_file = f"cookies/{username}.json"
            try:
                with open(cookies_file, 'w', encoding='utf-8') as f:
                    json.dump(cookies_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                messagebox.showerror("错误", f"无法保存Cookies文件：{str(e)}")
                return
            
            # 保存用户信息到config
            cookies_file = f"cookies/{username}.json"
            self.save_user_to_config(username, ua_var.get(), ibex_var.get(), cookies_file)
                    
            messagebox.showinfo("成功", "Cookies保存成功")
            dialog.destroy()
        
        # 使用grid布局放置按钮
        ttk.Button(btn_frame, text="保存", style="Accent.TButton",
                command=save_cookies).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="取消", style="Accent.TButton",
                command=dialog.destroy).grid(row=0, column=1, padx=5)

    def add_user(self):
        """添加用户对话框"""
        if len(self.users_data) >= self.__class__.MAX_USERS:
            messagebox.showerror("错误", f"最多只能添加{self.__class__.MAX_USERS}个用户")
            return
                
        userpage_width = self.resolution_set.get("userpage_width")
        userpage_height = self.resolution_set.get("userpage_height")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("添加用户")
        # dialog.geometry("800x780")
        if userpage_width and userpage_height:
            dialog.geometry(f"{userpage_width}x{userpage_height}")
        else:
            dialog.geometry("800x780")

        dialog.transient(self.root)  # 新增：设置为临时窗口
        dialog.grab_set()  # 新增：模态对话框
        
        form_frame = ttk.Frame(dialog, padding="20 15 20 15")
        form_frame.grid_columnconfigure(1, weight=1)  # 主内容列扩展
        form_frame.grid_columnconfigure(2, weight=0)  # 帮助提示列不扩展
        form_frame.pack(fill="both", expand=True)
        
        # ====用户名输入====
        ttk.Label(form_frame, text="用户名:").grid(row=0, column=0, sticky="w")
        username_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=username_var, style="Custom.TEntry").grid(
            row=0, column=1, sticky="ew", padx=5)
        
        # 用户名格式提示
        ttk.Label(form_frame, text="* 2-20位，仅支持中文、字母、数字和下划线", 
                style="Help.TLabel").grid(row=0, column=2, sticky="w")
        
        # ====usertype输入====
        ttk.Label(form_frame, text="用户类型:").grid(row=3, column=0, sticky="w")
        usertype_var = tk.StringVar(value="captcha")
        ttk.Combobox(form_frame, textvariable=usertype_var, 
                    values=["captcha"],
                    state="readonly", width=15).grid(
            row=3, column=1, sticky="w", padx=5)
        ttk.Label(form_frame, text="* 用户类型，固定为captcha", 
                style="Help.TLabel").grid(row=3, column=2, sticky="w")

        # ====tokenid输入====
        ttk.Label(form_frame, text="tokenid:").grid(row=4, column=0, sticky="w")
        tokenid_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=tokenid_var, style="Custom.TEntry").grid(
            row=4, column=1, sticky="ew", padx=5)
        ttk.Label(form_frame, text="* 用于自动过图形验证，可在我的网站或者咸鱼上获取", 
                style="Help.TLabel").grid(row=4, column=2, sticky="w")
        
        # ====登录方式选择====
        login_frame = ttk.LabelFrame(form_frame, text="登录方式")
        login_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)

        ttk.Button(login_frame, text="手机验证码登录", style="Accent.TButton",
                command=lambda: self.show_phone_login_dialog(dialog, username_var.get())).pack(fill="x", pady=2)
        ttk.Button(login_frame, text="账号密码登录", style="Accent.TButton",
                command=lambda: self.show_password_login_dialog(dialog, username_var.get())).pack(fill="x", pady=2)
        ttk.Button(login_frame, text="手动输入cookies", style="Accent.TButton",
                command=lambda: self.show_manual_cookies_dialog(dialog, username_var.get())).pack(fill="x", pady=2)


        # ====任务配置====
        task_frame = ttk.LabelFrame(form_frame, text="默认任务配置")
        task_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)
        
        task_vars = {}
        tasks = ["签到任务", "激励碎片任务", "章节卡任务", "游戏中心任务", "每日抽奖任务", "每周自动兑换章节卡", "章节卡信息推送"]
        for i, task in enumerate(tasks):
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(task_frame, text=task, variable=var).grid(
                row=i//3, column=i%3, sticky="w", padx=10, pady=5)
            task_vars[task] = var
        
        # 新增阅读时长上报任务（第3行第0列）
        readtime_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(task_frame, text="阅读时长上报", variable=readtime_var).grid(
            row=2, column=0, sticky="w", padx=10, pady=5)
        task_vars["阅读时长上报"] = readtime_var

        # 配置按钮（第3行第1列）
        readtime_config_var = {}  # 临时存储配置，保存时存入用户数据
        ttk.Button(task_frame, text="配置", style="Accent.TButton",
                command=lambda: self._edit_readtime_config(dialog, username_var.get(), readtime_config_var)
                ).grid(row=2, column=1, sticky="w", padx=5)

        # ====推送服务配置====
        push_frame = ttk.LabelFrame(form_frame, text="推送服务")
        push_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)
        
        # 推送服务列表
        push_columns = ("type", "title")
        push_list = ttk.Treeview(push_frame, columns=push_columns, show="headings", height=5)
        push_list.heading("type", text="类型")
        push_list.heading("title", text="配置名称")
        push_list.column("type", width=100)
        push_list.column("title", width=300)
        push_list.pack(side="left", fill="both", expand=True)

        # 推送服务操作按钮
        push_btn_frame = ttk.Frame(push_frame)
        push_btn_frame.pack(side="right", fill="y", padx=5)
        
        push_services = []

        def add_push_service():
            """添加推送服务配置"""
            pushpage_width = self.resolution_set.get("pushpage_width")
            pushpage_height = self.resolution_set.get("pushpage_height")

            push_dialog = tk.Toplevel(dialog)
            push_dialog.title("添加推送服务")
            if pushpage_width and pushpage_height:
                push_dialog.geometry(f"{pushpage_width}x{pushpage_height}")
            else:
                push_dialog.geometry("400x250")
            # push_dialog.geometry("400x250")
            
            push_form = ttk.Frame(push_dialog, padding="15 10 15 10")
            push_form.pack(fill="both", expand=True)
            push_form.grid_rowconfigure(1, weight=1)  # 第1行可扩展
            push_form.grid_columnconfigure(1, weight=1)  # 第1列可扩展
            
            # 类型选择
            ttk.Label(push_form, text="类型:").grid(row=0, column=0, sticky="w")
            service_type = tk.StringVar()
            ttk.Combobox(push_form, textvariable=service_type,values=["feishu", "serverchan", "qiwei", "pushplus"],
                        state="readonly",width=15, font=self.default_font).grid(row=0, column=1, sticky="w")

            # 飞书配置区域
            feishu_frame = ttk.Frame(push_form)
            feishu_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
            
            # Webhook URL行（可扩展）
            ttk.Label(feishu_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            feishu_url = ttk.Entry(feishu_frame)
            feishu_url.grid(row=0, column=1, sticky="ew", padx=5)
            feishu_frame.grid_columnconfigure(1, weight=1)
            
            ttk.Label(feishu_frame, text="是否有签名校验:").grid(row=1, column=0, sticky="w")
            has_sign = tk.BooleanVar()
            ttk.Checkbutton(feishu_frame, variable=has_sign, 
                        command=lambda: toggle_secret(secret_frame, has_sign.get())).grid(
                        row=1, column=1, sticky="w")
            
            # Secret行
            secret_frame = ttk.Frame(feishu_frame)
            ttk.Label(secret_frame, text="密钥:").grid(row=0, column=0, sticky="w")
            secret_entry = ttk.Entry(secret_frame)
            secret_entry.grid(row=0, column=1, sticky="ew", padx=5)
            secret_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
            secret_frame.grid_columnconfigure(1, weight=1)  # 允许Secret输入框扩展
            secret_frame.grid_remove()

            # ServerChan配置区域
            server_frame = ttk.Frame(push_form)
            ttk.Label(server_frame, text="SCKEY:").grid(row=0, column=0, sticky="w")
            sckey_entry = ttk.Entry(server_frame)
            sckey_entry.grid(row=0, column=1, sticky="ew")
            server_frame.grid_columnconfigure(1, weight=1)

            # Qiwei配置区域
            qiwei_frame = ttk.Frame(push_form)
            ttk.Label(qiwei_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            qiwei_url = ttk.Entry(qiwei_frame)
            qiwei_url.grid(row=0, column=1, sticky="ew", padx=8)
            qiwei_frame.grid_columnconfigure(0, minsize=250)
            qiwei_frame.grid_columnconfigure(1, weight=1)

            # 添加提示信息
            ttk.Label(qiwei_frame, text="下面二者选择一种方式填写即可，也可以都填或不填", 
                    style="Help.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
            ttk.Label(qiwei_frame, text="输入后点击+添加到列表", 
                    style="Help.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))

            # 用户ID列表配置
            ttk.Label(qiwei_frame, text="用户ID列表:").grid(row=3, column=0, sticky="w", pady=(5, 0))
            userids_frame = ttk.Frame(qiwei_frame)
            userids_frame.grid(row=3, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="通过特殊方式获取的userid\n如果不懂，请选择手机号方式填写\n(@all代表@全体)", 
                    style="Help.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 0), columnspan=2)

            userids_entry = ttk.Entry(userids_frame)
            userids_entry.pack(side="left", fill="x", expand=True)

            def add_userid():
                """添加用户ID到列表"""
                userid = userids_entry.get().strip()
                if userid:
                    userids_listbox.insert("end", userid)
                    userids_entry.delete(0, "end")

            ttk.Button(userids_frame, text="+", command=add_userid, width=3).pack(side="left", padx=(5, 0))

            # 用户ID列表显示
            userids_listbox = tk.Listbox(qiwei_frame, height=5)
            userids_listbox.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除用户ID按钮
            ttk.Button(qiwei_frame, text="删除选中用户ID", 
                    command=lambda: userids_listbox.delete(tk.ANCHOR)).grid(
                row=5, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # 手机号列表配置
            ttk.Label(qiwei_frame, text="手机号列表:").grid(row=6, column=0, sticky="w", pady=(5, 0))
            phoneids_frame = ttk.Frame(qiwei_frame)
            phoneids_frame.grid(row=6, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="请输入11位手机号", 
                    style="Help.TLabel").grid(row=7, column=0, sticky="w", pady=(10, 0), columnspan=2)

            phoneids_entry = ttk.Entry(phoneids_frame)
            phoneids_entry.pack(side="left", fill="x", expand=True)

            def add_phoneid():
                """添加手机号到列表，带格式验证"""
                phoneid = phoneids_entry.get().strip()
                if phoneid:
                    # 验证手机号格式（简单验证）
                    if re.match(r'^1[3-9]\d{9}$', phoneid):
                        phoneids_listbox.insert("end", phoneid)
                        phoneids_entry.delete(0, "end")
                    else:
                        messagebox.showwarning("警告", "手机号格式不正确")

            ttk.Button(phoneids_frame, text="+", command=add_phoneid, width=3).pack(side="left", padx=(5, 0))

            # 手机号列表显示
            phoneids_listbox = tk.Listbox(qiwei_frame, height=5)
            phoneids_listbox.grid(row=7, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除手机号按钮
            ttk.Button(qiwei_frame, text="删除选中手机号", 
                    command=lambda: phoneids_listbox.delete(tk.ANCHOR)).grid(
                row=8, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # PushPlus配置区域
            pushplus_frame = ttk.Frame(push_form)
            ttk.Label(pushplus_frame, text="Token:").grid(row=0, column=0, sticky="w")
            token_entry = ttk.Entry(pushplus_frame)
            token_entry.grid(row=0, column=1, sticky="ew")
            ttk.Label(pushplus_frame, text="群组id(不填只发给自己):").grid(row=1, column=0, sticky="w")
            topic_entry = ttk.Entry(pushplus_frame)
            topic_entry.grid(row=1, column=1, sticky="ew")
            pushplus_frame.grid_rowconfigure(1, weight=1)
            pushplus_frame.grid_columnconfigure(1, weight=1)

            # 类型切换处理
            def update_config_fields(*args):
                if service_type.get() == "feishu":
                    feishu_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                    server_frame.grid_remove()
                    qiwei_frame.grid_remove()
                    pushplus_frame.grid_remove()
                elif service_type.get() == "serverchan":
                    feishu_frame.grid_remove()
                    server_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                    qiwei_frame.grid_remove()
                    pushplus_frame.grid_remove()
                elif service_type.get() == "qiwei":
                    feishu_frame.grid_remove()
                    server_frame.grid_remove()
                    qiwei_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                    pushplus_frame.grid_remove()
                elif service_type.get() == "pushplus":
                    feishu_frame.grid_remove()
                    server_frame.grid_remove()
                    qiwei_frame.grid_remove()
                    pushplus_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
            
            service_type.trace_add("write", update_config_fields)
            update_config_fields()  # 初始化显示

            def save_push_service():
                """保存推送服务配置"""
                service_type_val = service_type.get()
                
                if service_type_val == "feishu":
                    url = feishu_url.get()
                    if not url:
                        messagebox.showerror("错误", "飞书Webhook URL不能为空")
                        return
                    
                    service = {
                        "type": "feishu",
                        "webhook_url": url,
                        "havesign": has_sign.get(),
                        "title": f"飞书推送 - {url[-20:]}"  # 简短显示
                    }
                    
                    if has_sign.get():
                        secret = secret_entry.get()
                        if not secret:
                            messagebox.showerror("错误", "签名模式必须填写密钥")
                            return
                        service["secret"] = secret
                        
                elif service_type_val == "serverchan":  # serverchan
                    sckey = sckey_entry.get()
                    if not sckey:
                        messagebox.showerror("错误", "ServerChan SCKEY不能为空")
                        return
                        
                    service = {
                        "type": "serverchan",
                        "sckey": sckey,
                        "title": f"Server酱 - {sckey[-20:]}"
                    }
                
                elif service_type_val == "qiwei":
                    url = qiwei_url.get()
                    if not url:
                        messagebox.showerror("错误", "QiWei Webhook URL不能为空")
                        return
                    
                    # 收集userids和phoneids
                    userids = [userids_listbox.get(i) for i in range(userids_listbox.size())]
                    phoneids = [phoneids_listbox.get(i) for i in range(phoneids_listbox.size())]
                    
                    service = {
                        "type": "qiwei",
                        "webhook_url": url,
                        "userids": userids,  # 保存为字符串列表
                        "phoneids": phoneids,  # 保存为字符串列表
                        "title": f"企业微信 - {url[-20:]}"
                    }

                elif service_type_val == "pushplus":
                    token = token_entry.get()
                    if not token:
                        messagebox.showerror("错误", "PushPlus Token不能为空")
                        return
                    
                    service = {
                        "type": "pushplus",
                        "token": token,
                        "topic": topic_entry.get(),
                        "title": f"PushPlus - {token[-20:]}"
                    }
                
                else: 
                    messagebox.showerror("错误", "未知的推送服务类型")
                    return
                    
                push_services.append(service)
                push_list.insert("", "end", values=(service["type"], service["title"]))
                push_dialog.destroy()
            
            # 创建按钮框架并使用grid布局
            btn_frame = ttk.Frame(push_dialog)
            btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)  # 固定在底部

            # 保存按钮
            ttk.Button(btn_frame, 
                    text="保存", 
                    style="Accent.TButton",
                    command=save_push_service).pack(side="left", expand=True, fill="x", padx=5)

            # 取消按钮
            ttk.Button(btn_frame, 
                    text="取消", 
                    style="Accent.TButton",
                    command=push_dialog.destroy).pack(side="right", expand=True, fill="x", padx=5)
        def toggle_secret(frame, show):
            """控制Secret输入框显示"""
            if show:
                frame.grid(row=2, column=0, columnspan=2, sticky="ew")  # 固定行号和跨列
            else:
                frame.grid_remove()

        # 推送服务列表滚动条
        push_scrollbar = ttk.Scrollbar(push_frame, orient="vertical", command=push_list.yview)
        push_scrollbar.pack(side="right", fill="y")
        push_list.configure(yscrollcommand=push_scrollbar.set)

        # 推送服务操作按钮
        ttk.Button(push_btn_frame, text="添加", style="Accent.TButton",
                command=add_push_service).pack(fill="x", pady=2)
        ttk.Button(push_btn_frame, text="编辑", style="Accent.TButton",
                command=lambda: edit_push_service(push_list)).pack(fill="x", pady=2)
        ttk.Button(push_btn_frame, text="删除", style="Accent.TButton",
                command=lambda: delete_push_service(push_list)).pack(fill="x", pady=2)

        def edit_push_service(listbox):
            """编辑推送服务配置"""
            selected = listbox.selection()
            if not selected:
                messagebox.showwarning("警告", "请先选择一个推送服务")
                return
            
            if not push_services:
                messagebox.showwarning("警告", "推送服务列表为空")
                return
                
            index = listbox.index(selected[0])
            service = push_services[index]

            pushpage_width = self.resolution_set.get("pushpage_width")
            pushpage_height = self.resolution_set.get("pushpage_height")
            
            # 创建新的配置对话框进行编辑
            push_dialog = tk.Toplevel(dialog)
            push_dialog.title(f"编辑推送服务 - {service['type']}")
            if pushpage_width and pushpage_height:
                push_dialog.geometry(f"{pushpage_width}x{pushpage_height}")
            else:
                push_dialog.geometry("400x250")
            # push_dialog.geometry("400x250")
            
            push_form = ttk.Frame(push_dialog, padding="15 10 15 10")
            push_form.pack(fill="both", expand=True)
            push_form.grid_rowconfigure(1, weight=1)  # 第1行可扩展
            push_form.grid_columnconfigure(1, weight=1)  # 第1列可扩展
            
            # 类型选择（禁用修改）
            ttk.Label(push_form, text="类型:").grid(row=0, column=0, sticky="w")
            ttk.Label(push_form, text=service["type"]).grid(row=0, column=1, sticky="w")
            
            # 飞书配置区域
            feishu_frame = ttk.Frame(push_form)
            ttk.Label(feishu_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            feishu_url = ttk.Entry(feishu_frame)
            feishu_url.insert(0, service.get("webhook_url", ""))
            feishu_url.grid(row=0, column=1, sticky="ew")
            
            ttk.Label(feishu_frame, text="是否有签名校验:").grid(row=1, column=0, sticky="w")
            has_sign = tk.BooleanVar(value=service.get("havesign", False))
            ttk.Checkbutton(feishu_frame, variable=has_sign, 
                        command=lambda: toggle_secret(secret_frame, has_sign.get())).grid(
                        row=1, column=1, sticky="w")
            
            secret_frame = ttk.Frame(feishu_frame)
            ttk.Label(secret_frame, text="密钥:").grid(row=0, column=0, sticky="w")
            secret_entry = ttk.Entry(secret_frame)
            secret_entry.insert(0, service.get("secret", ""))
            secret_entry.grid(row=0, column=1, sticky="ew")
            if service.get("havesign", False):
                secret_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
            else:
                secret_frame.grid_remove()

            # ServerChan配置区域
            server_frame = ttk.Frame(push_form)
            ttk.Label(server_frame, text="SCKEY:").grid(row=0, column=0, sticky="w")
            sckey_entry = ttk.Entry(server_frame)
            sckey_entry.insert(0, service.get("sckey", ""))
            sckey_entry.grid(row=0, column=1, sticky="ew")

            # Qiwei配置区域
            qiwei_frame = ttk.Frame(push_form)
            ttk.Label(qiwei_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            qiwei_url = ttk.Entry(qiwei_frame)
            qiwei_url.insert(0, service.get("webhook_url", ""))
            qiwei_url.grid(row=0, column=1, sticky="ew", padx=5)
            qiwei_frame.grid_columnconfigure(0, minsize=250)
            qiwei_frame.grid_columnconfigure(1, weight=1)

            # 添加提示信息
            ttk.Label(qiwei_frame, text="下面二者选择一种方式填写即可，也可以都填或不填", 
                    style="Help.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
            ttk.Label(qiwei_frame, text="输入后点击+添加到列表", 
                    style="Help.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))

            # 用户ID列表配置
            ttk.Label(qiwei_frame, text="用户ID列表:").grid(row=3, column=0, sticky="w", pady=(5, 0))
            userids_frame = ttk.Frame(qiwei_frame)
            userids_frame.grid(row=3, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="通过特殊方式获取的userid\n如果不懂，请选择手机号方式填写\n(@all代表@全体)", 
                    style="Help.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 0), columnspan=4)

            userids_entry = ttk.Entry(userids_frame)
            userids_entry.pack(side="left", fill="x", expand=True)

            def add_userid():
                """添加用户ID到列表"""
                userid = userids_entry.get().strip()
                if userid:
                    userids_listbox.insert("end", userid)
                    userids_entry.delete(0, "end")

            ttk.Button(userids_frame, text="+", command=add_userid, width=3).pack(side="left", padx=(5, 0))

            # 用户ID列表显示
            userids_listbox = tk.Listbox(qiwei_frame, height=5)
            userids_listbox.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除用户ID按钮
            ttk.Button(qiwei_frame, text="删除选中用户ID", 
                    command=lambda: userids_listbox.delete(tk.ANCHOR)).grid(
                row=5, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # 手机号列表配置
            ttk.Label(qiwei_frame, text="手机号列表:").grid(row=6, column=0, sticky="w", pady=(5, 0))
            phoneids_frame = ttk.Frame(qiwei_frame)
            phoneids_frame.grid(row=6, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="请输入11位手机号", 
                    style="Help.TLabel").grid(row=7, column=0, sticky="w", pady=(10, 0), columnspan=2)

            phoneids_entry = ttk.Entry(phoneids_frame)
            phoneids_entry.pack(side="left", fill="x", expand=True)

            def add_phoneid():
                """添加手机号到列表，带格式验证"""
                phoneid = phoneids_entry.get().strip()
                if phoneid:
                    # 验证手机号格式
                    if re.match(r'^1[3-9]\d{9}$', phoneid):
                        phoneids_listbox.insert("end", phoneid)
                        phoneids_entry.delete(0, "end")
                    else:
                        messagebox.showwarning("警告", "手机号格式不正确")

            ttk.Button(phoneids_frame, text="+", command=add_phoneid, width=3).pack(side="left", padx=(5, 0))

            # 手机号列表显示
            phoneids_listbox = tk.Listbox(qiwei_frame, height=5)
            phoneids_listbox.grid(row=7, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除手机号按钮
            ttk.Button(qiwei_frame, text="删除选中手机号", 
                    command=lambda: phoneids_listbox.delete(tk.ANCHOR)).grid(
                row=8, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # 加载已保存的userids和phoneids
            if service.get("userids"):
                for userid in service["userids"]:
                    userids_listbox.insert("end", userid)
            if service.get("phoneids"):
                for phoneid in service["phoneids"]:
                    phoneids_listbox.insert("end", phoneid)

            # PushPlus配置区域
            pushplus_frame = ttk.Frame(push_form)
            ttk.Label(pushplus_frame, text="Token:").grid(row=0, column=0, sticky="w")
            token_entry = ttk.Entry(pushplus_frame)
            token_entry.insert(0, service.get("token", ""))
            token_entry.grid(row=0, column=1, sticky="ew")
            ttk.Label(pushplus_frame, text="群组id(不填只发给自己):").grid(row=1, column=0, sticky="w")
            topic_entry = ttk.Entry(pushplus_frame)
            topic_entry.insert(0, service.get("topic", ""))
            topic_entry.grid(row=1, column=1, sticky="ew")

            # 根据类型显示对应配置
            if service["type"] == "feishu":
                feishu_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                server_frame.grid_remove()
                qiwei_frame.grid_remove()
                pushplus_frame.grid_remove()
            elif service["type"] == "serverchan":
                feishu_frame.grid_remove()
                server_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                qiwei_frame.grid_remove()
                pushplus_frame.grid_remove()
            elif service["type"] == "qiwei":
                feishu_frame.grid_remove()
                server_frame.grid_remove()
                qiwei_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                pushplus_frame.grid_remove()
            elif service["type"] == "pushplus":
                feishu_frame.grid_remove()
                server_frame.grid_remove()
                qiwei_frame.grid_remove()
                pushplus_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
            else:
                feishu_frame.grid_remove()
                server_frame.grid_remove()
                qiwei_frame.grid_remove()
                pushplus_frame.grid_remove()
                messagebox.showerror("错误", "未知推送服务类型")

            def update_push_service():
                """更新推送服务配置"""
                if service["type"] == "feishu":
                    url = feishu_url.get()
                    if not url:
                        messagebox.showerror("错误", "飞书Webhook URL不能为空")
                        return
                    
                    service.update({
                        "webhook_url": url,
                        "havesign": has_sign.get()
                    })
                    
                    if has_sign.get():
                        secret = secret_entry.get()
                        if not secret:
                            messagebox.showerror("错误", "签名模式必须填写秘钥")
                            return
                        service["secret"] = secret
                    else:
                        service.pop("secret", None)
                        
                    service["title"] = f"飞书推送 - {url[-20:]}"
                elif service["type"] == "serverchan":
                    sckey = sckey_entry.get()
                    if not sckey:
                        messagebox.showerror("错误", "ServerChan SCKEY不能为空")
                        return
                        
                    service.update({
                        "sckey": sckey,
                        "title": f"Server酱 - {sckey[-20:]}"
                    })
                elif service["type"] == "qiwei":
                    url = qiwei_url.get()
                    if not url:
                        messagebox.showerror("错误", "企微Webhook URL不能为空")
                        return
                    
                    # 收集userids和phoneids
                    userids = [userids_listbox.get(i) for i in range(userids_listbox.size())]
                    phoneids = [phoneids_listbox.get(i) for i in range(phoneids_listbox.size())]
                    
                    service.update({
                        "webhook_url": url,
                        "userids": userids,
                        "phoneids": phoneids,
                        "title": f"企微推送 - {url[-20:]}"
                    })
                elif service["type"] == "pushplus":
                    token = token_entry.get()
                    topic = topic_entry.get()
                    if not token:
                        messagebox.showerror("错误", "PushPlus Token不能为空")
                        return
                    
                    service.update({
                        "token": token,
                        "topic": topic,
                        "title": f"PushPlus推送 - {token[-20:]}"
                    })
                else:
                    messagebox.showerror("错误", "未知推送服务类型")
                    return
                    
                # 更新列表显示
                item = listbox.selection()[0]
                listbox.item(item, values=(service["type"], service["title"]))
                push_dialog.destroy()

            # 创建底部按钮框架
            btn_frame = ttk.Frame(push_dialog)
            btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)

            # 保存按钮
            ttk.Button(btn_frame, 
                    text="保存", 
                    style="Accent.TButton",
                    command=update_push_service).pack(
                side="left", expand=True, fill="x", padx=5)

            # 取消按钮
            ttk.Button(btn_frame, 
                    text="取消", 
                    style="Accent.TButton",
                    command=push_dialog.destroy).pack(
                side="right", expand=True, fill="x", padx=5)

        def delete_push_service(listbox):
            """删除推送服务"""
            selected = listbox.selection()
            if not selected:
                messagebox.showwarning("警告", "请先选择一个推送服务")
                return
                
            index = listbox.index(selected[0])
            del push_services[index]
            listbox.delete(selected[0])

        # 按钮容器
        # 修改位置：add_user 和 edit_user 中的按钮容器
        btn_container = ttk.Frame(form_frame)
        btn_container.grid(row=9, column=0, columnspan=3, sticky="e", pady=10)

        # 取消按钮
        # 左侧保存按钮
        ttk.Button(btn_container, text="保存", style="Accent.TButton", 
                command=lambda: save_new_user(push_services)).grid(
            row=0, column=0, sticky="e", padx=5)

        # 右侧取消按钮
        ttk.Button(btn_container, text="取消", style="Accent.TButton", command=dialog.destroy).grid(
            row=0, column=1, sticky="e", padx=5)

        def save_new_user(push_services):
            """保存新用户配置"""
            if len(self.users_data) >= self.__class__.MAX_USERS:
                messagebox.showerror("错误", f"最多只能添加{self.__class__.MAX_USERS}个用户")
                return

            username = username_var.get().strip()
            if not username:
                messagebox.showerror("错误", "用户名不能为空")
                return
            
            # 用户名格式验证
            if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]{2,20}$', username):
                messagebox.showerror("错误", "用户名格式错误！\n要求：\n1. 2-20个字符\n2. 仅支持中文、字母、数字和下划线")
                return
            
            # 检查用户是否已存在（通过登录界面创建）
            existing_user = next((u for u in self.users_data if u["username"] == username), None)
            
            # 创建基本用户数据
            user_data = {
                "username": username,
                "cookies_file": f"cookies/{username}.json",
                "usertype": usertype_var.get(),
                "tokenid": tokenid_var.get(),
                "tasks": {task: var.get() for task, var in task_vars.items()},
                "readtime_task_config": readtime_config_var,
                "push_services": [
                    {k: v for k, v in service.items() if k != "title"}
                    for service in push_services
                ]
            }
            
            if existing_user:
                # 用户已存在，更新其他配置（保留已通过登录获取的信息）
                existing_user.update({
                    "usertype": user_data["usertype"],
                    "tokenid": user_data["tokenid"],
                    "tasks": user_data["tasks"],
                    "push_services": user_data["push_services"]
                })
                message = "用户配置已更新（登录信息已保留）"
            else:
                # 用户不存在，创建新用户
                self.users_data.append(user_data)
                message = "用户保存成功"
            
            self.refresh_user_list()
            dialog.destroy()
            self.save_users_config()
            messagebox.showinfo("成功", message)

    def edit_user(self):
        """编辑用户配置"""
        selected = self.user_list.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return
        
        userpage_width = self.resolution_set.get("userpage_width")
        userpage_height = self.resolution_set.get("userpage_height")

        index = self.user_list.index(selected[0])
        user = self.users_data[index]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑用户 - {user['username']}")

        if userpage_width and userpage_height:
            dialog.geometry(f"{userpage_width}x{userpage_height}")
        else:
            dialog.geometry("800x780")

        dialog.transient(self.root)  # 新增：设置为临时窗口
        dialog.grab_set()  # 新增：模态对话框

        form_frame = ttk.Frame(dialog, padding="20 15 20 15")
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_columnconfigure(2, weight=0)
        form_frame.pack(fill="both", expand=True)

        # ====用户名输入====
        ttk.Label(form_frame, text="用户名:").grid(row=0, column=0, sticky="w")
        self.username_var = tk.StringVar(value=user["username"])
        ttk.Entry(form_frame, textvariable=self.username_var, style="Custom.TEntry").grid(
            row=0, column=1, sticky="ew", padx=5)

        # 用户名格式提示
        ttk.Label(form_frame, text="* 2-20位，仅支持中文、字母、数字和下划线", 
                style="Help.TLabel").grid(row=0, column=2, sticky="w")

        # ====usertype输入====
        ttk.Label(form_frame, text="用户类型:").grid(row=3, column=0, sticky="w")
        self.usertype_var = tk.StringVar(value=user.get("usertype", "captcha"))
        ttk.Combobox(form_frame, textvariable=self.usertype_var, 
                    values=["captcha"],
                    state="readonly", width=15).grid(
            row=3, column=1, sticky="w", padx=5)
        ttk.Label(form_frame, text="* 用户类型，固定为captcha", 
                style="Help.TLabel").grid(row=3, column=2, sticky="w")

        # ====tokenid输入====
        ttk.Label(form_frame, text="tokenid:").grid(row=4, column=0, sticky="w")
        self.tokenid_var = tk.StringVar(value=user.get("tokenid", ""))
        ttk.Entry(form_frame, textvariable=self.tokenid_var, style="Custom.TEntry").grid(
            row=4, column=1, sticky="ew", padx=5)
        ttk.Label(form_frame, text="* 用于自动过图形验证，可在我的网站或者咸鱼上获取", 
                style="Help.TLabel").grid(row=4, column=2, sticky="w")
        
        # ====登录方式选择====
        login_frame = ttk.LabelFrame(form_frame, text="登录方式")
        login_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)

        ttk.Button(login_frame, text="手机验证码登录", style="Accent.TButton",
                command=lambda: self.show_phone_login_dialog(dialog, self.username_var.get())).pack(fill="x", pady=2)
        ttk.Button(login_frame, text="账号密码登录", style="Accent.TButton",
                command=lambda: self.show_password_login_dialog(dialog, self.username_var.get())).pack(fill="x", pady=2)
        ttk.Button(login_frame, text="手动输入cookies", style="Accent.TButton",
                command=lambda: self.show_manual_cookies_dialog(dialog, self.username_var.get())).pack(fill="x", pady=2)

        # ====任务配置====
        task_frame = ttk.LabelFrame(form_frame, text="任务配置")
        task_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)

        task_vars = {}
        tasks = ["签到任务", "激励碎片任务", "章节卡任务", "游戏中心任务", "每日抽奖任务", "每周自动兑换章节卡", "章节卡信息推送"]
        for i, task in enumerate(tasks):
            var = tk.BooleanVar(value=user["tasks"].get(task, True))
            ttk.Checkbutton(task_frame, text=task, variable=var).grid(
                row=i//4, column=i%4, sticky="w", padx=10, pady=5)
            task_vars[task] = var

        # 在 edit_user 中，获取已有阅读时长配置
        readtime_config = user.get("readtime_task_config", {})
        if not readtime_config:
            readtime_config = {"book_ids": [], "min_duration": 5, "max_duration": 10, "total_duration": 120}

        # 阅读时长上报任务（第3行第0列）
        readtime_var = tk.BooleanVar(value=user["tasks"].get("阅读时长上报", True))
        ttk.Checkbutton(task_frame, text="阅读时长上报", variable=readtime_var).grid(
            row=2, column=0, sticky="w", padx=10, pady=5)
        task_vars["阅读时长上报"] = readtime_var

        # 配置按钮（第3行第1列）
        ttk.Button(task_frame, text="配置", style="Accent.TButton",
                command=lambda: self._edit_readtime_config(dialog, user["username"], readtime_config)
                ).grid(row=2, column=1, sticky="w", padx=5)

        # ====推送服务配置====
        push_frame = ttk.LabelFrame(form_frame, text="推送服务")
        push_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)

        # 推送服务列表
        push_columns = ("type", "title")
        push_list = ttk.Treeview(push_frame, columns=push_columns, show="headings", height=5)
        push_list.heading("type", text="类型")
        push_list.heading("title", text="配置名称")
        push_list.column("type", width=100)
        push_list.column("title", width=300)
        push_list.pack(side="left", fill="both", expand=True)

        # 推送服务操作按钮
        push_btn_frame = ttk.Frame(push_frame)
        push_btn_frame.pack(side="right", fill="y", padx=5)

        # 初始化推送服务数据
        push_services = user.get("push_services", []).copy()

        def refresh_push_list():
            """刷新推送服务列表"""
            for item in push_list.get_children():
                push_list.delete(item)
            for service in push_services:
                title = service.get("title", f"{service.get('type')}配置")
                push_list.insert("", "end", values=(service["type"], title))

        refresh_push_list()

        # 推送服务列表滚动条
        push_scrollbar = ttk.Scrollbar(push_frame, orient="vertical", command=push_list.yview)
        push_scrollbar.pack(side="right", fill="y")
        push_list.configure(yscrollcommand=push_scrollbar.set)

        def add_push_service():
            """添加推送服务配置"""
            pushpage_width = self.resolution_set.get("pushpage_width")
            pushpage_height = self.resolution_set.get("pushpage_height")

            push_dialog = tk.Toplevel(dialog)
            push_dialog.title("添加推送服务")
            if pushpage_width and pushpage_height:
                push_dialog.geometry(f"{pushpage_width}x{pushpage_height}")
            else:
                push_dialog.geometry("400x250")
            # geometry("400x250")

            push_form = ttk.Frame(push_dialog, padding="15 10 15 10")
            push_form.pack(fill="both", expand=True)
            push_form.grid_rowconfigure(1, weight=1)  # 第1行可扩展
            push_form.grid_columnconfigure(1, weight=1)  # 第1列可扩展

            # 类型选择
            ttk.Label(push_form, text="类型:").grid(row=0, column=0, sticky="w")
            service_type = tk.StringVar()
            ttk.Combobox(push_form, textvariable=service_type,values=["feishu", "serverchan", "qiwei", "pushplus"],
                        state="readonly",width=15, font=self.default_font).grid(row=0, column=1, sticky="w")

            # 飞书配置区域
            feishu_frame = ttk.Frame(push_form)
            feishu_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
            
            # Webhook URL行（可扩展）
            ttk.Label(feishu_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            feishu_url = ttk.Entry(feishu_frame)
            feishu_url.grid(row=0, column=1, sticky="ew", padx=5)
            feishu_frame.grid_columnconfigure(1, weight=1)

            ttk.Label(feishu_frame, text="是否有签名校验:").grid(row=1, column=0, sticky="w")
            has_sign = tk.BooleanVar()
            ttk.Checkbutton(feishu_frame, variable=has_sign, 
                        command=lambda: toggle_secret(secret_frame, has_sign.get())).grid(
                        row=1, column=1, sticky="w")

            # Secret行
            secret_frame = ttk.Frame(feishu_frame)
            ttk.Label(secret_frame, text="密钥:").grid(row=0, column=0, sticky="w")
            secret_entry = ttk.Entry(secret_frame)
            secret_entry.grid(row=0, column=1, sticky="ew", padx=5)
            secret_frame.grid_columnconfigure(1, weight=1)  # 允许Secret输入框扩展
            secret_frame.grid_remove()

            # ServerChan配置区域
            server_frame = ttk.Frame(push_form)
            ttk.Label(server_frame, text="SCKEY:").grid(row=0, column=0, sticky="w")
            sckey_entry = ttk.Entry(server_frame)
            sckey_entry.grid(row=0, column=1, sticky="ew")
            server_frame.grid_columnconfigure(1, weight=1)

            # Qiwei配置区域
            qiwei_frame = ttk.Frame(push_form)
            ttk.Label(qiwei_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            qiwei_url = ttk.Entry(qiwei_frame)
            qiwei_url.grid(row=0, column=1, sticky="ew", padx=8)
            qiwei_frame.grid_columnconfigure(0, minsize=250)
            qiwei_frame.grid_columnconfigure(1, weight=1)

            # 添加提示信息
            ttk.Label(qiwei_frame, text="下面二者选择一种方式填写即可，也可以都填或不填", 
                    style="Help.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
            ttk.Label(qiwei_frame, text="输入后点击+添加到列表", 
                    style="Help.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))

            # 用户ID列表配置
            ttk.Label(qiwei_frame, text="用户ID列表:").grid(row=3, column=0, sticky="w", pady=(5, 0))
            userids_frame = ttk.Frame(qiwei_frame)
            userids_frame.grid(row=3, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="通过特殊方式获取的userid\n如果不懂，请选择手机号方式填写\n(@all代表@全体)", 
                    style="Help.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 0), columnspan=2)

            userids_entry = ttk.Entry(userids_frame)
            userids_entry.pack(side="left", fill="x", expand=True)

            def add_userid():
                """添加用户ID到列表"""
                userid = userids_entry.get().strip()
                if userid:
                    userids_listbox.insert("end", userid)
                    userids_entry.delete(0, "end")

            ttk.Button(userids_frame, text="+", command=add_userid, width=3).pack(side="left", padx=(5, 0))

            # 用户ID列表显示
            userids_listbox = tk.Listbox(qiwei_frame, height=5)
            userids_listbox.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除用户ID按钮
            ttk.Button(qiwei_frame, text="删除选中用户ID", 
                    command=lambda: userids_listbox.delete(tk.ANCHOR)).grid(
                row=5, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # 手机号列表配置
            ttk.Label(qiwei_frame, text="手机号列表:").grid(row=6, column=0, sticky="w", pady=(5, 0))
            phoneids_frame = ttk.Frame(qiwei_frame)
            phoneids_frame.grid(row=6, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="请输入11位手机号", 
                    style="Help.TLabel").grid(row=7, column=0, sticky="w", pady=(10, 0), columnspan=2)

            phoneids_entry = ttk.Entry(phoneids_frame)
            phoneids_entry.pack(side="left", fill="x", expand=True)

            def add_phoneid():
                """添加手机号到列表，带格式验证"""
                phoneid = phoneids_entry.get().strip()
                if phoneid:
                    # 验证手机号格式（简单验证）
                    if re.match(r'^1[3-9]\d{9}$', phoneid):
                        phoneids_listbox.insert("end", phoneid)
                        phoneids_entry.delete(0, "end")
                    else:
                        messagebox.showwarning("警告", "手机号格式不正确")

            ttk.Button(phoneids_frame, text="+", command=add_phoneid, width=3).pack(side="left", padx=(5, 0))

            # 手机号列表显示
            phoneids_listbox = tk.Listbox(qiwei_frame, height=5)
            phoneids_listbox.grid(row=7, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除手机号按钮
            ttk.Button(qiwei_frame, text="删除选中手机号", 
                    command=lambda: phoneids_listbox.delete(tk.ANCHOR)).grid(
                row=8, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # PushPlus配置区域
            pushplus_frame = ttk.Frame(push_form)
            ttk.Label(pushplus_frame, text="Token:").grid(row=0, column=0, sticky="w")
            token_entry = ttk.Entry(pushplus_frame)
            token_entry.grid(row=0, column=1, sticky="ew")
            ttk.Label(pushplus_frame, text="群组id(不填只发给自己):").grid(row=1, column=0, sticky="w")
            topic_entry = ttk.Entry(pushplus_frame)
            topic_entry.grid(row=1, column=1, sticky="ew")
            pushplus_frame.grid_columnconfigure(1, weight=1)

            # 类型切换处理
            def update_config_fields(*args):
                if service_type.get() == "feishu":
                    feishu_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                    server_frame.grid_remove()
                    qiwei_frame.grid_remove()
                    pushplus_frame.grid_remove()
                elif service_type.get() == "serverchan":
                    feishu_frame.grid_remove()
                    server_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                    qiwei_frame.grid_remove()
                    pushplus_frame.grid_remove()
                elif service_type.get() == "qiwei":
                    feishu_frame.grid_remove()
                    server_frame.grid_remove()
                    qiwei_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                    pushplus_frame.grid_remove()
                elif service_type.get() == "pushplus":
                    feishu_frame.grid_remove()
                    server_frame.grid_remove()
                    qiwei_frame.grid_remove()
                    pushplus_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

            service_type.trace_add("write", update_config_fields)
            update_config_fields()  # 初始化显示

            def save_push_service():
                """保存推送服务配置"""
                service_type_val = service_type.get()
                if service_type_val == "feishu":
                    url = feishu_url.get()
                    if not url:
                        messagebox.showerror("错误", "飞书Webhook URL不能为空")
                        return

                    service = {
                        "type": "feishu",
                        "webhook_url": url,
                        "havesign": has_sign.get(),
                        "title": f"飞书推送 - {url[-20:]}"
                    }

                    if has_sign.get():
                        secret = secret_entry.get()
                        if not secret:
                            messagebox.showerror("错误", "签名模式必须填写密钥")
                            return
                        service["secret"] = secret

                elif service_type_val == "serverchan":  # serverchan
                    sckey = sckey_entry.get()
                    if not sckey:
                        messagebox.showerror("错误", "ServerChan SCKEY不能为空")
                        return
                        
                    service = {
                        "type": "serverchan",
                        "sckey": sckey,
                        "title": f"Server酱 - {sckey[-20:]}"
                    }
                
                elif service_type_val == "qiwei":
                    url = qiwei_url.get()
                    if not url:
                        messagebox.showerror("错误", "QiWei Webhook URL不能为空")
                        return
                    
                    # 收集userids和phoneids
                    userids = [userids_listbox.get(i) for i in range(userids_listbox.size())]
                    phoneids = [phoneids_listbox.get(i) for i in range(phoneids_listbox.size())]
                    
                    service = {
                        "type": "qiwei",
                        "webhook_url": url,
                        "userids": userids,  # 保存为字符串列表
                        "phoneids": phoneids,  # 保存为字符串列表
                        "title": f"企业微信 - {url[-20:]}"
                    }
                
                elif service_type_val == "pushplus":
                    token = token_entry.get()
                    topic = topic_entry.get()
                    if not token:
                        messagebox.showerror("错误", "PushPlus Token不能为空")
                        return
                    service = {
                        "type": "pushplus",
                        "token": token,
                        "topic": topic,
                        "title": f"PushPlus - {token[-20:]}"
                    }

                else:
                    messagebox.showerror("错误", "未知的推送服务类型")
                    return

                push_services.append(service)
                push_list.insert("", "end", values=(service["type"], service["title"]))
                push_dialog.destroy()

            # 修改按钮框架布局
            btn_frame = ttk.Frame(push_dialog)
            btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)  # 固定在底部

            # 保存按钮
            ttk.Button(btn_frame, 
                    text="保存", 
                    style="Accent.TButton",
                    command=save_push_service).pack(side="left", expand=True, fill="x", padx=5)

            # 取消按钮
            ttk.Button(btn_frame, 
                    text="取消", 
                    style="Accent.TButton",
                    command=push_dialog.destroy).pack(side="right", expand=True, fill="x", padx=5)

        def edit_push_service(listbox):
            """编辑推送服务配置"""
            selected = listbox.selection()
            if not selected:
                messagebox.showwarning("警告", "请先选择一个推送服务")
                return
            
            if not push_services:
                messagebox.showwarning("警告", "推送服务列表为空")
                return

            index = listbox.index(selected[0])
            service = push_services[index]

            pushpage_width = self.resolution_set.get("pushpage_width")
            pushpage_height = self.resolution_set.get("pushpage_height")

            # 创建新的配置对话框进行编辑
            push_dialog = tk.Toplevel(dialog)
            push_dialog.title(f"编辑推送服务 - {service['type']}")
            if pushpage_width and pushpage_height:
                push_dialog.geometry(f"{pushpage_width}x{pushpage_height}")
            else:
                push_dialog.geometry("400x250")
            # push_dialog.geometry("400x250")

            push_form = ttk.Frame(push_dialog, padding="15 10 15 10")
            push_form.pack(fill="both", expand=True)
            push_form.grid_rowconfigure(1, weight=1)  # 第1行可扩展
            push_form.grid_columnconfigure(1, weight=1)  # 第1列可扩展

            # 类型选择（禁用修改）
            ttk.Label(push_form, text="类型:").grid(row=0, column=0, sticky="w")
            ttk.Label(push_form, text=service["type"]).grid(row=0, column=1, sticky="w")

            # 飞书配置区域
            feishu_frame = ttk.Frame(push_form)
            feishu_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
            ttk.Label(feishu_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            feishu_url = ttk.Entry(feishu_frame)
            feishu_url.insert(0, service.get("webhook_url", ""))
            feishu_url.grid(row=0, column=1, sticky="ew")
            feishu_frame.grid_columnconfigure(1, weight=1)

            ttk.Label(feishu_frame, text="是否有签名校验:").grid(row=1, column=0, sticky="w")
            has_sign = tk.BooleanVar(value=service.get("havesign", False))
            ttk.Checkbutton(feishu_frame, variable=has_sign, 
                        command=lambda: toggle_secret(secret_frame, has_sign.get())).grid(
                        row=1, column=1, sticky="w")

            secret_frame = ttk.Frame(feishu_frame)
            ttk.Label(secret_frame, text="密钥:").grid(row=0, column=0, sticky="w")
            secret_entry = ttk.Entry(secret_frame)
            secret_entry.insert(0, service.get("secret", ""))
            secret_entry.grid(row=0, column=1, sticky="ew")
            
            if service.get("havesign", False):
                secret_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
                secret_frame.grid_columnconfigure(1, weight=1)
            else:
                secret_frame.grid_remove()

            # ServerChan配置区域
            server_frame = ttk.Frame(push_form)
            ttk.Label(server_frame, text="SCKEY:").grid(row=0, column=0, sticky="w")
            sckey_entry = ttk.Entry(server_frame)
            sckey_entry.insert(0, service.get("sckey", ""))
            sckey_entry.grid(row=0, column=1, sticky="ew")
            server_frame.grid_columnconfigure(1, weight=1)

            # Qiwei配置区域
            qiwei_frame = ttk.Frame(push_form)
            ttk.Label(qiwei_frame, text="Webhook URL:").grid(row=0, column=0, sticky="w")
            qiwei_url = ttk.Entry(qiwei_frame)
            qiwei_url.insert(0, service.get("webhook_url", ""))
            qiwei_url.grid(row=0, column=1, sticky="ew", padx=5)
            qiwei_frame.grid_columnconfigure(0, minsize=250)
            qiwei_frame.grid_columnconfigure(1, weight=1)

            # 添加提示信息
            ttk.Label(qiwei_frame, text="下面二者选择一种方式填写即可，也可以都填或不填", 
                    style="Help.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
            ttk.Label(qiwei_frame, text="输入后点击+添加到列表", 
                    style="Help.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))

            # 用户ID列表配置
            ttk.Label(qiwei_frame, text="用户ID列表:").grid(row=3, column=0, sticky="w", pady=(5, 0))
            userids_frame = ttk.Frame(qiwei_frame)
            userids_frame.grid(row=3, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="通过特殊方式获取的userid\n如果不懂，请选择手机号方式填写\n(@all代表@全体)", 
                    style="Help.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 0), columnspan=4)

            userids_entry = ttk.Entry(userids_frame)
            userids_entry.pack(side="left", fill="x", expand=True)

            def add_userid():
                """添加用户ID到列表"""
                userid = userids_entry.get().strip()
                if userid:
                    userids_listbox.insert("end", userid)
                    userids_entry.delete(0, "end")

            ttk.Button(userids_frame, text="+", command=add_userid, width=3).pack(side="left", padx=(5, 0))

            # 用户ID列表显示
            userids_listbox = tk.Listbox(qiwei_frame, height=5)
            userids_listbox.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除用户ID按钮
            ttk.Button(qiwei_frame, text="删除选中用户ID", 
                    command=lambda: userids_listbox.delete(tk.ANCHOR)).grid(
                row=5, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # 手机号列表配置
            ttk.Label(qiwei_frame, text="手机号列表:").grid(row=6, column=0, sticky="w", pady=(5, 0))
            phoneids_frame = ttk.Frame(qiwei_frame)
            phoneids_frame.grid(row=6, column=1, sticky="ew", pady=(5, 0))

            ttk.Label(qiwei_frame, text="请输入11位手机号", 
                    style="Help.TLabel").grid(row=7, column=0, sticky="w", pady=(10, 0), columnspan=2)

            phoneids_entry = ttk.Entry(phoneids_frame)
            phoneids_entry.pack(side="left", fill="x", expand=True)

            def add_phoneid():
                """添加手机号到列表，带格式验证"""
                phoneid = phoneids_entry.get().strip()
                if phoneid:
                    # 验证手机号格式
                    if re.match(r'^1[3-9]\d{9}$', phoneid):
                        phoneids_listbox.insert("end", phoneid)
                        phoneids_entry.delete(0, "end")
                    else:
                        messagebox.showwarning("警告", "手机号格式不正确")

            ttk.Button(phoneids_frame, text="+", command=add_phoneid, width=3).pack(side="left", padx=(5, 0))

            # 手机号列表显示
            phoneids_listbox = tk.Listbox(qiwei_frame, height=5)
            phoneids_listbox.grid(row=7, column=1, columnspan=2, sticky="ew", pady=(5, 0))

            # 删除手机号按钮
            ttk.Button(qiwei_frame, text="删除选中手机号", 
                    command=lambda: phoneids_listbox.delete(tk.ANCHOR)).grid(
                row=8, column=1, columnspan=2, sticky="w", pady=(5, 0))

            # 加载已保存的userids和phoneids
            if service.get("userids"):
                for userid in service["userids"]:
                    userids_listbox.insert("end", userid)
            if service.get("phoneids"):
                for phoneid in service["phoneids"]:
                    phoneids_listbox.insert("end", phoneid)

            # PushPlus配置区域
            pushplus_frame = ttk.Frame(push_form)
            ttk.Label(pushplus_frame, text="Token:").grid(row=0, column=0, sticky="w")
            token_entry = ttk.Entry(pushplus_frame)
            token_entry.insert(0, service.get("token", ""))
            token_entry.grid(row=0, column=1, sticky="ew")
            ttk.Label(pushplus_frame, text="群组id(不填只发给自己):").grid(row=1, column=0, sticky="w")
            topic_entry = ttk.Entry(pushplus_frame)
            topic_entry.insert(0, service.get("topic", ""))
            topic_entry.grid(row=1, column=1, sticky="ew")
            pushplus_frame.grid_columnconfigure(1, weight=1)

            # 根据类型显示对应配置
            if service["type"] == "feishu":
                feishu_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                server_frame.grid_remove()
                qiwei_frame.grid_remove()
                pushplus_frame.grid_remove()
            elif service["type"] == "serverchan":
                feishu_frame.grid_remove()
                server_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                qiwei_frame.grid_remove()
                pushplus_frame.grid_remove()
            elif service["type"] == "qiwei":
                feishu_frame.grid_remove()
                server_frame.grid_remove()
                qiwei_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
                pushplus_frame.grid_remove()
            elif service["type"] == "pushplus":
                feishu_frame.grid_remove()
                server_frame.grid_remove()
                qiwei_frame.grid_remove()
                pushplus_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
            else:
                feishu_frame.grid_remove()
                server_frame.grid_remove()
                qiwei_frame.grid_remove()
                pushplus_frame.grid_remove()
                messagebox.showerror("错误", "未知推送服务类型")

            def update_push_service():
                """更新推送服务配置"""
                if service["type"] == "feishu":
                    url = feishu_url.get()
                    if not url:
                        messagebox.showerror("错误", "飞书Webhook URL不能为空")
                        return

                    service.update({
                        "webhook_url": url,
                        "havesign": has_sign.get()
                    })

                    if has_sign.get():
                        secret = secret_entry.get()
                        if not secret:
                            messagebox.showerror("错误", "签名模式必须填写秘钥")
                            return
                        service["secret"] = secret
                    else:
                        service.pop("secret", None)
                    service["title"] = f"飞书推送 - {url[-20:]}"
                elif service["type"] == "serverchan":
                    sckey = sckey_entry.get()
                    if not sckey:
                        messagebox.showerror("错误", "ServerChan SCKEY不能为空")
                        return
                        
                    service.update({
                        "sckey": sckey,
                        "title": f"Server酱 - {sckey[-20:]}"
                    })
                elif service["type"] == "qiwei":
                    url = qiwei_url.get()
                    if not url:
                        messagebox.showerror("错误", "企微Webhook URL不能为空")
                        return
                    
                    # 收集userids和phoneids
                    userids = [userids_listbox.get(i) for i in range(userids_listbox.size())]
                    phoneids = [phoneids_listbox.get(i) for i in range(phoneids_listbox.size())]
                    
                    service.update({
                        "webhook_url": url,
                        "userids": userids,
                        "phoneids": phoneids,
                        "title": f"企微推送 - {url[-20:]}"
                    })
                elif service["type"] == "pushplus":
                    token = token_entry.get()
                    topic = topic_entry.get()
                    if not token:
                        messagebox.showerror("错误", "PushPlus Token不能为空")
                        return
                    
                    service.update({
                        "token": token,
                        "topic": topic,
                        "title": f"PushPlus - {token[-20:]}"
                    })
                else: 
                    messagebox.showerror("错误", "未知推送服务类型")
                    return

                # 更新列表显示
                item = listbox.selection()[0]
                listbox.item(item, values=(service["type"], service["title"]))
                push_dialog.destroy()

            # 创建底部按钮框架
            btn_frame = ttk.Frame(push_dialog)
            btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)

            # 保存按钮
            ttk.Button(btn_frame, 
                    text="保存", 
                    style="Accent.TButton",
                    command=update_push_service).pack(
                side="left", expand=True, fill="x", padx=5)

            # 取消按钮
            ttk.Button(btn_frame, 
                    text="取消", 
                    style="Accent.TButton",
                    command=push_dialog.destroy).pack(
                side="right", expand=True, fill="x", padx=5)

        def toggle_secret(frame, show):
            if show:
                frame.grid(row=2, column=0, columnspan=2, sticky="ew")  # 固定行号和跨列
            else:
                frame.grid_remove()

        def delete_push_service(listbox):
            """删除推送服务"""
            selected = listbox.selection()
            if not selected:
                messagebox.showwarning("警告", "请先选择一个推送服务")
                return

            index = listbox.index(selected[0])
            del push_services[index]
            listbox.delete(selected[0])

        # 推送服务操作按钮
        ttk.Button(push_btn_frame, text="添加", style="Accent.TButton",
                command=add_push_service).pack(fill="x", pady=2)
        ttk.Button(push_btn_frame, text="编辑", style="Accent.TButton",
                command=lambda: edit_push_service(push_list)).pack(fill="x", pady=2)
        ttk.Button(push_btn_frame, text="删除", style="Accent.TButton",
                command=lambda: delete_push_service(push_list)).pack(fill="x", pady=2)
        
        # 配置网格列权重
        form_frame.grid_columnconfigure(1, weight=1)

        # 按钮容器
        btn_container = ttk.Frame(form_frame)
        btn_container.grid(row=9, column=0, columnspan=3, sticky="e", pady=10)

        # 取消按钮
        ttk.Button(btn_container, text="取消", style="Accent.TButton",
                command=dialog.destroy).pack(side="right", padx=5)

        # 保存按钮
        ttk.Button(btn_container, text="保存", style="Accent.TButton",
                command=lambda: save_edited_user(push_services)).pack(
                side="right", padx=5)

        
        def save_edited_user(updated_push_services=None):
            """保存编辑后的用户配置"""
            if updated_push_services is None:
                updated_push_services = []
            new_username = self.username_var.get().strip()
            old_username = user["username"]

            # 检查用户名是否为空
            if not new_username:
                messagebox.showerror("错误", "用户名不能为空")
                return

            # 用户名格式验证
            if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]{2,20}$', new_username):
                messagebox.showerror("错误", "用户名格式错误！\n要求：\n1. 2-20个字符\n2. 仅支持中文、字母、数字和下划线")
                return

            # 检查用户名是否冲突
            if new_username != old_username and any(
                u["username"] == new_username and u != user  # 使用对象对比而非索引
                for u in self.users_data
            ):
                messagebox.showerror("错误", "该用户名已存在")
                return

            # 更新cookies文件路径
            new_cookies_file = f"cookies/{new_username}.json"
            if new_username != old_username:
                try:
                    old_cookies_file = user["cookies_file"]
                    if os.path.exists(old_cookies_file):
                        os.rename(old_cookies_file, new_cookies_file)
                except Exception as e:
                    messagebox.showerror("错误", f"无法更新Cookies文件：{str(e)}")
                    return

            # 更新用户数据
            edited_user = {
                "username": new_username,
                "cookies_file": new_cookies_file,
                "usertype": self.usertype_var.get(),
                "tokenid": self.tokenid_var.get(),
                "tasks": {task: var.get() for task, var in task_vars.items()},
                "readtime_task_config": readtime_config,
                "push_services": [
                    {k: v for k, v in service.items() if k != "title"}
                    for service in updated_push_services or []
                ]
            }

            # self.users_data[index] = edited_user
            self.users_data[index].update(edited_user)
            self.refresh_user_list()
            dialog.destroy()
            self.save_users_config() # 实时保存用户配置更改 也可以删了，就会变成只有主界面的保存按钮才能保存
            messagebox.showinfo("成功", "用户信息已更新")  # ✅ 添加成功提示

    def remove_user(self):
        """删除选中的用户"""
        selected = self.user_list.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return
        
        index = self.user_list.index(selected[0])
        user = self.users_data[index]
        username = user["username"]
        cookies_file = user.get("cookies_file", "")

        
        if messagebox.askyesno("确认", f"确定要删除用户 '{username}' 吗？"):
            # 删除Cookies文件（如果存在）
            if cookies_file and os.path.exists(cookies_file):
                try:
                    os.remove(cookies_file)
                except Exception as e:
                    messagebox.showerror("错误", f"无法删除Cookies文件：{str(e)}")
                    return  # 阻止继续删除用户数据

            del self.users_data[index]
            self.refresh_user_list()
            self.save_users_config() # 实时保存用户配置更改 也可以删了，就会变成只有主界面的保存按钮才能保存

    def _edit_readtime_config(self, parent, username, config_dict):
        """
        编辑阅读时长任务配置的对话框
        :param parent: 父窗口
        :param username: 当前用户名（用于获取 cookies 等信息）
        :param config_dict: 用于保存配置的字典（可变对象）
        """
        # 获取用户已有的 cookies 和 UA（用于搜索）
        user = next((u for u in self.users_data if u["username"] == username), None)
        if user:
            cookies_file = user.get("cookies_file")
            cookies = {}
            if cookies_file and os.path.exists(cookies_file):
                try:
                    with open(cookies_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                except:
                    cookies = {}
            user_agent = user.get("user_agent") or self.config_data.get("default_user_agent", "")
            ibex = user.get("ibex", "")
        else:
            cookies = {}
            user_agent = self.config_data.get("default_user_agent", "")
            ibex = ""

        readtime_report_width = self.resolution_set.get("pushpage_width")
        readtime_report_height = self.resolution_set.get("pushpage_height")

        dialog = tk.Toplevel(parent)
        dialog.title("阅读时长上报任务配置")
        dialog.geometry(f"{readtime_report_width}x{readtime_report_height}")
        dialog.transient(parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill="both", expand=True)

        # ===== 书籍ID列表 =====
        book_frame = ttk.LabelFrame(main_frame, text="书籍ID列表", padding="5")
        book_frame.pack(fill="both", expand=True, pady=5)

        # 左侧列表框 + 滚动条
        list_frame = ttk.Frame(book_frame)
        list_frame.pack(side="left", fill="both", expand=True)

        book_listbox = tk.Listbox(list_frame, selectmode="extended", height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=book_listbox.yview)
        book_listbox.configure(yscrollcommand=scrollbar.set)
        book_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 右侧按钮
        btn_frame = ttk.Frame(book_frame)
        btn_frame.pack(side="right", fill="y", padx=(5,0))

        def add_books():
            """搜索并添加书籍"""
            keyword = simpledialog.askstring("搜索书籍", "请输入书籍关键词：", parent=dialog)
            if not keyword:
                return
            # 调用多选搜索方法
            selected_ids = self._search_books_multiselect(dialog, user_agent, cookies, ibex, keyword)
            if selected_ids:
                for bid in selected_ids:
                    # 避免重复
                    if str(bid) not in book_listbox.get(0, tk.END):
                        book_listbox.insert(tk.END, str(bid))

        def add_manual():
            ids_str = tk.simpledialog.askstring("手动添加书籍ID", "请输入书籍ID（多个用逗号分隔）：", parent=dialog)
            if not ids_str:
                return
            parts = [p.strip() for p in ids_str.split(',') if p.strip()]
            added = 0
            for p in parts:
                if p.isdigit():
                    if p not in book_listbox.get(0, tk.END):
                        book_listbox.insert(tk.END, p)
                        added += 1
                else:
                    messagebox.showwarning("警告", f"无效的书籍ID: {p}，仅支持数字，已跳过", parent=dialog)
            if added:
                messagebox.showinfo("成功", f"已添加 {added} 个书籍ID", parent=dialog)

        ttk.Button(btn_frame, text="手动添加", style="Accent.TButton", command=add_manual).pack(fill="x", pady=2)

        def delete_selected():
            for i in reversed(book_listbox.curselection()):
                book_listbox.delete(i)

        ttk.Button(btn_frame, text="搜索添加", style="Accent.TButton", command=add_books).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="删除选中", style="Accent.TButton", command=delete_selected).pack(fill="x", pady=2)

        # 初始化现有书籍ID
        for bid in config_dict.get("book_ids", []):
            book_listbox.insert(tk.END, str(bid))

        # ===== 时长范围 =====
        range_frame = ttk.Frame(main_frame)
        range_frame.pack(fill="x", pady=5)

        ttk.Label(range_frame, text="每章阅读时长范围(分钟):").pack(side="left", padx=5)
        min_dur_var = tk.IntVar(value=config_dict.get("min_duration", 5))
        max_dur_var = tk.IntVar(value=config_dict.get("max_duration", 10))
        ttk.Spinbox(range_frame, from_=1, to=60, textvariable=min_dur_var, width=5).pack(side="left")
        ttk.Label(range_frame, text="—").pack(side="left")
        ttk.Spinbox(range_frame, from_=1, to=60, textvariable=max_dur_var, width=5).pack(side="left")
        ttk.Label(range_frame, text="分钟").pack(side="left", padx=5)

        # ===== 阅读总时长 =====
        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill="x", pady=5)

        ttk.Label(total_frame, text="阅读总时长(分钟):").pack(side="left", padx=5)
        total_dur_var = tk.IntVar(value=config_dict.get("total_duration", 120))
        ttk.Spinbox(total_frame, from_=1, to=1440, textvariable=total_dur_var, width=8).pack(side="left")
        ttk.Label(total_frame, text="分钟").pack(side="left", padx=5)

        # ===== 底部按钮 =====
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=10)

        def save_config():
            # 从列表框收集书籍ID（转换为字符串）
            book_ids = []
            for i in range(book_listbox.size()):
                try:
                    book_ids.append(str(book_listbox.get(i)))
                except:
                    pass
            config_dict.clear()
            config_dict.update({
                "book_ids": book_ids,
                "min_duration": min_dur_var.get(),
                "max_duration": max_dur_var.get(),
                "total_duration": total_dur_var.get()
            })
            dialog.destroy()

        ttk.Button(bottom_frame, text="取消", style="Accent.TButton", command=dialog.destroy).pack(side="right", padx=5)
        ttk.Button(bottom_frame, text="保存", style="Accent.TButton", command=save_config).pack(side="right", padx=5)

        dialog.wait_window()  # 等待对话框关闭

    def _search_books_multiselect(self, parent, user_agent, cookies, ibex, keyword):
        """弹出多选书籍对话框，返回选中的书籍ID列表"""
        from utils import search_books

        try:
            booklist = search_books(user_agent, cookies, ibex, keyword)
            if not booklist:
                messagebox.showinfo("提示", "未找到相关书籍", parent=parent)
                return []
        except Exception as e:
            messagebox.showerror("错误", f"搜索失败: {str(e)}", parent=parent)
            return []

        search_books_width = self.resolution_set.get("pushpage_width")
        search_books_height = self.resolution_set.get("pushpage_height")

        # 创建弹窗
        popup = tk.Toplevel(parent)
        popup.title("选择书籍（可多选）")
        popup.geometry(f"{search_books_width}x{search_books_height}")
        popup.transient(parent)
        popup.grab_set()

        frame = ttk.Frame(popup, padding=10)
        frame.pack(fill="both", expand=True)

        # 表格显示书籍列表
        columns = ("name", "author", "bookid")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended", height=12)
        tree.heading("name", text="书籍名")
        tree.heading("author", text="作者")
        tree.heading("bookid", text="书籍ID")
        tree.column("name", width=180)
        tree.column("author", width=100)
        tree.column("bookid", width=100)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 插入数据
        for book in booklist:
            tree.insert("", "end", values=(book['BookName'], book['AuthorName'], book['BookId']))

        result = []

        def confirm():
            nonlocal result
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("警告", "请至少选择一本书", parent=popup)
                return
            for item in selected:
                values = tree.item(item, "values")
                result.append(str(values[2]))  # 书籍ID
            popup.destroy()

        btn_frame = ttk.Frame(popup)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="确认", style="Accent.TButton", command=confirm).pack(side="left", padx=10, expand=True)
        ttk.Button(btn_frame, text="取消", style="Accent.TButton", command=popup.destroy).pack(side="right", padx=10, expand=True)

        popup.wait_window()
        return result
    
    def create_cookies_converter(self, parent, default_content=None):
        """创建带转换功能的Cookies配置区域"""
        converter_frame = ttk.Frame(parent)

        # 设置列权重：左侧和右侧可扩展，中间按钮列固定
        converter_frame.grid_columnconfigure(0, weight=1)  # 左侧输入区可扩展
        converter_frame.grid_columnconfigure(1, weight=0)  # 中间按钮列固定
        converter_frame.grid_columnconfigure(2, weight=1)  # 右侧显示区可扩展
        converter_frame.grid_rowconfigure(1, weight=1)  # 文本区域可垂直扩展
        
        # 左侧输入框
        input_label = ttk.Label(converter_frame, text="原始字符串:")
        input_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))
        
        input_text = tk.Text(converter_frame, height=5, font=self.default_font)
        input_text.grid(row=1, column=0, sticky="nsew", padx=5)
        
        # 右侧JSON显示
        json_label = ttk.Label(converter_frame, text="JSON格式:")
        json_label.grid(row=0, column=2, sticky="w", padx=5, pady=(5, 0))
        
        cookies_text = tk.Text(converter_frame, height=10, font=self.default_font)
        cookies_text.grid(row=1, column=2, sticky="nsew", padx=5)
        
        # 中间转换按钮
        convert_btn = ttk.Button(
            converter_frame,
            text="→\n转\n换",
            style="Accent.TButton",
            command=lambda: self.convert_string_to_json(input_text, cookies_text),
            width=6
        )
        convert_btn.grid(row=0, column=1, rowspan=2, sticky="ns", padx=20, pady=40)

        # ==== 水印提示逻辑 ==== 
        self.placeholder_text = "输入示例：appId=xxx; areaId=xxx; lang=xxx;"

        def set_placeholder():
            """设置水印提示"""
            input_text.delete("1.0", "end")
            input_text.insert("1.0", self.placeholder_text)
            input_text.tag_add("placeholder", "1.0", "end")
            input_text.tag_config("placeholder", foreground="gray")
            input_text._has_placeholder = True

        def clear_placeholder(event=None):
            """清除水印提示"""
            if getattr(input_text, "_has_placeholder", False):
                input_text.delete("1.0", "end")
                input_text.tag_config("placeholder", foreground="gray")  # 保留样式
                input_text._has_placeholder = False

        def restore_placeholder(event=None):
            """恢复水印提示"""
            if input_text.get("1.0", "end-1c") == "":
                set_placeholder()

        def on_key(event):
            """拦截 BackSpace 键，防止删除水印"""
            if getattr(input_text, "_has_placeholder", False):
                if event.keysym == "BackSpace":
                    return "break"
                else:
                    clear_placeholder()
            input_text.after(100, restore_placeholder)

        # 初始化水印提示
        input_text._has_placeholder = False
        input_text.bind("<FocusIn>", clear_placeholder)
        input_text.bind("<FocusOut>", restore_placeholder)
        input_text.bind("<Key>", on_key)

        set_placeholder()  # 初始设置
        # ==== 水印提示逻辑结束 ==== 

        # 插入默认内容
        # 插入默认内容
        if default_content is None:
            default_content = self.__class__.DEFAULT_COOKIES_TEMPLATE
        
        if default_content:
            if isinstance(default_content, str):
                cookies_text.insert("1.0", default_content)
            else:
                cookies_text.insert("1.0", json.dumps(default_content, indent=2, ensure_ascii=False))

        return converter_frame, cookies_text
    
    def convert_string_to_json(self, input_text, cookies_text):
        """转换字符串到JSON格式"""
        raw_str = input_text.get("1.0", "end-1c")

        # 检查是否是水印内容
        if getattr(input_text, "_has_placeholder", False) or raw_str == self.placeholder_text:
            messagebox.showwarning("警告", "请输入有效的Cookies字符串")
            return
        
        try:
            # 解析字符串为字典
            cookies_dict = {}
            pairs = [p.strip() for p in raw_str.split(";") if p.strip()]
            
            for pair in pairs:
                if "=" not in pair:
                    raise ValueError(f"无效的键值对: {pair}")
                
                key, value = pair.split("=", 1)
                cookies_dict[key.strip()] = value.strip()
            
            # 转换为JSON格式字符串
            json_str = json.dumps(cookies_dict, indent=2, ensure_ascii=False)
            
            # 更新右侧显示
            cookies_text.delete("1.0", "end")
            cookies_text.insert("1.0", json_str)
            
        except Exception as e:
            messagebox.showerror("转换失败", f"无法解析Cookies字符串：{str(e)}")

    def save_config(self):
        """保存配置到文件"""
        # 输入验证
        if self.log_days_var.get() < 1 or self.log_days_var.get() > 30:
            messagebox.showerror("错误", "日志保留天数必须在 1-30 天之间")
            return
        
        if self.retry_var.get() < 1 or self.retry_var.get() > 10:
            messagebox.showerror("错误", "重试次数必须在 1-10 次之间")
            return

        # 更新全局配置
        self.config_data.update({
            "default_user_agent": self.ua_var.get(),
            "log_level": self.log_level_var.get(),
            "log_retention_days": self.log_days_var.get(),
            "retry_attempts": self.retry_var.get()
        })
        
        # 保存用户配置
        self.config_data["users"] = self.users_data
        
        # 写入文件
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            
        messagebox.showinfo("成功", "配置保存成功")

    def save_users_config(self):
        """仅保存用户配置到文件"""
        try:
            # 更新配置数据中的用户列表
            self.config_data["users"] = self.users_data
            
            # 写入文件
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("错误", f"保存用户配置失败：{str(e)}")      

    def execute_task(self):
        """执行任务按钮点击事件"""

        # 获取当前可执行文件所在目录
        base_path = os.path.dirname(sys.argv[0])
        if sys_run == 1:
            qdjob_path = os.path.join(base_path, "QDjob.exe")
            qdjob_windows_path = os.path.join(base_path, "QDjob_windows.exe")
        elif sys_run == 2:
            qdjob_path = os.path.join(base_path, "QDjob")
            qdjob_windows_path = os.path.join(base_path, "QDjob_linux")
        else:
            messagebox.showerror("错误", "未知系统类型，请使用windows系统或者linux系统运行本程序")

        if os.path.exists(qdjob_path):
            import subprocess
            subprocess.Popen([qdjob_path])
        elif os.path.exists(qdjob_windows_path):
            import subprocess
            subprocess.Popen([qdjob_windows_path])
        else:
            error_message = (
                "❌未找到任务执行程序QDjob\n\n"
                "⚠️请将QDjob与本程序放置于同一个文件夹下\n\n"
                "⚠️请勿修改文件名"
            )
            messagebox.showerror("执行失败", error_message)

if __name__ == "__main__":
    import platform
    if platform.system() == "Windows":
        import ctypes
        try:
            # 告诉 Windows 这个程序是 DPI 感知的
            ctypes.windll.shcore.SetProcessDpiAwareness(1) # 1 代表 PROCESS_SYSTEM_DPI_AWARE
        except Exception:
            try:
                # 兼容旧版本 Windows
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    root = tk.Tk()
    
    # 增加这一行，让 Tkinter 根据当前的 DPI 缩放比例自适应大小
    # root.tk.call('tk', 'scaling', root.winfo_fpixels('1i')/72.0) 
    
    app = ConfigEditor(root)
    root.mainloop()