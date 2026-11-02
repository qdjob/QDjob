# coding: utf-8
import os
import json
import requests
import time
import random, string
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enctrypt_qidian import getQDSign, getSDKSign, getborgus, getuserid_from_QDInfo, getQDInfo_byQDInfo, getibex_byibex, getsignature
from push import *
from logger import LoggerManager
from logger import DEFAULT_LOG_RETENTION

__version__ = 'v1.4.3'

# 配置常量
CONFIG_FILE = 'config.json'
COOKIES_DIR = 'cookies'
DEFAULT_USER_AGENT = "Mozilla/5.0 (Linux; Android 13; PDEM10 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/109.0.5414.86 MQQBrowser/6.2 TBS/047601 Mobile Safari/537.36 QDJSSDK/1.0  QDNightStyle_1  QDReaderAndroid/7.9.384/1466/1000032/OPPO/QDShowNativeLoading"
DEFAULT_COOKIES_REFRESH_INTERVAL_DAYS = 20  # cookies 自动刷新间隔（天），默认20天

# 网络超时（秒）：默认 900 秒（15 分钟），仅作为后台任务的兜底保护
# 性能/网络较差的环境可适当放宽；可用环境变量覆盖
def _env_timeout(name: str, default: str) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)

REQUEST_CONNECT_TIMEOUT = _env_timeout('QDJOB_CONNECT_TIMEOUT', '900')
REQUEST_READ_TIMEOUT = _env_timeout('QDJOB_READ_TIMEOUT', '900')
REQUEST_TIMEOUT = (REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT)

logger = LoggerManager().setup_basic_logger()

SDK_VERSION_TABLE = {
    "1656": "401",
    "1676": "401",
    "1686": "401",
    "1696": "401",
    "1706": "401",
    "1716": "401",
}

class QidianError(Exception):
    """自定义异常类"""
    def __init__(self, message: str, raw_data: Optional[Dict] = None):
        super().__init__(message)
        self.raw_data = raw_data

class QidianTimeoutError(QidianError):
    """接口请求超时异常（超时后终止当前任务）"""

class UserConfig:
    """用户配置"""
    def __init__(self, username: str, cookies: Dict[str, str], cookies_file: str,
                 tasks: Dict[str, bool], user_agent: str, ibex: str,
                 push_services: List[PushService], readtime_task_config: Dict[str, Any], tokenid: Optional[str] = None, 
                 usertype: Optional[str] = None,
                 cookies_refresh_interval_days: int = DEFAULT_COOKIES_REFRESH_INTERVAL_DAYS,
                 last_cookies_refresh_time: Optional[str] = None):
        self.username = username
        self.cookies = cookies
        self.cookies_file = cookies_file
        self.tasks = tasks
        self.user_agent = user_agent
        self.ibex = ibex
        self.push_services = push_services
        self.readtime_task_config = readtime_task_config
        self.tokenid = tokenid
        self.usertype = usertype
        self.cookies_refresh_interval_days = cookies_refresh_interval_days
        self.last_cookies_refresh_time = last_cookies_refresh_time

class ConfigManager:
    """配置管理类"""
    def __init__(self):
        self.config = self._load_config()
        self._validate_config()  # 新增：执行全局配置校验
        self.users = self._init_users()
        # logger.info("配置加载完成")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载主配置文件"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    def _init_users(self) -> List[UserConfig]:
        """初始化用户配置"""
        # 添加用户数量限制检查
        if len(self.config['users']) > 3:
            logger.error("❌ 用户数量超过最大限制3个，请调整配置文件")
            raise ValueError("用户数量超过最大限制3个")
        
        users = []
        for user_data in self.config['users']:
            if not self._validate_user_config(user_data):
                logger.error(f"用户 [{user_data.get('username', '未知')}] 配置错误，跳过该用户。")
                continue

            # 加载cookies文件
            cookies_path = user_data.get('cookies_file', f"{COOKIES_DIR}/{user_data['username']}.json")
            try:
                with open(cookies_path, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                # 如果 cookies 为空，跳过该用户
                if not cookies:
                    logger.error(f"用户 [{user_data['username']}] 的 cookies 文件为空，跳过该用户")
                    continue
            except FileNotFoundError:
                logger.error(f"未找到 cookies 文件: {cookies_path}，跳过用户 [{user_data['username']}]")
                continue

            # 初始化推送服务
            push_services = []
            for push_config in user_data.get('push_services', []):
                push_type = push_config.get('type')
                config_without_type = {k: v for k, v in push_config.items() if k != 'type'}

                if push_type == 'feishu':
                    push_service = FeiShu(**config_without_type)
                elif push_type == 'serverchan':
                    push_service = ServerChan(**config_without_type)
                elif push_type == 'qiwei':
                    push_service = QiweiPush(**config_without_type)
                elif push_type == 'pushplus':
                    push_service = PushPlus(**config_without_type)
                else:
                    logger.warning(f"[推送配置] 用户[{user_data['username']}] 未知的推送类型: {push_type}")
                    continue

                push_services.append(push_service)
            
            # 创建用户配置对象
            user_agent = user_data.get('user_agent', '') or self.config.get('default_user_agent')
            logger.info(f"用户[{user_data['username']}] 使用的User-Agent: {user_agent} "
                        f"(用户配置: {user_data.get('user_agent', '未设置')}, "
                        f"默认: {self.config.get('default_user_agent')})")

            ibex = user_data.get('ibex', '')
            readtime_task_config = user_data.get('readtime_task_config', {})

            # 新任务默认开启：旧配置中没有这些键时自动补齐，显式设为 false 仍然生效
            tasks = user_data.get('tasks', {})
            if isinstance(tasks, dict):
                for new_task in ('广告加点任务', '天降福利任务'):
                    tasks.setdefault(new_task, True)

            user = UserConfig(
                username=user_data['username'],
                cookies=cookies,
                cookies_file=cookies_path,
                tasks=tasks,
                user_agent=user_agent,
                ibex=ibex,
                push_services=push_services,
                readtime_task_config=readtime_task_config,
                tokenid=user_data.get('tokenid'),
                usertype=user_data.get('usertype'),
                cookies_refresh_interval_days=user_data.get('cookies_refresh_interval_days', DEFAULT_COOKIES_REFRESH_INTERVAL_DAYS),
                last_cookies_refresh_time=user_data.get('last_cookies_refresh_time') or None,
            )
            users.append(user)
            
        return users
    
    def save_cookies(self, username: str, cookies: Dict[str, str]) -> None:
        """保存用户cookies"""
        cookies_path = f"{COOKIES_DIR}/{username}.json"
        try:
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)
            logger.debug(f"保存cookies成功: {cookies_path}")
        except Exception as e:
            logger.error(f"保存cookies失败: {e}")

    def update_last_refresh_time(self, username: str, refresh_time: Optional[str] = None) -> bool:
        """记录用户上次刷新cookies的时间点并回写config.json

        :param username: 用户名
        :param refresh_time: 指定时间字符串(格式:%Y-%m-%d %H:%M:%S)，为空则取当前本地时间
        :return: 是否记录成功
        """
        if not refresh_time:
            refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # 以磁盘上的配置为准，避免内存与磁盘不一致造成覆盖
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件失败，无法记录cookies刷新时间: {e}")
            return False

        updated = False
        for user_data in config.get('users', []):
            if user_data.get('username') == username:
                user_data['last_cookies_refresh_time'] = refresh_time
                updated = True
                break

        if not updated:
            logger.warning(f"未在配置文件中找到用户[{username}]，无法记录cookies刷新时间")
            return False

        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入配置文件失败，无法记录cookies刷新时间: {e}")
            return False

        # 同步内存中的配置与用户对象
        self.config = config
        for user in self.users:
            if user.username == username:
                user.last_cookies_refresh_time = refresh_time
                break

        logger.info(f"用户[{username}]cookies刷新时间已记录: {refresh_time}")
        return True

    def _validate_config(self):
        """全局配置校验"""
        # 最大用户数量限制说明
        if 'users' in self.config:
            if len(self.config['users']) > 3:
                logger.warning("⚠️ 注意：用户数量超过3个时将被拒绝加载")
                
        # 校验日志级别
        if 'log_level' in self.config:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if self.config['log_level'] not in valid_levels:
                logger.warning(f"日志级别配置错误，使用默认级别 INFO。有效值: {', '.join(valid_levels)}")
                self.config['log_level'] = 'INFO'
        
        # 校验日志保留天数
        if 'log_retention_days' in self.config:
            try:
                days = int(self.config['log_retention_days'])
                if days <= 0:
                    raise ValueError("日志保留天数必须为正整数")
                self.config['log_retention_days'] = days
            except (ValueError, TypeError):
                logger.warning("日志保留天数配置错误，使用默认值 7 天")
                self.config['log_retention_days'] = 7

        # 校验重试次数
        if 'retry_attempts' in self.config:
            try:
                attempts = int(self.config['retry_attempts'])
                if attempts <= 0:
                    raise ValueError("重试次数必须为正整数")
                self.config['retry_attempts'] = attempts
            except (ValueError, TypeError):
                logger.warning("重试次数配置错误，使用默认值 3 次")
                self.config['retry_attempts'] = 3
        else:
            self.config['retry_attempts'] = 3

        # 校验User-Agent 
        if "default_user_agent" in self.config:
            if not isinstance(self.config['default_user_agent'], str):
                logger.warning("默认User-Agent配置错误，使用默认值")
                self.config['default_user_agent'] = DEFAULT_USER_AGENT
        else:
            self.config['default_user_agent'] = DEFAULT_USER_AGENT
        
        # 校验用户配置
        if 'users' in self.config:
            for user_data in self.config['users']:
                self._validate_user_config(user_data)
    
    def _validate_user_config(self, user_data: dict) -> bool:
        """验证单个用户配置"""
        required_fields = ['username', 'cookies_file', 'tasks', 'user_agent', 'ibex', 'push_services']

        for field in required_fields:
            if field not in user_data:
                logger.error(f"用户[{user_data.get('username', '未知')}] 缺少必要字段: {field}")
                return False
            
        if "ibex" in user_data:
            if not isinstance(user_data['ibex'], str):
                logger.warning(f"用户[{user_data['username']}] ibex配置错误：不是字符串类型。请检查输入")
                return False
            
        if 'tokenid' in user_data:
            if not isinstance(user_data['tokenid'], str):
                logger.error(f"用户[{user_data.get('username', '未知')}] 字段[tokenid] 必须为字符串类型")
                return False
        if 'usertype' in user_data:
            if not isinstance(user_data['usertype'], str):
                logger.error(f"用户[{user_data.get('username', '未知')}] 字段[usertype] 必须为字符串类型")
                return False

        # 校验cookies自动刷新间隔（天），默认20天
        if 'cookies_refresh_interval_days' in user_data:
            try:
                interval_days = int(user_data['cookies_refresh_interval_days'])
                if interval_days <= 0:
                    raise ValueError("cookies自动刷新间隔必须为正整数")
                user_data['cookies_refresh_interval_days'] = interval_days
            except (ValueError, TypeError):
                logger.warning(f"用户[{user_data.get('username', '未知')}] cookies自动刷新间隔配置错误，使用默认值 {DEFAULT_COOKIES_REFRESH_INTERVAL_DAYS} 天")
                user_data['cookies_refresh_interval_days'] = DEFAULT_COOKIES_REFRESH_INTERVAL_DAYS
        else:
            user_data['cookies_refresh_interval_days'] = DEFAULT_COOKIES_REFRESH_INTERVAL_DAYS

        # 校验上次刷新cookies时间点（由程序记录，允许为空）
        if 'last_cookies_refresh_time' in user_data and user_data['last_cookies_refresh_time'] is not None:
            if not isinstance(user_data['last_cookies_refresh_time'], str):
                logger.warning(f"用户[{user_data.get('username', '未知')}] last_cookies_refresh_time 必须为字符串类型，已重置为空")
                user_data['last_cookies_refresh_time'] = ''

        tasks = user_data.get('tasks', {})
        if not isinstance(tasks, dict):
            logger.error(f"用户[{user_data['username']}] 任务配置必须为字典类型")
            return False

        push_services = user_data.get('push_services', [])
        if not isinstance(push_services, list):
            logger.error(f"用户[{user_data['username']}] 推送服务配置必须为列表类型")
            return False

        valid_push_types = ['feishu', 'serverchan', 'qiwei', 'pushplus']
        for push_config in push_services:
            if not isinstance(push_config, dict):
                logger.warning(f"用户[{user_data['username']}] 推送配置项不是字典类型")
                return False

            push_type = push_config.get('type')
            if push_type not in valid_push_types:
                logger.warning(f"[配置错误] 用户[{user_data['username']}] 未知的推送类型: {push_type}")
                return False

            if push_type == 'feishu':
                if not push_config.get('webhook_url'):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] 飞书推送缺少必要字段: webhook_url")
                    return False
                if not isinstance(push_config.get('webhook_url', ''), str):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] 飞书推送 webhook_url 必须为字符串类型")
                    return False
                if not isinstance(push_config.get('havesign', False), bool):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] 飞书推送 havesign 必须为布尔类型")
                    return False
                if push_config.get('havesign', False) and not push_config.get('secret', ''):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] 飞书推送启用签名校验但 secret 为空")
                    return False
                if push_config.get('havesign', False) and not isinstance(push_config.get('secret', ''), str):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] 飞书推送 secret 必须为字符串类型")
                    return False

            elif push_type == 'serverchan':
                if not push_config.get('sckey'):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] Server酱推送缺少必要字段: sckey")
                    return False
                if not isinstance(push_config.get('sckey', ''), str):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] Server酱推送 sckey 必须为字符串类型")
                    return False
            
            elif push_type == 'qiwei':
                if not push_config.get('webhook_url'):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] Qiwei推送缺少必要字段: webhook_url")
                    return False
                if not isinstance(push_config.get('webhook_url', ''), str):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] Qiwei推送 webhook_url 必须为字符串类型")
                    return False
            
            elif push_type == 'pushplus':
                if not push_config.get('token'):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] PushPlus推送缺少必要字段: token")
                    return False
                if not isinstance(push_config.get('token', ''), str):
                    logger.warning(f"[配置错误] 用户[{user_data['username']}] PushPlus推送 token 必须为字符串类型")
                    return False

        return True

class QidianClient:
    """起点客户端"""
    def __init__(self, config: UserConfig):
        self.config = config
        self.username = config.username
        self.tokenid = config.tokenid
        self.session = requests.Session()
        # 标记最近一次请求是否超时，供 TaskProcessor 统一中止任务
        self.last_request_timeout = False
        self.last_timeout_url = ''
        self._init_headers()

    def reset_timeout_state(self) -> None:
        """重置超时标记（每个任务开始前调用）"""
        self.last_request_timeout = False
        self.last_timeout_url = ''

    def _mark_timeout(self, url: str, error: Exception) -> None:
        """记录请求超时，供任务层统一判定为 timeout 并中止后续任务"""
        self.last_request_timeout = True
        self.last_timeout_url = url
        logger.error(f"接口请求超时: {url}（{error}）")

        # self.init_versions()
    
    def _init_headers(self) -> None:
        """初始化请求头"""
        self.headers_sdk = {
            'Host': 'h5.if.qidian.com',
            'Connection': 'keep-alive',
            'Accept': 'application/json, text/plain, */*',
            'helios': '1',
            'User-Agent': self.config.user_agent,
            'SDKSign': '',
            'ibex': '',
            'borgus': '',
            'tstamp': '',
            'Origin': 'https://h5.if.qidian.com',
            'X-Requested-With': 'com.qidian.QDReader',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://h5.if.qidian.com/h5/adv-develop/entry2?_viewmode=0&jump=zhanghu',
            'Accept-Language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en-US;q=0.7,en;q=0.6',
        }
        
        self.headers_qd = {
            'Cache-Control': 'max-stale=0',
            'tstamp': '',
            'QDInfo': '',
            'User-Agent': self.config.user_agent,
            'QDSign': '',
            'Host': 'druidv6.if.qidian.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip'
        }
    
    def init(self) -> bool:
        """初始化信息"""
        match = re.search(r'QDReaderAndroid/(\d+\.\d+\.\d+)/(\d+)/', self.config.user_agent)
        if match:
            self.version = match.group(1)
            self.versioncode = match.group(2)
            
            if not self.version: 
                logger.error('无法获取版本号，请检查UA')
                return False
            logger.debug(f'当前UA版本：{self.version}')

            if not self.versioncode: 
                logger.error('无法获取版本编号，请检查UA')
                return False
            logger.debug(f'当前UA版本编号：{self.versioncode}')
        else:
            logger.error('无法匹配User-Agent格式，请检查UA内容')
            return False
        
        match_2 = re.search(r'Android\s+([\d.]+)', self.config.user_agent, re.IGNORECASE)
        if match_2:
            self.android_version = match_2.group(1)
            logger.debug(f'当前Android版本：{self.android_version}')
        else:
            logger.error('无法匹配Android版本号，请检查UA内容')
            return False

        if self.versioncode in SDK_VERSION_TABLE:
            self.sdkversion = SDK_VERSION_TABLE[self.versioncode]
        else:
            self.sdkversion = '401'  # 默认值

        self.ibex = self.config.ibex
        logger.debug(f'ibex：{self.ibex}')
        if not self.ibex:
            logger.warning("ibex未配置，可能会导致验证码问题")
        
        self.qid = self.config.cookies.get('qid', '')
        logger.debug(f'qid：{self.qid}')
        self.QDInfo = self.config.cookies.get('QDInfo', '')
        self.userid = getuserid_from_QDInfo(self.QDInfo)
        logger.debug(f'userid：{self.userid}')
        return True
    
    def _handle_response(self, response: requests.Response, 
                        error_msg: str = "请求失败") -> Dict[str, Any]:
        """处理响应并检测验证码"""
        try:
            result = response.json()
            logger.debug(f"响应数据: {result}")
            
            # 检测验证码
            risk_conf = result.get('Data', {}).get('RiskConf', {})
            ban_id = risk_conf.get('BanId', 0)  # 默认为0

            # 强制转换为整数并判断
            try:
                ban_id = int(ban_id)
            except (ValueError, TypeError):
                ban_id = 0

            # 非0即触发验证码
            if ban_id != 0:
                result['is_captcha'] = True
                result['captcha_data'] = risk_conf.copy()
                
            return result
        except json.JSONDecodeError:
            logger.error(f"{error_msg}: {response.text}")
            raise QidianError(f"{error_msg}: {response.text}")
        
    def _make_qd_request(self, url: str, params: dict = None, data: dict = None, method: str = 'POST',
                         extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """创建qd类型请求"""
        # 添加随机延迟
        time.sleep(random.uniform(1, 3))  # 随机延迟 1~3 秒

        ts = str(int(time.time() * 1000))
        params = params or {}
        data = data or {}
        
        data_encrypt = data.copy() if data else params.copy()

        QDSign = getQDSign(ts, data_encrypt, self.version, self.qid, userid=self.userid)
        QDInfo = getQDInfo_byQDInfo(ts, self.QDInfo)
        borgus = getborgus(ts, data_encrypt, self.versioncode, self.qid)
        ibex = getibex_byibex(ts, self.ibex)
        
        # 更新headers
        headers = self.headers_qd.copy()
        headers.update({
            'tstamp': ts,
            'QDInfo': QDInfo,
            'QDSign': QDSign,
            'ibex': ibex,
            'borgus': borgus
        })
        if extra_headers:
            headers.update(extra_headers)

        # 更新 cookies
        self.config.cookies['QDInfo'] = QDInfo

        # 根据 method 显式选择请求方式
        try:
            if method.upper() == 'POST':
                response = self.session.post(url, params=params, data=data, headers=headers,
                                             cookies=self.config.cookies, timeout=REQUEST_TIMEOUT)
            else:
                response = self.session.get(url, params=params, headers=headers,
                                            cookies=self.config.cookies, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as e:
            self._mark_timeout(url, e)
            raise QidianTimeoutError(f"接口请求超时: {url}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {url}（{e}）")
            raise QidianError(f"网络请求失败: {url}") from e

        return self._handle_response(response, "qd类型请求失败")

    def _make_sdk_request(self, url: str, params: dict = None, data: dict = None, method: str = 'POST') -> Dict[str, Any]:
        """创建sdk类型请求"""
        # 添加随机延迟
        time.sleep(random.uniform(1, 3))  # 随机延迟 1~3 秒

        ts = str(int(time.time() * 1000))
        params = params or {}
        data = data or {}
        
        data_encrypt = data.copy() if data else params.copy()
        
        SDKSign = getSDKSign(ts, data_encrypt, self.version, self.qid, userid=self.userid)
        QDInfo = getQDInfo_byQDInfo(ts, self.QDInfo)
        borgus = getborgus(ts, data_encrypt, self.versioncode, self.qid)
        ibex = getibex_byibex(ts, self.ibex)
        
        # 更新headers
        headers = self.headers_sdk.copy()
        headers.update({
            'tstamp': ts,
            'SDKSign': SDKSign,
            'ibex': ibex,
            'borgus': borgus
        })

        # 更新 cookies
        self.config.cookies['QDInfo'] = QDInfo
        
         # 根据 method 显式选择请求方式
        try:
            if method.upper() == 'POST':
                if params=={} or params==None:
                    response = self.session.post(url, data=data, headers=headers,
                                                 cookies=self.config.cookies, timeout=REQUEST_TIMEOUT)
                else:
                    response = self.session.post(url, params=params, data=data, headers=headers,
                                                 cookies=self.config.cookies, timeout=REQUEST_TIMEOUT)
            else:
                if params=={} or params==None:
                    response = self.session.get(url, headers=headers, cookies=self.config.cookies,
                                                data=data, timeout=REQUEST_TIMEOUT)
                else:
                    response = self.session.get(url, params=params, headers=headers,
                                                cookies=self.config.cookies, data=data, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as e:
            self._mark_timeout(url, e)
            raise QidianTimeoutError(f"接口请求超时: {url}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {url}（{e}）")
            raise QidianError(f"网络请求失败: {url}") from e

        return self._handle_response(response, "sdk类型请求失败")
    
    def _solve_captcha(self, captcha_data: dict) -> Optional[dict]:
        """
        解决验证码的核心方法
        :param captcha_data: 从API返回的RiskConf数据
        :return: 包含randstr和ticket的字典，或None表示失败
        """
        ban_id = captcha_data.get('BanId', 0)
        
        # 检查BanId是否为2
        try:
            ban_id = int(ban_id)
        except (TypeError, ValueError):
            ban_id = 0
        
        if ban_id != 2:
            logger.error(f"非预料的BanId: {ban_id}，可能是设备风控或其他原因")
            return False
        
        # 检查CaptchaAId是否支持
        captcha_a_id = captcha_data.get('CaptchaAId', '')
        
        if captcha_a_id == "198420051":
            try:
                logger.info("开始进行验证码处理")
                from Captcha import main
                # 使用无头模式，避免干扰用户
                captcha_result = main(tokenid=self.tokenid, captcha_a_id=captcha_a_id, user_agent=self.config.user_agent)
                logger.debug(f"验证码识别结果: {captcha_result}")
                # 验证结果格式
                if not isinstance(captcha_result, dict) or 'code' not in captcha_result:
                    logger.error("验证码识别返回格式错误")
                    return None
                    
                if captcha_result.get('code') == 0:
                    logger.info(f"验证码识别成功: randstr={captcha_result['randstr']}, ticket={captcha_result['ticket'][:10]}...")
                    return captcha_result
                
                elif captcha_result.get('code') == 12:
                    logger.error(f"验证码识别失败: {captcha_result['message']}")
                    return None
                
                elif captcha_result.get('code') == 50:
                    logger.error(f"验证码识别失败: {captcha_result['message']}")
                    return None
                
                elif captcha_result.get('code') == 666:
                    logger.error(f"验证码识别失败: {captcha_result['message']}")
                    return None
                
                else:
                    logger.error(f"未知返回：{captcha_result}")
                    return None
                
            except Exception as e:
                logger.exception(f"验证码处理异常: {e}")
                return None
        
        elif captcha_a_id == "1600000770":
            try:
                logger.info("开始进行验证码处理")
                from Captcha import main_slider
                # 使用无头模式，避免干扰用户
                captcha_result = main_slider(tokenid=self.tokenid, captcha_a_id=captcha_a_id, user_agent=self.config.user_agent)
                logger.debug(f"验证码识别结果: {captcha_result}")
                # 验证结果格式
                if not isinstance(captcha_result, dict) or 'code' not in captcha_result:
                    logger.error("验证码识别返回格式错误")
                    return None
                    
                if captcha_result.get('code') == 0:
                    logger.info(f"验证码识别成功: randstr={captcha_result['randstr']}, ticket={captcha_result['ticket'][:10]}...")
                    return captcha_result
                
                elif captcha_result.get('code') == 12:
                    logger.error(f"验证码识别失败: {captcha_result['message']}")
                    return None
                
                elif captcha_result.get('code') == 50:
                    logger.error(f"验证码识别失败: {captcha_result['message']}")
                    return None
                
                elif captcha_result.get('code') == 666:
                    logger.error(f"验证码识别失败: {captcha_result['message']}")
                    return None
                
                else:
                    logger.error(f"未知返回：{captcha_result}")
                    return None
                
            except Exception as e:
                logger.exception(f"验证码处理异常: {e}")
                return None
        else:
            logger.error(f"未实现的验证码类型: {captcha_a_id}，当前仅支持198420051(点选)和1600000770(滑块)")
            return False

    def _make_request_with_captcha(self, url: str, data: dict, method: str = 'POST', max_captcha_attempts: int = 3) -> dict:
        """
        带验证码自动处理的请求方法
        :param url: 请求URL
        :param data: 请求数据
        :param method: 请求方法
        :param max_captcha_attempts: 最大验证码尝试次数
        :return: 处理后的结果
        """
        captcha_attempt = 0
        original_data = data.copy()
        
        # 记录上一次的解答结果，用于区分是"首次触发验证码"还是"提交验证码解答"
        captcha_solution = None 
        
        while captcha_attempt <= max_captcha_attempts:
            request_data = original_data.copy()
            
            # 只有在成功拿到了打码结果的情况下，才附加验证码参数去验证
            if captcha_attempt > 0 and captcha_solution:
                request_data = {
                    'taskId': original_data.get('taskId', ''),
                    'sessionKey': str(captcha_data.get('SessionKey', '')),
                    'banId': str(captcha_data.get('BanId', '0')),
                    'captchaTicket': captcha_solution.get('ticket', ''),
                    'captchaRandStr': captcha_solution.get('randstr', ''),
                    'challenge': '',
                    'validate': '',
                    'seccode': '',
                }
            
            result = self._make_sdk_request(url, data=request_data, method=method)
            
            # 检查是否触发了验证码（无论是首次触发，还是上一次提交的解答错误被重新打回）
            if result.get('is_captcha'):
                if not self.tokenid:
                    logger.info("未设置tokenid，跳过验证码处理")
                    return {
                        'status': 'captcha_failed', 
                        'msg': '跳过验证码处理',
                        'captcha_data': result.get('captcha_data')
                    }

                captcha_attempt += 1
                captcha_data = result['captcha_data']
                
                logger.info(f"第{captcha_attempt}次尝试处理验证码...")
                
                # 尝试解决验证码
                captcha_solution = self._solve_captcha(captcha_data)
                
                if captcha_solution is False:
                    return {
                        'status': 'captcha', 
                        'msg': '无法处理的验证码类型',
                        'captcha_data': captcha_data
                    }

                if captcha_solution is None:
                    logger.warning(f"验证码识别服务返回失败，准备重试 (已尝试 {captcha_attempt}/{max_captcha_attempts} 次)")
                    # 识别失败时，不要带着错误参数去请求，下一个循环会用 original_data 重新触发一次验证码
                    continue  

                # 识别成功，进入下一次循环去提交 ticket
                continue  
            
            # 如果没有进入 is_captcha 的分支，说明请求成功通过了风控
            return result
        
        # 尝试次数用尽
        return {
            'status': 'captcha_failed',
            'msg': f'验证码处理或校验失败，已达到最大尝试次数 ({max_captcha_attempts}次)',
            'captcha_data': locals().get('captcha_data', {})
        }

    def ptlogin_checkstatus(self):
        '''检查登录状态, 获取cookies有效期'''
        url = 'https://ptlogin.yuewen.com/sdk/checkstatus'
        ts = str(int(time.time() * 1000))
        
        headers = {
            'Cookie': f'ywguid={self.config.cookies.get("ywguid","")};ywkey={self.config.cookies.get("ywkey","")};',
            'referer': 'http://android.qidian.com',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': 'ptlogin.yuewen.com',
            'Connection': 'Keep-Alive',
            'User-Agent': 'okhttp/3.12.6',
        }
        data = {
            'areaid': '30',
            'format': 'json',
            'returnurl': 'http://www.qidian.com',
            'source': '1000009',
            'ticket': '0',
            'alk': ''.join(random.choices(string.ascii_letters + string.digits, k=12)),
            'auto': '1',
            'ibex': getibex_byibex(ts, self.ibex),
            'appid': '12',
            'osversion': f'Android{self.android_version}_{self.version}_{self.versioncode}',
            'version': self.versioncode,
            'sdkversion': self.sdkversion,
            'signature': getsignature(ts, self.qid),
            'referer': 'http://android.qidian.com',
            'autotime': '30',
        }
        try:
            response = self.session.post(url=url, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as e:
            self._mark_timeout(url, e)
            return {"NeedRefresh": False, "status": "timeout", "expired_time": ""}
        except requests.exceptions.RequestException as e:
            logger.error(f"[ptlogin_checkstatus] 网络请求失败: {e}")
            return {"NeedRefresh": False, "status": "failed", "expired_time": ""}
        logger.debug(f"[ptlogin_checkstatus]: {response.text}")
        res = response.json()
        if not res:
            logger.error("[ptlogin_checkstatus] 获取登录状态失败")
            return {"NeedRefresh": False, "status": "failed", "expired_time": ""}
        if res.get('code') != 0:
            # if res.get('code') == -31001:
            #     logger.error("[ptlogin_checkstatus] 当前登录状态已失效且无法自动更新cookies，请重新手动登录")
            #     return {"NeedRefresh": False, "status": "Manual", "expired_time": ""}
            logger.warning(f"[ptlogin_checkstatus] 当前登录状态已失效 code: {res.get('code')}")
            if res.get('data'):
                if res["data"].get("autoLoginExpiredTime"):
                    expired_time = res["data"]["autoLoginExpiredTime"]
                    expired_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expired_time))
                    logger.info(f"[ptlogin_checkstatus] 登录有效期: {expired_time_str}")
                    return {"NeedRefresh": True, "status": "expired", "expired_time": expired_time}
                return {"NeedRefresh": True, "status": "error [autoLoginExpiredTime]", "expired_time": ""}
            return {"NeedRefresh": True, "status": "error [code]", "expired_time": ""}
        if res.get('data'):
            if res["data"].get("autoLoginExpiredTime"):
                expired_time = res["data"]["autoLoginExpiredTime"]
                expired_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expired_time))
                logger.info(f"[ptlogin_checkstatus] 登录有效期: {expired_time_str}")
                return {"NeedRefresh": False, "status": "active", "expired_time": expired_time_str}
            return {"NeedRefresh": False, "status": "active error [autoLoginExpiredTime]", "expired_time": ""}
        return {"NeedRefresh": False, "status": "active error [data]", "expired_time": ""}

    def login_druidv6(self):
        url = "https://druidv6.if.qidian.com/argus/api/v2/user/login"

        headers = {
            'User-Agent': self.config.user_agent,
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Host': 'druidv6.if.qidian.com',
            'Content-Type': 'application/x-www-form-urlencoded',
            'tstamp': "",
            'QDInfo': "",
            'borgus': "",
            'ibex': "",
            'QDSign': "",
        }

        data = {
            'fromSource': "1000009",
            'loginfrom': "0",
            'areaId': self.config.cookies.get('areaId'),
            'isFirstRegister': "false",
            'ywguid': self.config.cookies.get('ywguid'),
            'appId': self.config.cookies.get('appId'),
            'ywkey': self.config.cookies.get('ywkey'),
        }

        cookies = {
            'appId': self.config.cookies.get('appId'),
            'areaId': self.config.cookies.get('areaId'),
            'lang': "cn",
            'mode': "normal",
            'bar': "44",
            'qid': self.config.cookies.get('qid'),
            'qidth': self.config.cookies.get('qidth'),
            'ywguid': self.config.cookies.get('ywguid'),
            'ywkey': self.config.cookies.get('ywkey'),
            'QDInfo': self.config.cookies.get('QDInfo'),
        }

        data_encrypt = data.copy()
        ts = str(int(time.time() * 1000))
        QDSign = getQDSign(ts, data_encrypt, self.version, self.qid, self.userid)
        QDInfo = getQDInfo_byQDInfo(ts, self.QDInfo)
        borgus = getborgus(ts, data_encrypt, self.versioncode, self.qid)

        ibex = getibex_byibex(ts, self.ibex)

        headers.update({
            'tstamp': ts,
            'QDInfo': QDInfo,
            'borgus': borgus,
            'QDSign': QDSign,
            'ibex': ibex,
        })
        cookies.update({
            'QDInfo': QDInfo,
        })

        try:
            response = self.session.post(
                url, 
                data=data, 
                headers=headers, 
                cookies=cookies, 
                timeout=REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout as e:
            self._mark_timeout(url, e)
            logger.error("登录druidv6.if.qidian.com超时")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"登录druidv6.if.qidian.com请求异常: {e}")
            return False
        logger.info(f"[login_druidv6] 原始响应: {response.text}")
    
        res = response.json()

        if res.get('Result') != 0 and res.get('Result') != "0":
            logger.error("登录druidv6.if.qidian.com失败")
            return False
        if not res.get("Data") or not res.get("Data").get("LoginResult"):
            logger.error("登录druidv6.if.qidian.com失败，返回data为空")
            return False
        cmfuToken = str(res['Data']['LoginResult'].get('CmfuToken'))
        cookies_new = self.config.cookies.copy()
        cookies_new.update({
            'cmfuToken': cmfuToken,
        })
        return cookies_new
    
    def update_cookies(self):
        '''更新cookies函数'''
        cookies_old = self.config.cookies.copy()
        logger.debug(f"[update_cookies] cookies_old: {cookies_old}")
        cookies_new = self.login_druidv6()
        logger.debug(f"[update_cookies] cookies_new: {cookies_new}")
        if not cookies_new:
            return False, "更新cookies失败"
        if cookies_new == cookies_old:
            logger.info("[update_cookies] 服务端返回的cookies与本地一致（cmfuToken未变化），无需更新")
            return True, "cookies未更新（cmfuToken未变化）"
        logger.info(f"保留旧cookies到[{COOKIES_DIR}/{self.username}_old.json] 中")
        try:
            # 保留旧cookies到f"{COOKIE_DIR}/{self.username}_old.json"
            with open(f"{COOKIES_DIR}/{self.username}_old.json", 'w', encoding='utf-8') as f:
                json.dump(cookies_old, f, ensure_ascii=False, indent=4)
                logger.info(f"保留旧cookies成功：{f.name}")
        except Exception as e:
            logger.error(f"保存旧cookies失败：{e}")
            return False, "保留旧cookies失败"
        logger.info("开始写入更新后的cookies文件")
        try:
            with open(self.config.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies_new, f, ensure_ascii=False, indent=4)
                logger.info("更新成功")
        except Exception as e:
            logger.error(f"写入更新后的cookies文件失败：{e}")
            return False, "写入新cookies失败"
        
        # 更新cookies
        self.config.cookies = cookies_new
        return True, "更新cookies成功"

    def check_login(self) -> Optional[str]:
        """检查登录状态"""
        ts = str(int(time.time() * 1000))
        url = "https://druidv6.if.qidian.com/argus/api/v1/user/getprofile"
        
        # 生成签名
        params = {}
        params_encrypt = {}
        QDSign = getQDSign(ts, params_encrypt, self.version, self.qid, userid=self.userid)
        QDInfo = getQDInfo_byQDInfo(ts, self.QDInfo)
        borgus = getborgus(ts, params_encrypt, self.versioncode, self.qid)
        
        # 设置请求头
        headers = self.headers_qd.copy()
        headers.update({
            'tstamp': ts,
            'QDInfo': QDInfo,
            'QDSign': QDSign,
            'borgus': borgus
        })

        # 更新 cookies
        self.config.cookies['QDInfo'] = QDInfo
        
        try:
            response = self.session.get(url, params=params, cookies=self.config.cookies,
                                        headers=headers, timeout=REQUEST_TIMEOUT)
            result = self._handle_response(response, "登录检测失败")
            
            if result.get('Data', {}).get('Nickname'):
                return result['Data']['Nickname']
            return None
        except requests.exceptions.Timeout as e:
            self._mark_timeout(url, e)
            return None
        except Exception as e:
            logger.error(f"登录检测异常: {e}")
            return None

    def check_riskstatus(self) -> Optional[str]:
        """检查福利中心风险状态"""
        url = 'https://h5.if.qidian.com/argus/api/v1/common/risk/check'
        params = {
            'appId': '1999'
        }
        result = self._make_sdk_request(url, params=params, method='GET')

        # 检测登录状态
        login_status = True
        if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
            login_status = False

        # 检测风险状态
        risk_status = False
        if result.get('Result') == 0 or result.get('Result') == "0":
            if result.get('Data', {}).get('RiskConf'):
                risk_status = True

        return {'login_status': login_status, 'risk_status': risk_status}
        

    def qdsign(self) -> dict:
        """执行签到任务"""
        try:
            url = "https://druidv6.if.qidian.com/argus/api/v2/checkin/checkin"
            data = {
                'sessionKey': '',
                'banId': '0',
                'captchaTicket': '',
                'captchaRandStr': '',
                'challenge': '',
                'validate': '',
                'seccode': '',
            }
            
            result = self._make_qd_request(url, data=data, method='POST')

            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

            if result.get('Result') == -91002:
                return {'status': 'success', 'msg': '今日已签到'}
            
            if result.get('Result') == 0 and result.get('Data', {}).get('HasCheckIn', '') == 1:
                return {'status': 'success', 'msg': '签到成功'}
                
            if result.get('is_captcha'):
                return {'status': 'captcha', 'msg': '触发验证码', 'captcha_data': result['captcha_data']}
                
            return {'status': 'failed', 'msg': f"签到失败: {result.get('Message', '未知原因')}"}
            
        except Exception as e:
            return {'status': 'error', 'msg': f'执行异常: {str(e)}'}

    def get_adv_job(self) -> Dict[str, Any]:
        """获取激励任务列表"""
        # url = "https://h5.if.qidian.com/argus/api/v1/video/adv/mainPage"
        url = "https://h5.if.qidian.com/argus/api/v2/video/adv/mainPage"
        result = self._make_sdk_request(url,method='GET')

        # if not result.get('Data') or not result['Data'].get('VideoBenefitModule'):
        if not result.get('Data') or not result['Data'].get('DailyBenefitModule'):
            raise QidianError("获取激励任务列表失败")
            
        return result

    def do_adv_job(self, task_id: str) -> dict:
        """完成单个激励任务"""
        url = "https://h5.if.qidian.com/argus/api/v1/video/adv/finishWatch"
        data = {
            'taskId': task_id,
            'BanId': '0',
            'BanMessage': '',
            'CaptchaAId': '',
            'CaptchaType': '0',
            'CaptchaURL': '',
            'Challenge': '',
            'Gt': '',
            'NewCaptcha': '0',
            'Offline': '0',
            'PhoneNumber': '',
            'SessionKey': '',
        }
        
        result = self._make_request_with_captcha(url, data, method='POST')

        # 处理特殊结果
        if isinstance(result, dict) and result.get('status') == 'captcha_failed':
            return result
        
        # 处理特殊结果
        if isinstance(result, dict) and result.get('status') == 'captcha':
            return result
        
        # 处理登录失效情况
        if isinstance(result, dict):
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

        # 检查是否是成功的API响应
        if isinstance(result, dict) and result.get('Result') in (0, "0"):
            return {'status': 'success'}

        # 处理其他可能的错误情况
        logger.error(f"激励任务执行失败: {result}")
        return {'status': 'failed', 'raw_response': result}
    
    def _finish_watch_with_captcha(self, url: str, data: dict,
                                   sign_type: str = 'qd',
                                   extra_headers: Optional[Dict[str, str]] = None,
                                   max_captcha_attempts: int = 3) -> Dict[str, Any]:
        """发送 finishWatch 请求，触发验证码时保留 taskId/gradientLevel 等原始参数"""
        captcha_attempt = 0
        captcha_solution = None
        captcha_data = {}

        while captcha_attempt <= max_captcha_attempts:
            request_data = data.copy()

            if captcha_attempt > 0 and captcha_solution:
                request_data.update({
                    'sessionKey': str(captcha_data.get('SessionKey', '')),
                    'banId': str(captcha_data.get('BanId', '0')),
                    'captchaTicket': captcha_solution.get('ticket', ''),
                    'captchaRandStr': captcha_solution.get('randstr', ''),
                    'challenge': '',
                    'validate': '',
                    'seccode': '',
                })

            if sign_type == 'sdk':
                result = self._make_sdk_request(url, data=request_data, method='POST')
            else:
                result = self._make_qd_request(url, data=request_data, method='POST', extra_headers=extra_headers)

            if result.get('is_captcha'):
                if not self.tokenid:
                    logger.info("未设置tokenid，跳过验证码处理")
                    return {
                        'status': 'captcha_failed',
                        'msg': '跳过验证码处理',
                        'captcha_data': result.get('captcha_data')
                    }

                captcha_attempt += 1
                captcha_data = result['captcha_data']
                logger.info(f"第{captcha_attempt}次尝试处理广告·加点验证码...")
                captcha_solution = self._solve_captcha(captcha_data)

                if captcha_solution is False:
                    return {
                        'status': 'captcha',
                        'msg': '无法处理的验证码类型',
                        'captcha_data': captcha_data
                    }

                if captcha_solution is None:
                    logger.warning(f"验证码识别服务返回失败，准备重试 (已尝试 {captcha_attempt}/{max_captcha_attempts} 次)")
                continue

            return result

        return {
            'status': 'captcha_failed',
            'msg': f'验证码处理或校验失败，已达到最大尝试次数 ({max_captcha_attempts}次)',
            'captcha_data': captcha_data
        }

    def do_reading_adv_job(self, task_id: str) -> dict:
        """完成单个“广告·加点”子任务（gradientLevel 依次为 1/2/3）"""
        url = "https://h5.if.qidian.com/argus/api/v1/video/adv/finishWatch"
        # 实测该接口不需要 cecelia、gorgon、abtest-gzip，置空即可
        extra_headers = {
            'cecelia': '',
            'gorgon': '',
            'abtest-gzip': '',
        }
        rewards = []

        try:
            for gradient_level in (1, 2, 3):
                data = {
                    'taskId': task_id,
                    'gradientLevel': str(gradient_level),
                    'type': '1',
                    'h5': '0',
                    'oneOff': '0',
                    'sessionKey': '',
                    'banId': '0',
                    'captchaTicket': '',
                    'captchaRandStr': '',
                    'challenge': '',
                    'validate': '',
                    'seccode': '',
                }

                result = self._finish_watch_with_captcha(url, data, sign_type='qd', extra_headers=extra_headers)

                # 验证码/登录失效等特殊结果直接向上传递
                if isinstance(result, dict) and result.get('status') in ('captcha', 'captcha_failed', 'Unauthorized'):
                    return result

                if isinstance(result, dict) and result.get("status", 200) == 401 and result.get("error", "") == "Unauthorized":
                    logger.error("登录已失效，请重新登录或者抓取cookies")
                    return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

                if not isinstance(result, dict) or result.get('Result') not in (0, "0"):
                    logger.error(f"广告·加点子任务[{task_id}] gradientLevel={gradient_level} 执行失败: {result}")
                    return {'status': 'failed', 'raw_response': result, 'msg': '广告·加点任务执行失败'}

                for reward in (result.get('Data') or {}).get('RewardList') or []:
                    desc = reward.get('Desc')
                    if desc:
                        rewards.append(desc)
                        logger.info(f"广告·加点奖励: {desc}")

                logger.info(f"广告·加点子任务[{task_id}] gradientLevel={gradient_level} 完成")
                if gradient_level < 3:
                    time.sleep(random.uniform(1, 2))

            return {'status': 'success', 'rewards': rewards}

        except Exception as e:
            logger.error(f"广告·加点子任务[{task_id}]执行异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '广告·加点任务异常，请检查日志'}


    def reading_advjob(self) -> dict:
        """执行阅读页“广告·加点”任务（只要 ReadingPageTaskModule.TaskList 中存在并已解锁就执行）"""
        try:
            result = self.get_adv_job()
            # 检测登录状态
            if result.get("status", 200) == 401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

            module = (result.get('Data') or {}).get('ReadingPageTaskModule') or {}
            task_list = module.get('TaskList') or []

            # 接口未返回该模块或 TaskList 为空时直接跳过（不依据版本号判断）
            if not task_list:
                logger.info("当前账号没有广告·加点任务，跳过（该任务仅新版本有效）")
                return {'status': 'success', 'msg': '当前版本无广告·加点任务（仅新版本有效）'}

            def _status_value(task: dict) -> int:
                try:
                    return int(task.get('Status', 0))
                except (TypeError, ValueError):
                    return 0

            def _pick_pending(tasks: List[dict]) -> List[dict]:
                """筛选未完成且已解锁（Status>=0）的子任务"""
                return [
                    task for task in tasks
                    if task.get('IsFinished') != 1
                    and _status_value(task) >= 0
                ]

            target_tasks = task_list
            if target_tasks and all(task.get('IsFinished') == 1 for task in target_tasks):
                logger.info("广告·加点任务已完成")
                return {'status': 'success', 'msg': '任务已完成'}

            if not _pick_pending(task_list):
                logger.info("广告·加点任务暂无可执行子任务（需阅读解锁）")
                return {'status': 'success', 'msg': '暂无可执行子任务，需阅读解锁'}

            rewards = []
            attempted = set()

            # 子任务存在链式解锁：每完成一个重新拉取主页面，继续处理新解锁的任务
            for _ in range(len(target_tasks) + 1):
                active_tasks = [
                    task for task in _pick_pending(task_list)
                    if task.get('TaskId') not in attempted
                ]
                if not active_tasks:
                    break

                task = active_tasks[0]
                task_id = task.get('TaskId')
                attempted.add(task_id)
                logger.info(
                    f"开始执行广告·加点子任务: {task.get('Title', '广告·加点')} "
                    f"({task_id}) Process={task.get('Process', 0)}/{task.get('Total', 0)}"
                )

                task_result = self.do_reading_adv_job(task_id)

                if task_result.get('status') == 'success':
                    rewards.extend(task_result.get('rewards') or [])
                    time.sleep(random.randint(1, 2))
                elif task_result.get('status') == 'Unauthorized':
                    logger.error("登录已失效，请重新登录或者抓取cookies")
                    return {'status': 'Unauthorized', 'msg': '登录已失效，请重新抓取cookies'}
                elif task_result.get('status') == 'captcha':
                    logger.warning("无法处理的验证码类型")
                    return {'status': task_result.get('status', 'captcha'), 'result': task_result, 'msg': '无法处理的验证码类型'}
                elif task_result.get('status') == 'captcha_failed':
                    logger.error(f"验证码处理失败: {task_result.get('msg')}")
                    return {'status': task_result.get('status', 'captcha'), 'result': task_result, 'msg': task_result.get('msg')}
                else:
                    logger.error(f"执行广告·加点任务失败: {task_result.get('msg', '未知原因')}")
                    return {
                        'status': 'failed',
                        'msg': task_result.get('msg', '执行广告·加点任务失败'),
                        'raw_response': task_result.get('raw_response')
                    }

                # 重新拉取任务列表，处理链式解锁
                check_result = self.get_adv_job()
                if check_result.get("status", 200) == 401 and check_result.get("error", "") == "Unauthorized":
                    logger.error("登录已失效，请重新登录或者抓取cookies")
                    return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
                task_list = (check_result.get('Data') or {}).get('ReadingPageTaskModule', {}).get('TaskList') or []

            # 最终校验
            check_result = self.get_adv_job()
            if check_result.get("status", 200) == 401 and check_result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

            check_list = (check_result.get('Data') or {}).get('ReadingPageTaskModule', {}).get('TaskList') or []
            check_targets = check_list

            if not check_targets or all(task.get('IsFinished') == 1 for task in check_targets):
                msg = '任务已完成'
                if rewards:
                    msg += f"，获得: {'、'.join(dict.fromkeys(rewards))}"
                logger.info(f"广告·加点任务完成{('，获得: ' + '、'.join(dict.fromkeys(rewards))) if rewards else ''}")
                return {'status': 'success', 'msg': msg}

            locked_count = sum(1 for task in check_targets if _status_value(task) < 0)
            if locked_count:
                logger.info(f"广告·加点任务仍有{locked_count}个子任务未解锁（需阅读）")
                return {'status': 'success', 'msg': f'已完成可执行子任务，剩余{locked_count}个需阅读解锁'}

            logger.error("广告·加点任务未完成")
            return {'status': 'failed', 'code': 10086, 'msg': '任务未完成'}

        except Exception as e:
            logger.error(f"广告·加点任务异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '任务异常，请检查日志'}


    def get_main_page_dialog(self) -> Dict[str, Any]:
        """获取天降福利弹窗任务"""
        url = "https://h5.if.qidian.com/argus/api/v2/video/adv/mainPageDialog"
        return self._make_sdk_request(url, method='GET')

    def do_dialog_adv_job(self, task_id: str) -> dict:
        """完成天降福利广告任务（SDKSign + 新式参数，无需 gradientLevel）"""
        url = "https://h5.if.qidian.com/argus/api/v1/video/adv/finishWatch"
        data = {
            'taskId': task_id,
            'type': '1',
            'h5': '0',
            'oneOff': '0',
            'sessionKey': '',
            'banId': '0',
            'captchaTicket': '',
            'captchaRandStr': '',
            'challenge': '',
            'validate': '',
            'seccode': '',
        }

        try:
            result = self._finish_watch_with_captcha(url, data, sign_type='sdk')

            # 验证码/登录失效等特殊结果直接向上传递
            if isinstance(result, dict) and result.get('status') in ('captcha', 'captcha_failed', 'Unauthorized'):
                return result

            if isinstance(result, dict) and result.get("status", 200) == 401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

            if not isinstance(result, dict) or result.get('Result') not in (0, "0"):
                logger.error(f"天降福利任务[{task_id}]执行失败: {result}")
                return {'status': 'failed', 'raw_response': result, 'msg': '天降福利任务执行失败'}

            rewards = []
            for reward in (result.get('Data') or {}).get('RewardList') or []:
                desc = reward.get('Desc')
                if desc:
                    rewards.append(desc)
                    logger.info(f"天降福利奖励: {desc}")

            logger.info(f"天降福利任务[{task_id}]完成")
            return {'status': 'success', 'rewards': rewards}

        except Exception as e:
            logger.error(f"天降福利任务[{task_id}]执行异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '天降福利任务异常，请检查日志'}

    def dialog_advjob(self) -> dict:
        """执行天降福利任务（只要 mainPageDialog 返回有效 TaskId 就执行）"""
        try:
            result = self.get_main_page_dialog()
            # 检测登录状态
            if result.get("status", 200) == 401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

            data = result.get('Data') or {}
            task_id = str(data.get('TaskId') or '')
            # TaskId 为空或 0 表示当前没有天降福利任务（旧版本/已领取/未触发）
            if not task_id or task_id == '0':
                logger.info("当前没有天降福利任务，跳过（该任务仅新版本有效）")
                return {'status': 'success', 'msg': '当前无天降福利任务（仅新版本有效）'}

            dialog_info = data.get('FirstDialog') or {}
            logger.info(
                f"开始执行天降福利任务: {dialog_info.get('Title', '天降福利')} ({task_id}) "
                f"{dialog_info.get('SubTitle', '')}"
            )

            task_result = self.do_dialog_adv_job(task_id)

            if task_result.get('status') == 'success':
                rewards = task_result.get('rewards') or []
                msg = '任务已完成'
                if rewards:
                    msg += f"，获得: {'、'.join(dict.fromkeys(rewards))}"
                logger.info(f"天降福利任务完成{('，获得: ' + '、'.join(dict.fromkeys(rewards))) if rewards else ''}")
                return {'status': 'success', 'msg': msg}
            elif task_result.get('status') == 'Unauthorized':
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {'status': 'Unauthorized', 'msg': '登录已失效，请重新抓取cookies'}
            elif task_result.get('status') == 'captcha':
                logger.warning("无法处理的验证码类型")
                return {'status': task_result.get('status', 'captcha'), 'result': task_result, 'msg': '无法处理的验证码类型'}
            elif task_result.get('status') == 'captcha_failed':
                logger.error(f"验证码处理失败: {task_result.get('msg')}")
                return {'status': task_result.get('status', 'captcha'), 'result': task_result, 'msg': task_result.get('msg')}
            else:
                logger.error(f"执行天降福利任务失败: {task_result.get('msg', '未知原因')}")
                return {
                    'status': 'failed',
                    'msg': task_result.get('msg', '执行天降福利任务失败'),
                    'raw_response': task_result.get('raw_response')
                }

        except QidianTimeoutError as e:
            logger.error(f"天降福利任务接口超时: {e}")
            return {'status': 'timeout', 'msg': str(e)}
        except QidianError as e:
            # 旧版本或接口不可用时跳过，不影响其他任务
            logger.warning(f"获取天降福利任务失败（该任务仅新版本有效）: {e}")
            return {'status': 'success', 'msg': '当前版本无天降福利任务（仅新版本有效）'}
        except Exception as e:
            logger.error(f"天降福利任务异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '任务异常，请检查日志'}


    def get_chapters(self, bookid: str) -> dict:
        """获取章节列表"""
        url = f'https://wxapp.qidian.com/api/book/categoryV2?bookId={bookid}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36',
        }
        try: 
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            res_text = response.text
            logger.debug(f"获取章节列表: {res_text}")
            result = response.json()
            if result.get('code') != 0:
                logger.error(f"响应结果错误：{result.get('msg')}")
                return []
            if not result.get('data'): 
                logger.error(f"获取数据失败：{result.get('msg')}")
                return []
            if not result['data'].get('bookName'):
                logger.error("获取书名失败")
                return []
            logger.info(f"获取章节列表成功，书名：{result['data']['bookName']}")
            volumelist = result.get('data', {}).get('vs')
            chapterlist = []
            for volume in volumelist: 
                for chapter in volume.get('cs', []):
                    chapterlist.append({
                        'chapterid': chapter.get('id'),
                        'chapterName': chapter.get('cN'),
                        'postTime': chapter.get('uT'),
                        'chapterWordscount': chapter.get('cnt'),
                    })
            return chapterlist
        except requests.exceptions.Timeout as e:
            self._mark_timeout(url, e)
            raise QidianTimeoutError(f"获取章节列表超时: {url}") from e
        except Exception as e:
            logger.error(f"获取章节列表异常: {e}")
            return []
        
    def do_readtime_report(self, chapter_Info: dict):
        """上报阅读时长"""
        chapterreadtimeinfo = json.dumps(chapter_Info, separators=(',', ':'))

        url = "https://druidv6.if.qidian.com/argus/api/v2/common/statistics/readingtime"
        headers = {
            'tstamp': '',
            'cecelia': '',
            'QDInfo': '',
            'User-Agent': '',
            'borgus': '',
            'ibex': '',
            'QDSign': '',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': 'druidv6.if.qidian.com',
            'Connection': 'Keep-Alive',
        }
        data = {
            'chapterReadTimeInfo': chapterreadtimeinfo,
        }
        ts = str(int(time.time() * 1000))
        data_encrypt = {
            'chapterReadTimeInfo': chapterreadtimeinfo,
        }
        QDSign = getQDSign(ts, data_encrypt, self.version, self.qid, userid=self.userid)
        QDInfo = getQDInfo_byQDInfo(ts, self.QDInfo)
        ibex = getibex_byibex(ts, self.ibex)
        borgus = getborgus(ts, data_encrypt, self.versioncode, self.qid)
        headers.update({
            'tstamp': ts,
            'QDInfo': QDInfo,
            'QDSign': QDSign,
            'borgus': borgus,
            'ibex': ibex,
        })
        self.config.cookies['QDInfo'] = QDInfo
        try:
            response = requests.post(url, data=data, cookies=self.config.cookies,
                                     headers=headers, timeout=REQUEST_TIMEOUT)
            res_text = response.text
            logger.debug(f"上报阅读时长: {res_text}")
            result = response.json()
            if result.get('Result') == 0 or result.get('Result') == "0":
                return True
            return False
        except requests.exceptions.Timeout as e:
            self._mark_timeout(url, e)
            return False
        except Exception as e:
            logger.error(f"上报阅读时长异常: {e}")
            return False

    def advjob(self) -> dict:
        """执行激励碎片任务"""
        try:
            # 获取任务列表
            result = self.get_adv_job()
            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
            # task_list = result['Data']['VideoBenefitModule']['TaskList']
            task_list = result['Data']['DailyBenefitModule']['TaskList']
            
            # 如果所有任务已完成
            if task_list[-1]['IsFinished'] == 1:
                logger.info("激励碎片任务已经完成")
                return {'status': 'success', 'msg': '任务已完成'}
                
            # 执行未完成的任务
            for i, task in enumerate(task_list):
                if task['IsFinished'] == 0:
                    logger.info(f"正在执行第{i+1}个任务")
                    result = self.do_adv_job(task['TaskId'])

                    if result.get('status') == 'success':
                        time.sleep(random.randint(1, 2))
                    elif result.get('status') == 'Unauthorized':
                        logger.error("登录已失效，请重新登录或者抓取cookies")
                        return {'status': 'Unauthorized', 'msg': '登录已失效，请重新抓取cookies'}
                    elif result.get('status') == 'captcha':
                        logger.warning("无法处理的验证码类型")
                        return {'status': result.get('status', 'captcha'), 'result': result, 'msg': '无法处理的验证码类型'}
                    elif result.get('status') == 'captcha_failed':
                        logger.error(f"验证码处理失败: {result.get('msg')}")
                        return {'status': result.get('status', 'captcha'), 'result': result, 'msg': result.get('msg')}  # 返回详细失败原因
                    else:
                        logger.error("执行激励任务失败")
                        return {'status': 'failed', 'msg': "执行激励任务失败"}
            
            # 验证任务是否全部完成
            check_result = self.get_adv_job()
            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
            check_task_list = check_result['Data']['DailyBenefitModule']['TaskList']
            all_finished = all(task["IsFinished"] for task in check_task_list)
            
            if all_finished:
                logger.info("激励碎片任务完成")
                return {'status': 'success', 'msg': '任务已完成'}
                
            logger.error("激励碎片任务未完成")
            return {'status': 'failed', 'code': 10086, 'msg': '任务未完成'}
            
        except Exception as e:
            logger.error(f"激励任务异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '任务异常，请检查日志'}

    def exadvjob(self) -> dict:
        """执行额外章节卡任务"""
        try:
            # 获取任务列表
            result = self.get_adv_job()
            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
            # task_list = result['Data']['CountdownBenefitModule']['TaskList']
            task_list = result['Data']['VideoRewardTab']['TaskList']
            
            for task in task_list:
                if task['Title'] == "完成3个广告任务得奖励":
                    if task['IsReceived'] == 1:
                        logger.info("额外章节卡任务已完成")
                        return {'status': 'success', 'msg': '任务已完成'}
                        
                    for i in range(3):
                        task_result = self.do_adv_job(task['TaskId'])
                        
                        if task_result.get('status') == 'success':
                            time.sleep(random.randint(1, 2))
                        elif result.get('status') == 'Unauthorized':
                            logger.error("登录已失效，请重新登录或者抓取cookies")
                            return {'status': 'Unauthorized', 'msg': '登录已失效，请重新抓取cookies'}
                        elif result.get('status') == 'captcha':
                            logger.warning("无法处理的验证码类型")
                            return {'status': result.get('status', 'captcha'), 'result': result, 'msg': '无法处理的验证码类型'}
                        elif result.get('status') == 'captcha_failed':
                            logger.error(f"验证码处理失败: {result.get('msg')}")
                            return {'status': result.get('status', 'captcha'), 'result': result, 'msg': result.get('msg')}  # 返回详细失败原因
                        else:
                            logger.error("执行额外章节卡任务失败")
                            continue
                
            # 检查任务状态
            check_result = self.get_adv_job()
            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
            check_task_list = check_result['Data']['VideoRewardTab']['TaskList']
            
            for task in check_task_list:
                if task['Title'] == "完成3个广告任务得奖励":
                    if task['IsReceived'] == 1:
                        logger.info("额外章节卡任务完成")
                        return {'status': 'success', 'msg': '任务已完成'}
                        
                    logger.error("额外章节卡任务未完成")
                    return {'status': 'failed', 'code': 10086, 'msg': '任务未完成'}
                    
            logger.error("未找到额外章节卡任务")
            return {'status': 'error', 'msg': '未找到该任务'}
            
        except Exception as e:
            logger.error(f"额外章节卡任务异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '任务异常，请检查日志'}
        
    def do_game(self) -> dict:
        """执行游戏中心任务"""
        def generate_trackid():
            """
            生成符合JavaScript代码逻辑的trackId
            格式：8-4-4-4-12的十六进制字符串，如: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
            """
            template = "xxxxxxxx-xxxxxxxx-xxxxxxxx-xxxxxxxx"
            hex_chars = "0123456789abcdef"  # 小写十六进制字符集
            return ''.join(
                random.choice(hex_chars) if c == 'x' else c 
                for c in template
            )
        
        headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://qdgame.qidian.com',
            'X-Requested-With': 'com.qidian.QDReader',
            'Sec-Fetch-Site': 'same-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://qdgame.qidian.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        try: 
            # 获取任务列表
            result = self.get_adv_job()
            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
            task_list = result['Data']['MoreRewardTab']['TaskList']
            game_url = ''
            type_gamejob = 0
            for task in task_list:
                if task['Title'] == "当日玩游戏10分钟":
                    type_gamejob = 1
                    is_finished = task['IsFinished']
                    is_received = task['IsReceived']
                    game_url = task['ActionUrl']
                    taskid = task['TaskId']
                    remaining_time = int(task['Total'])-int(task['Process'])
                    if is_received == 1:
                        logger.info("游戏中心任务已完成")
                        return {'status': 'success', 'msg': '任务已完成'}
                    elif (is_finished == 1 and is_received == 0) or (remaining_time <= 0):
                        logger.info("游戏中心任务已完成，奖励未领取")
                        logger.info("开始领取游戏中心任务奖励")
                        result = self.do_adv_job(taskid)
                        if result.get('status') == 'success':
                            logger.info("游戏任务领取成功")
                            return {'status': 'success', 'msg': '任务已完成'}
                        elif result.get('status') == 'captcha':
                            logger.warning("无法处理的验证码类型")
                            return {'status': result.get('status', 'captcha'), 'result': result, 'msg': '无法处理的验证码类型'}
                        elif result.get('status') == 'captcha_failed':
                            logger.error(f"验证码处理失败: {result.get('msg')}")
                            return {'status': result.get('status', 'captcha'), 'result': result, 'msg': result.get('msg')}  # 返回详细失败原因
                        else:
                            logger.error("游戏中心任务领取失败")
                            return {'status': 'error', 'error': '未知异常', 'msg': '任务异常，请检查日志'}
                    else:
                        logger.info("游戏中心任务未完成，开始执行游戏中心任务")
                if re.match(r"首次玩.*10分钟", task['Title']):
                    type_gamejob = 2
                    is_finished = task['IsFinished']
                    is_received = task['IsReceived']
                    game_url = task['ActionUrl']
                    taskid = task['TaskId']
                    remaining_time = int(task['Total'])-int(task['Process'])
                    if is_received == 1:
                        logger.info("游戏中心任务已完成")
                        return {'status': 'success', 'msg': '任务已完成'}
                    elif (is_finished == 1 and is_received == 0) or (remaining_time <= 0):
                        logger.info("游戏中心任务已完成，奖励未领取")
                        logger.info("开始领取游戏中心任务奖励")
                        result = self.do_adv_job(taskid)
                        if result.get('status') == 'success':
                            logger.info("游戏任务领取成功")
                            return {'status': 'success', 'msg': '任务已完成'}
                        elif result.get('status') == 'captcha':
                            logger.warning("无法处理的验证码类型")
                            return {'status': result.get('status', 'captcha'), 'result': result, 'msg': '无法处理的验证码类型'}
                        elif result.get('status') == 'captcha_failed':
                            logger.error(f"验证码处理失败: {result.get('msg')}")
                            return {'status': result.get('status', 'captcha'), 'result': result, 'msg': result.get('msg')}  # 返回详细失败原因
                        else:
                            logger.error("游戏中心任务领取失败")
                            return {'status': 'error', 'error': '未知异常', 'msg': '任务异常，请检查日志'}
                    else:
                        logger.info("游戏中心任务未完成，开始执行游戏中心任务")
            if not game_url or not taskid: 
                logger.error("游戏中心任务未找到")
                return {'status': 'failed', 'code': 10086, 'msg': '任务未找到'}
            if type_gamejob == 1:
                if 'qdgame://' in game_url:
                    logger.info("游戏中心任务URL为跳转链接类型，转为https链接")
                    # 将qdgame://替换为https://
                    game_url = game_url.replace('qdgame://', 'https://')
                    res_get_game_url = self.session.get(game_url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
                    game_url = res_get_game_url.headers.get('Location')
                    logger.info(f"游戏中心任务URL转换结果: {game_url}")
                    if not game_url:
                        logger.error("游戏中心任务URL转换失败")
                        return {'status': 'failed', 'code': 10086, 'msg': '任务未找到'}
                    
                match = re.search(r'partnerid=(\d+)', game_url)
                if not match:
                    logger.error("游戏中心任务URL错误")
                    return {'status': 'failed', 'code': 10086, 'msg': '游戏中心任务URL错误'}
                game_id = 201796
                partnerid = match.group(1)
            elif type_gamejob == 2:
                # 如果qdgame://在game_url中，则使用正则匹配
                if 'qdgame://' in game_url:
                    logger.info("游戏中心任务URL为跳转链接类型，转为https链接")
                    game_url = game_url.replace('qdgame://', 'https://')
                    res_get_game_url = self.session.get(game_url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
                    game_url = res_get_game_url.headers.get('Location')
                    logger.info(f"游戏中心任务URL转换结果: {game_url}")
                    if not game_url:
                        logger.error("游戏中心任务URL转换失败")
                        return {'status': 'failed', 'code': 10086, 'msg': '游戏中心任务URL转换失败'}

                match = re.search(r'/game/(\d+).*?partnerid=(\d+)', game_url)
                if not match:
                    logger.error("游戏中心任务URL错误")
                    return {'status': 'failed', 'code': 10086, 'msg': '游戏中心任务URL错误'}
                game_id = match.group(1)
                partnerid = match.group(2)
                
            else:
                logger.error(f"游戏中心任务类型异常: {type_gamejob}")
                return {'status': 'error', 'error': '游戏中心任务类型异常', 'msg': '游戏中心任务类型异常'}
            game_url = f"https://qdgame.qidian.com/game/{game_id}?partnerid={partnerid}"
            logger.info(f"游戏中心任务URL: {game_url}")
            url_track = 'https://lygame.qidian.com/home/statistic/track'
            params_get_PHPSESSID = {
                'action': 'gameball_impression',
                'positionType': '0',
                'gameId': '0',
                'url': game_url,
                'origin': 'https://qdgame.qidian.com',
                # '_t': '0.05669065654385208',
                'platformId': '1',
            }
            response_PHPSESSID = self.session.get(url_track, params=params_get_PHPSESSID, headers=headers,
                                                 cookies=self.config.cookies, timeout=REQUEST_TIMEOUT)
            logger.debug(f"response_PHPSESSID: {response_PHPSESSID.text}")
            if not response_PHPSESSID.status_code == 200: 
                logger.error("获取进程ID失败")
                return {'status': 'failed', 'code': 10086, 'msg': '获取进程ID失败'}
            res = response_PHPSESSID.json()
            if res.get('code') != 0 or not res.get('msg'):
                logger.error("获取进程ID失败")
                return {'status': 'failed', 'code': 10086, 'msg': '获取进程ID失败'}
            PHESSID = response_PHPSESSID.cookies.get('PHESSID')
            logger.debug(f"PHESSID: {PHESSID}")
            cookies = self.config.cookies.copy()
            trackid = generate_trackid()
            cookies['PHESSID'] = PHESSID
            cookies['trackid'] = trackid
            def heartbeat(game_id, full_time: int=690):
                run_time = 0
                url_heartbeat = "https://lygame.qidian.com/home/log/heartbeat"
                params_heartbeat = {
                    'gameId': str(game_id),
                    'platformId': '1',
                }
                while run_time < full_time:
                    response_heartbeat = self.session.get(url_heartbeat, params=params_heartbeat,
                                                          cookies=cookies, headers=headers,
                                                          timeout=REQUEST_TIMEOUT)
                    res = response_heartbeat.json()
                    if not res.get('code') == 0 or not res.get('data'):
                        logger.error("心跳失败")
                        return {'status': 'failed', 'code': 10086, 'msg': '心跳失败'}
                    next_time = int(res.get('data'))
                    logger.info(f"心跳成功，下一次心跳间隔: {next_time}")
                    run_time += next_time
                    time.sleep(next_time)
            heartbeat(game_id,(remaining_time+1)*60) # 多加一分钟，避免游戏时间不足
            logger.info("游戏中心任务结束，开始获取奖励")
            task_result = self.do_adv_job(taskid)
            if task_result.get('status') == 'success':
                logger.info("检查完成情况")
                result = self.get_adv_job()
                task_list = result['Data']['MoreRewardTab']['TaskList']
                for task in task_list:
                    if task['Title'] == "当日玩游戏10分钟":
                        is_received = task['IsReceived']
                        if is_received == 1:
                            logger.info("游戏中心任务已完成")
                            return {'status': 'success', 'msg': '任务已完成'}
                        else:
                            logger.error("游戏中心任务未完成")
                            return {'status': 'failed', 'code': 10086, 'msg': '任务未完成'}
                    if re.match(r"首次玩.*10分钟", task['Title']):
                        is_received = task['IsReceived']
                        if is_received == 1:
                            logger.info("游戏中心任务已完成")
                            return {'status': 'success', 'msg': '任务已完成'}
                        else:
                            logger.error("游戏中心任务未完成")
                            return {'status': 'failed', 'code': 10086, 'msg': '任务未完成'}
            elif task_result.get('status') == 'captcha':
                logger.warning("无法处理的验证码类型")
                return {'status':task_result.get('status'),'result': task_result, 'msg': '无法处理的验证码类型'}
            else:
                logger.error("执行游戏中心任务失败")
                return {'status': 'failed', 'code': 10086, 'msg': '执行游戏中心任务失败'}
        except requests.exceptions.Timeout as e:
            self._mark_timeout("游戏中心任务", e)
            return {'status': 'timeout', 'msg': f'游戏中心任务接口超时: {e}'}
        except QidianTimeoutError as e:
            return {'status': 'timeout', 'msg': str(e)}
        except Exception as e:
            logger.error(f"执行游戏中心任务异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '任务异常，请检查日志'}

    def lottery(self) -> dict:
        """执行每日抽奖任务"""
        try:
            url = "https://h5.if.qidian.com/argus/api/v2/checkin/detail"
            result = self._make_sdk_request(url, method='GET')
            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
            
            video_chance = result['Data']['LotteryInfo']['HasVideoUrge']
            lottery_chance = result['Data']['LotteryInfo']['LotteryCount']
            
            if lottery_chance == 0 and video_chance == 0:
                logger.info("抽奖机会已用完")
                return {'status': 'success', 'msg': '任务已完成'}
                
            logger.info(f"观看视频机会: {video_chance}次, 抽奖机会: {lottery_chance}次")
            
            for i in range(video_chance):
                url_video = "https://h5.if.qidian.com/argus/api/v2/video/callback"
                data_video = {
                    'sessionKey': '',
                    'banId': '0',
                    'captchaTicket': '',
                    'captchaRandStr': '',
                    'challenge': '',
                    'validate': '',
                    'seccode': '',
                    'appId': '1002',
                    'adId': '6050165817126400',
                    'videoSucc': '1',
                }
                
                video_result = self._make_sdk_request(url_video, data=data_video, method='POST')

                # 检测登录状态
                if video_result.get("status", 200)==401 and video_result.get("error", "") == "Unauthorized":
                    logger.error("登录已失效，请重新登录或者抓取cookies")
                    return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}

                # 明确处理可能的验证码情况（虽然理论上不应该发生）
                if video_result.get('is_captcha'):
                    # 记录警告但不中断任务
                    logger.warning("抽奖任务中意外遇到验证码，可能是API变更")
                    # 可以选择尝试解决或直接失败
                    return {'status': 'failed', 'msg': '意外的验证码'}
                
                if video_result.get('Result') in (0, "0"):
                    logger.info(f"观看第{i+1}次视频成功")
                    time.sleep(random.randint(1, 2))
                else:
                    logger.error("观看抽奖视频失败")
                    return {'status': 'failed', 'msg': '观看抽奖视频失败'}
            
            url_lottery = "https://h5.if.qidian.com/argus/api/v2/checkin/lottery"
            data_lottery = {
                'sessionKey': '',
                'banId': '0',
                'captchaTicket': '',
                'captchaRandStr': '',
                'challenge': '',
                'validate': '',
                'seccode': '',
            }
            
            total_chance = lottery_chance + video_chance
            for i in range(total_chance):
                lottery_result = self._make_sdk_request(url_lottery, data=data_lottery, method='POST')

                # 检测登录状态
                if lottery_result.get("status", 200)==401 and lottery_result.get("error", "") == "Unauthorized":
                    logger.error("登录已失效，请重新登录或者抓取cookies")
                    return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
                
                if lottery_result.get('is_captcha'):
                    return {'status': 'captcha', 'captcha_data': lottery_result['captcha_data'], 'msg': '意外的验证码'}
                
                if lottery_result.get('Result') == 0:
                    logger.info(f"第{i+1}次抽奖成功")
                    time.sleep(random.randint(1, 2))
                else:
                    logger.error("抽奖失败")
                    return {'status': 'failed', 'msg': '抽奖失败'}
            
            check_result = self._make_sdk_request(url, method='GET')
            check_video = check_result['Data']['LotteryInfo']['HasVideoUrge']
            check_lottery = check_result['Data']['LotteryInfo']['LotteryCount']
            
            if check_video == 0 and check_lottery == 0:
                logger.info("抽奖任务完成")
                return {'status': 'success', 'msg': '任务已完成'}
                
            logger.error("抽奖任务未完成")
            return {'status': 'failed', 'code': 10086, 'msg': '任务未完成'}
            
        except Exception as e:
            logger.error(f"抽奖任务异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '任务异常，请检查日志'}
        
    def weekly_exchange_card(self) -> dict:
        '''每周自动兑换章节卡'''
        try:
            url_exchange_page = "https://h5.if.qidian.com/argus/api/v3/checkin/checkinexchangepage"
            result = self._make_sdk_request(url_exchange_page, method='GET')
            # 检测登录状态
            if result.get("status", 200)==401 and result.get("error", "") == "Unauthorized":
                logger.error("登录已失效，请重新登录或者抓取cookies")
                return {"status": "Unauthorized", "msg": "登录已失效，请重新抓取cookies"}
            if result.get('Result') != 0 and result.get('Result') != "0":
                logger.error("获取章节卡兑换页面失败")
                return {'status': 'failed', 'code': 10086, 'msg': '获取章节卡兑换页面失败'}
            if result.get('Data') == None:
                logger.error("获取章节卡兑换页面数据为空")
                return {'status': 'failed', 'code': 10086, 'msg': '获取章节卡兑换页面数据为空'}
            remain_points = result["Data"].get("Balance")
            logger.info(f"当前余额: {remain_points}")
            goods_list = result["Data"].get("Goods", [])
            
            # 验证数据有效性
            if remain_points is None or remain_points <= 0:
                logger.error(f"无效的余额: {remain_points}")
                return {'status': 'stop', 'msg': '余额不足或无效'}
            
            if not goods_list:
                logger.error("章节卡列表为空")
                return {'status': 'stop', 'msg': '章节卡列表为空'}
            
            # 选择可兑换的章节卡（价格不超过余额的最贵章节卡）
            selected_good = None
            for good in goods_list:
                # 确保章节卡有有效的价格
                if "GoodsScore" not in good:
                    continue
                    
                price = good["GoodsScore"]
                # 选择价格不超过余额且最贵的章节卡
                if price <= remain_points and (selected_good is None or price > selected_good["GoodsScore"]):
                    selected_good = good
            
            # 检查是否找到可兑换章节卡
            if selected_good is None:
                logger.info(f"没有可兑换的章节卡（当前余额: {remain_points}）")
                return {'status': 'stop', 'msg': f'余额不足({remain_points})'}
            
            goods_id = selected_good["GoodsId"]
            goods_score = selected_good["GoodsScore"]
            chapter_card_count = selected_good["ChapterCardCount"]
            
            logger.info(f"选择章节卡: GoodsId：{goods_id}, 价格：{goods_score}, 章节卡点数：{chapter_card_count}")
            
            url_exchange = "https://h5.if.qidian.com/argus/api/v3/checkin/exchangegoods"
            data = {
                'goodId': goods_id,
            }
            exchange_result = self._make_sdk_request(url_exchange, data=data, method='POST')
            if exchange_result.get('Result') == -220000:
                logger.error("章节卡未到兑换时间")
                return {'status': 'stop', 'msg': '未到兑换时间'}
            elif exchange_result.get('Result') != 0 and exchange_result.get('Result') != "0":
                logger.error("章节卡兑换失败")
                return {'status': 'failed', 'code': 10086, 'msg': '兑换接口返回失败'}
            else:
                logger.info(f"章节卡兑换成功，获得章节卡点数：{chapter_card_count}")
                return {'status': 'success', 'msg': f'消耗{goods_score}点兑换{chapter_card_count}点章节卡'}


        except Exception as e:
            logger.error(f"每周自动兑换章节卡任务异常: {e}")
            return {'status': 'error', 'error': str(e)}
        
    def readtime_report(self) -> dict:
        """
        阅读时长上报任务
        根据用户配置的书籍ID、每章时长范围及总时长，自动生成连续章节的阅读记录并上报
        返回格式与其他任务一致：{'status': 'success'} 或 {'status': 'failed'}
        """
        try:
            # 1. 获取配置
            config = self.config.readtime_task_config
            if not config:
                logger.warning("未配置阅读时长上报任务参数")
                return {'status': 'failed', 'msg': '缺少阅读时长配置'}

            book_ids = config.get('book_ids', [])
            min_dur = config.get('min_duration', 5)
            max_dur = config.get('max_duration', 10)
            total_dur = config.get('total_duration', 60)

            if not book_ids:
                logger.warning("未配置需要上报阅读时长的书籍ID")
                return {'status': 'failed', 'msg': '书籍ID列表为空'}

            # 2. 随机选择一本书
            book_id = random.choice(book_ids)
            logger.info(f"随机选择书籍ID: {book_id}")

            # 3. 获取章节列表
            chapters = self.get_chapters(book_id)  # 返回列表，每个元素包含 chapterid, chapterName 等
            if not chapters:
                logger.error(f"获取书籍[{book_id}]章节列表失败")
                return {'status': 'failed', 'msg': '章节列表为空'}

            total_chapters = len(chapters)
            logger.info(f"书籍[{book_id}]共有 {total_chapters} 章")

            # 4. 随机生成阅读时长（分钟），累加直到达到或超过总时长
            durations = []
            accumulated = 0
            while accumulated < total_dur:
                dur = random.randint(min_dur, max_dur)
                durations.append(dur)
                accumulated += dur

            N = len(durations)
            logger.info(f"需要上报 {N} 章，总时长 {accumulated} 分钟（目标 {total_dur} 分钟）")

            # 5. 检查章节数量是否足够
            if total_chapters < N:
                logger.error(f"书籍[{book_id}]章节数不足（需要 {N} 章，实际 {total_chapters} 章）")
                return {'status': 'failed', 'msg': '章节数不足'}

            # 6. 随机选取连续 N 章
            start_idx = random.randint(0, total_chapters - N)
            selected_chapters = chapters[start_idx:start_idx + N]
            logger.info(f"选取章节范围: {start_idx+1} ~ {start_idx+N}")

            # 7. 生成时间戳（毫秒），最后一章结束时间为当前时间减去随机偏移（1~5秒）
            now_ms = int(time.time() * 1000)
            final_end = now_ms - random.randint(1000, 5000)

            # 从后向前生成记录
            chapter_Info = []
            current_end = final_end
            full_read_time = 0
            # 逆序遍历章节（从最后一章到第一章）
            for idx, ch in enumerate(reversed(selected_chapters)):
                read_ms = durations[N - 1 - idx] * 60 * 1000  # 对应时长的毫秒数
                start_ts = current_end - read_ms
                # 构建单条阅读数据
                read_data = {
                    "readTime": read_ms,
                    "bookId": int(book_id),
                    "chapterId": int(ch['chapterid']),
                    "startTime": start_ts,
                    "endTime": current_end,
                    "bookType": 1,
                    "chapterVip": 1,
                    "scrollMode": 1,
                    "unlockStatus": -100,
                    "unlockReason": -100,
                    "sp": "",
                }
                chapter_Info.append(read_data)
                # 为前一个章节生成间隔（1~3秒）
                gap_ms = random.randint(1000, 3000)
                current_end = start_ts - gap_ms
                # 记录上报总阅读时长
                full_read_time += read_ms/1000/60

            # 由于是从后向前生成，实际记录顺序是反的（最后一章在前），但接口不要求顺序，所以无需反转
            logger.info(f"生成 {len(chapter_Info)} 条阅读记录，共计{full_read_time:.2f}分钟，准备上报")

            # 8. 调用 utils 中的上报函数
            success = self.do_readtime_report(chapter_Info=chapter_Info)

            if success:
                logger.info("阅读时长上报成功")
                return {'status': 'success', 'msg': f'上报了{full_read_time:.2f}分钟阅读时长'}
            else:
                logger.error("阅读时长上报失败")
                return {'status': 'failed', 'msg': '阅读时长上报失败'}

        except Exception as e:
            logger.error(f"阅读时长上报任务异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '任务异常，请查看日志'}
        
    def get_readcard_status(self):
        '''获取当前章节卡信息'''
        try:
            url = "https://h5.if.qidian.com/argus/api/v1/readtime/scoremall/chaptercardwithbook"
            result = self._make_sdk_request(url, method='GET')
            
            if result.get('Result') != 0 and result.get('Result') != "0":
                logger.error("获取章节卡信息失败")
                return {'status': 'failed', 'msg': '获取章节卡信息失败'}
            
            cards = result.get('Data', {}).get('ChapterCards', [])
            
            if not cards:
                logger.info("当前账号没有章节卡")
                return {
                    'status': 'success',
                    'total_value': 0,
                    'total_count': 0,
                    'earliest_expire': None,
                    'cards': [],
                    'msg': '当前账号没有章节卡'
                }
            
            # 计算总价值和总数量
            total_value = 0
            total_count = 0
            
            for card in cards:
                value = int(card.get('Value', 0))
                amount = int(card.get('Amount', 1))
                total_value += value * amount
                total_count += amount
            
            # 找到最快过期的章节卡
            earliest_card = min(cards, key=lambda x: int(x.get('ExpireAt', 0)))
            expire_timestamp = int(earliest_card.get('ExpireAt', 0))
            
            from datetime import datetime
            expire_date = datetime.fromtimestamp(expire_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            
            earliest_expire = {
                'value': int(earliest_card.get('Value', 0)),
                'amount': int(earliest_card.get('Amount', 1)),
                'expire_at': expire_timestamp,
                'expire_date': expire_date
            }
            
            logger.info(f"章节卡余额: {total_value} (共{total_count}张)")
            logger.info(f"最快过期: {earliest_expire['value']}点 x {earliest_expire['amount']}张, 过期时间: {expire_date}")
            
            return {
                'status': 'success',
                'total_value': total_value,
                'total_count': total_count,
                'earliest_expire': earliest_expire,
                'cards': cards,
                'msg': f"\n章节卡余额: {total_value} (共{total_count}张)\n最快过期: {earliest_expire['value']}点 x {earliest_expire['amount']}张, 过期时间: {expire_date}"
            }
            
        except Exception as e:
            logger.error(f"查询章节卡异常: {e}")
            return {'status': 'error', 'error': str(e), 'msg': '查询章节卡异常，请查看日志'}
    
    # 其他核心功能方法...

class TaskProcessor:
    """任务处理器"""
    def __init__(self, client: QidianClient, user: UserConfig, retry_attempts: int = 3):
        self.client = client
        self.user = user
        self.task_results = {}
        self.retry_attempts = retry_attempts  # 从全局配置中获取
    
    def run_task(self, task_name: str, task_func: Callable) -> None:
        """运行单个任务"""
        if not self.user.tasks.get(task_name, False):
            logger.info(f"任务[{task_name}]已禁用，跳过执行")
            return True
            
        logger.info(f"开始执行任务: {task_name}")
        self.client.reset_timeout_state()
        for attempt in range(1, self.retry_attempts + 1):
            logger.info(f"开始第{attempt}次尝试")
            try:
                result = task_func()

                # 只要本次任务中任意接口超时，立即放弃本次执行（不再重试后续任务）
                if getattr(self.client, 'last_request_timeout', False):
                    result = self._timeout_result()

                if isinstance(result, dict):
                    status = result.get('status')
                    msg = result.get('msg', '未知原因') # 统一提取 msg
                    
                    if status == 'success':
                        logger.info(f"任务[{task_name}]执行完成: {msg}")
                        self.task_results[task_name] = result
                        break
                    elif status == 'timeout':
                        logger.error(f"任务[{task_name}]因接口超时终止，放弃本次执行: {msg}")
                        self.task_results[task_name] = result
                        return False
                    elif status == "Unauthorized":
                        logger.error(f"任务[{task_name}]因未登录强行停止所有任务: {msg}")
                        self.task_results[task_name] = result
                        return False
                    elif status == 'captcha_failed':
                        captcha_data = result.get('captcha_data', {})
                        logger.error(f"任务[{task_name}]因验证码失败: {msg}")
                        logger.debug(f"验证码数据: {json.dumps(captcha_data, ensure_ascii=False)}")
                        self.task_results[task_name] = {
                            'status': 'captcha_failed',
                            'msg': msg,  # 统一存入 msg
                            'captcha_data': captcha_data
                        }
                        break
                    elif status == 'captcha':
                        logger.warning(f"任务[{task_name}]因验证码中断: {msg}")
                        self.task_results[task_name] = result
                        break
                    elif status == 'stop':
                        logger.error(f"任务[{task_name}]主动停止: {msg}")
                        self.task_results[task_name] = result
                        break
                    else:
                        if attempt < self.retry_attempts:
                            logger.warning(f"任务[{task_name}]第{attempt}次执行失败({msg})，正在重试...")
                            time.sleep(random.uniform(1, 2))
                        else:
                            logger.error(f"任务[{task_name}]执行失败，已达到最大重试次数")
                            self.task_results[task_name] = result
                else:
                    logger.error(f"任务[{task_name}]返回格式错误")
                    self.task_results[task_name] = {'status': 'failed', 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'msg': f'任务[{task_name}]返回格式错误'}
                    break

            except Exception as e:
                if getattr(self.client, 'last_request_timeout', False):
                    logger.error(f"任务[{task_name}]因接口超时终止，放弃本次执行: {e}")
                    self.task_results[task_name] = self._timeout_result()
                    return False
                if attempt < self.retry_attempts:
                    logger.warning(f"任务[{task_name}]第{attempt}次执行异常: {e}，正在重试...")
                    time.sleep(random.uniform(1, 2))
                else:
                    logger.error(f"任务[{task_name}]执行异常: {e}")
                    self.task_results[task_name] = {
                        'status': 'error',
                        'error': str(e),
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
        return True

    def _timeout_result(self) -> dict:
        """构造统一的接口超时结果"""
        url = getattr(self.client, 'last_timeout_url', '')
        msg = '接口请求超时，已放弃本次执行'
        if url:
            msg += f'（{url}）'
        return {
            'status': 'timeout',
            'msg': msg,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def process_all_tasks(self) -> Dict[str, Any]:
        """处理所有任务"""
        tasks = [
            ('签到任务', self.client.qdsign),
            ('激励碎片任务', self.client.advjob),
            ('章节卡任务', self.client.exadvjob),
            ('广告加点任务', self.client.reading_advjob),
            ('天降福利任务', self.client.dialog_advjob),
            ('游戏中心任务', self.client.do_game),
            ('每日抽奖任务', self.client.lottery),
            # ('其他任务', self.other_task_func),
            # 添加其他任务...
        ]

        # 仅在配置了阅读时长上报的配置项后才会执行该任务
        if self.user.readtime_task_config:
            tasks.append(('阅读时长上报', self.client.readtime_report))

        # 获取当前星期，如果为周日，则添加每周自动兑换章节卡任务
        if time.strftime('%w') == '0':
            tasks.append(('每周自动兑换章节卡', self.client.weekly_exchange_card))
        else:
            logger.info("非周日，不执行每周自动兑换章节卡任务")

        # 将章节卡信息推送任务放到最后一个
        tasks.append(('章节卡信息推送', self.client.get_readcard_status))
        
        for task_name, task_func in tasks:
            flag = self.run_task(task_name, task_func)
            if not flag:
                break
        
        return self.task_results

class MainApp:
    """主程序"""
    def __init__(self):
        self.config_manager = None  # 延迟初始化

    def pre_check(self) -> bool:
        """运行前的文件存在性检查"""
        if not os.path.exists(CONFIG_FILE):
            logger.error(f"配置文件 {CONFIG_FILE} 不存在，请检查路径是否正确")
            return False

        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)

            for user_data in config.get('users', []):
                username = user_data.get('username', '未知')
                cookies_file = user_data.get('cookies_file', f"{COOKIES_DIR}/{username}.json")
                if not os.path.exists(cookies_file):
                    logger.error(f"用户 [{username}] 的 cookies 文件 {cookies_file} 不存在")
                    return False

        except Exception as e:
            logger.error(f"读取配置文件失败: {e}")
            return False

        return True

    def run(self) -> None:
        """运行程序"""
        global logger
        # 获取基础日志系统（已初始化）
        logger = LoggerManager().logger

        logger.info(f"QDjob程序启动，当前版本为: {__version__}")
        logger.info(f"接口超时设置: 连接 {REQUEST_CONNECT_TIMEOUT:g}s / 读取 {REQUEST_READ_TIMEOUT:g}s"
                    f"（仅作兜底，可用 QDJOB_CONNECT_TIMEOUT / QDJOB_READ_TIMEOUT 覆盖）")

        if not self.pre_check():
            logger.error("预检查失败，程序终止")
            return
        
        # 初始化 ConfigManager
        self.config_manager = ConfigManager()
        config = self.config_manager.config

        # 初始化日志系统
        log_level = config.get('log_level', 'INFO')
        log_retention_days = config.get('log_retention_days', DEFAULT_LOG_RETENTION)
        logger = LoggerManager().reconfigure_logger(log_level, log_retention_days)

        # 继续执行主流程
        for user in self.config_manager.users:
            logger.info(f"开始处理用户: {user.username}")

            try:
                # 初始化客户端
                client = QidianClient(user)
                if not client.init():
                    logger.error(f"用户: {user.username} 初始化失败")
                    continue

                logger.info(f"开始检查用户[{user.username}]登录状态")
                # 检查登录状态
                nickname = client.check_login()
                if client.last_request_timeout:
                    timeout_msg = f"登录检测接口超时: {client.last_timeout_url}"
                    logger.error(f"用户[{user.username}]{timeout_msg}，放弃该用户本次执行")
                    self._send_notification(user, {'登录检测': {'status': 'timeout', 'msg': timeout_msg}})
                    continue
                if not nickname:
                    logger.warning(f"用户[{user.username}]未登录")
                    continue
                
                logger.info(f"用户主页[{nickname}]登录成功")

                # 根据配置的刷新间隔自动刷新cookies（替代已废弃的ptlogin有效期检测）
                if self._need_refresh_cookies(user):
                    logger.info(f"用户[{user.username}]开始自动刷新cookies")
                    is_success, refresh_msg = client.update_cookies()
                    if is_success:
                        logger.info(f"用户[{user.username}]cookies自动刷新成功: {refresh_msg}")
                        self.config_manager.update_last_refresh_time(user.username)
                    else:
                        logger.warning(f"用户[{user.username}]cookies自动刷新失败: {refresh_msg}，继续后续流程")
                    # 单独推送一次cookies刷新结果
                    self._send_cookies_refresh_notification(user, is_success, refresh_msg, trigger="按间隔自动刷新")
                    if client.last_request_timeout:
                        logger.warning(f"用户[{user.username}]cookies刷新接口超时，跳过本次自动刷新")
                        client.reset_timeout_state()

                # 检测福利中心状态 有ptlogin，这个可以取消
                WelfareStatus = client.check_riskstatus()
                if client.last_request_timeout:
                    timeout_msg = f"福利中心检测接口超时: {client.last_timeout_url}"
                    logger.error(f"用户[{user.username}]{timeout_msg}，放弃该用户本次执行")
                    self._send_notification(user, {'福利中心检测': {'status': 'timeout', 'msg': timeout_msg}})
                    continue
                login_status = WelfareStatus.get('login_status', True)
                risk_status = WelfareStatus.get('risk_status', False)
                if not login_status:
                    logger.warning(f"用户[{user.username}]福利中心登录失效，尝试刷新cookies")
                    is_success, refresh_msg = client.update_cookies()
                    # 单独推送一次cookies刷新结果
                    self._send_cookies_refresh_notification(user, is_success, refresh_msg, trigger="福利中心登录失效")
                    if not is_success:
                        logger.error(f"用户[{user.username}]刷新cookies失败: {refresh_msg}，跳过该用户执行下一个用户")
                        continue
                    self.config_manager.update_last_refresh_time(user.username)
                    logger.info(f"用户[{user.username}]刷新cookies成功: {refresh_msg}，重新检测福利中心登录状态")

                    # 刷新成功后重新检测福利中心登录状态
                    WelfareStatus = client.check_riskstatus()
                    login_status = WelfareStatus.get('login_status', True)
                    risk_status = WelfareStatus.get('risk_status', False)
                    if not login_status:
                        logger.warning(f"用户[{user.username}]刷新cookies后福利中心仍登录失效，跳过该用户执行下一个用户")
                        continue
                    logger.info(f"用户[{user.username}]刷新cookies后福利中心登录状态恢复正常")

                if risk_status:
                    logger.warning(f"用户[{user.username}]福利中心触发风控，后续任务执行可能会出现问题")


                # # 检查账号ptlogin登录状态，这个更彻底
                # ptlogin_result = client.ptlogin_checkstatus()
                # ptlogin_status = ptlogin_result["status"]
                # ptlogin_expired_time = ptlogin_result["expired_time"]
                # topush = False

                # if ptlogin_result["NeedRefresh"] == True:
                #     if ptlogin_status == "expired":
                #         logger.warning(f"用户[{user.username}]ptlogin登录已过期，过期时间: {ptlogin_expired_time}，尝试自动更新cookies")
                #     else:
                #         logger.warning(f"用户[{user.username}]ptlogin登录状态异常，错误信息：{ptlogin_status}，尝试自动更新cookies")
                #     # 刷新cookies
                #     is_success, refresh_msg = client.update_cookies()
                #     if is_success:
                #         logger.info(f"用户[{user.username}]cookies更新成功")
                #         # 简单推送提示
                #         topush = True
                #         title_simple = f"QDjob 用户[{user.username}] cookies更新成功"
                #         msg_text_simple = f"用户[{user.username}]cookies更新成功，更新时间: {ptlogin_expired_time}"
                        
                #     else:
                #         logger.error(f"用户[{user.username}]cookies更新失败: {refresh_msg}，后续任务可能执行失败")
                #         # 简单推送提示
                #         topush = True
                #         title_simple = f"QDjob 用户[{user.username}] cookies更新失败"
                #         msg_text_simple = f"用户[{user.username}]cookies更新失败，错误信息：{refresh_msg}\n更新时间: {ptlogin_expired_time}"
                # else:
                #     if ptlogin_status == "failed":
                #         logger.warning(f"用户[{user.username}]获取ptlogin登录状态异常，错误信息：{ptlogin_status}")
                #     elif ptlogin_status == "Manual":
                #         logger.error(f"用户[{user.username}]ptlogin已过期太久，需要手动登录，更新时间：{ptlogin_expired_time}")
                #         topush = True
                #         title_simple = f"QDjob 用户[{user.username}] ptlogin已过期太久，需要手动登录"
                #         msg_text_simple = f"用户[{user.username}]ptlogin已过期太久，需要手动登录，更新时间：{ptlogin_expired_time}"
                #     elif ptlogin_status == "active":
                #         logger.info(f"用户[{user.username}]ptlogin登录状态正常，cookies自动更新时间：{ptlogin_expired_time}")
                #     else:
                #         logger.warning(f"用户[{user.username}]ptlogin登录状态未知，错误信息：{ptlogin_status}")

                # # 单独推送cookies更新消息
                # if topush == True:
                #     for push_service in user.push_services:
                #         service_name = push_service.__class__.__name__
                #         try:
                #             push_result = push_service.send(title_simple, msg_text_simple)
                #             if push_result.get('success'):
                #                 logger.info(f"[{service_name}] 推送成功")
                #             else:
                #                 logger.info(f"[{service_name}] 推送失败: {push_result.get('raw')}")
                #         except Exception as e:
                #             logger.error(f"[{service_name}] 推送异常: {str(e)}")


                retry_attempts = self.config_manager.config.get('retry_attempts', 3)
                
                # 处理任务
                processor = TaskProcessor(client, user, retry_attempts)
                results = processor.process_all_tasks()
                
                # 发送通知
                self._send_notification(user, results)
                
                # 保存cookies
                # self.config_manager.save_cookies(user.username, client.session.cookies.get_dict())
                
            except Exception as e:
                logger.error(f"处理用户[{user.username}]时发生错误: {e}")
                if 'client' in locals() and getattr(client, 'last_request_timeout', False):
                    timeout_msg = f"运行过程中接口超时: {getattr(client, 'last_timeout_url', '')}"
                    self._send_notification(user, {'运行异常': {'status': 'timeout', 'msg': timeout_msg}})
    
    def _need_refresh_cookies(self, user: UserConfig) -> bool:
        """根据配置的刷新间隔判断是否需要自动刷新cookies

        规则：
        - 刷新时间记录缺失或非法（为空/非时间字符串）：仅将其纠正为当前时间，本次不刷新（返回 False）
        - 距上次刷新未超过间隔：返回 False
        - 距上次刷新已超过间隔：返回 True

        :param user: 用户配置对象
        :return: True 表示需要刷新
        """
        interval_days = getattr(user, 'cookies_refresh_interval_days', DEFAULT_COOKIES_REFRESH_INTERVAL_DAYS)
        last_time = getattr(user, 'last_cookies_refresh_time', None)

        last_dt = None
        if last_time:
            try:
                last_dt = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                last_dt = None

        if last_dt is None:
            logger.info(f"用户[{user.username}]无有效的cookies刷新时间记录[{last_time}]，已将其纠正为当前时间，本次不自动刷新cookies")
            self.config_manager.update_last_refresh_time(user.username)
            return False

        elapsed = datetime.now() - last_dt
        if elapsed >= timedelta(days=interval_days):
            logger.info(f"用户[{user.username}]距上次刷新cookies已{elapsed.days}天，超过间隔{interval_days}天，需要自动刷新")
            return True

        logger.info(f"用户[{user.username}]距上次刷新cookies仅{elapsed.days}天（间隔{interval_days}天），暂不自动刷新")
        return False
    
    def _send_cookies_refresh_notification(self, user: UserConfig, success: bool, message: str, trigger: str = "") -> None:
        """cookies刷新后单独推送一次结果

        :param user: 用户配置对象
        :param success: 刷新是否成功
        :param message: 刷新结果描述
        :param trigger: 触发刷新的原因
        """
        if not user.push_services:
            logger.debug(f"用户[{user.username}]未配置推送服务，跳过cookies刷新推送")
            return

        result_text = "成功" if success else "失败"
        emoji = "✅" if success else "❌"
        refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        title = f"QDJob 用户[{user.username}] cookies刷新{result_text}"
        msg_text = (
            f"👤 用户[{user.username}] cookies刷新{result_text}\n"
            + "-" * 20 + "\n"
            f"{emoji} 刷新结果: {result_text}\n"
            f"📝 详情: {message}\n"
            f"🕒 刷新时间: {refresh_time}\n"
        )
        if trigger:
            msg_text += f"🔧 触发方式: {trigger}\n"

        for push_service in user.push_services:
            service_name = push_service.__class__.__name__
            try:
                push_result = push_service.send(title, msg_text)
                if push_result.get('success'):
                    logger.info(f"[{service_name}] cookies刷新推送成功")
                else:
                    logger.info(f"[{service_name}] cookies刷新推送失败: {push_result.get('raw')}")
            except Exception as e:
                logger.error(f"[{service_name}] cookies刷新推送异常: {str(e)}")

    def _send_notification(self, user: UserConfig, results: Dict[str, Any]) -> None:
        """发送通知"""
        if not user.push_services:
            logger.debug(f"用户[{user.username}]未配置推送服务")
            return
            
        # 构造消息内容
        msg_text = f"👤 用户[{user.username}]任务报告:\n" + "-"*20 + "\n"
        success_count = 0
        total_count = len(results)
        has_captcha = False
        captcha_reason = ""
        has_timeout = False
        timeout_reason = ""

        for task_name, result in results.items():
            emoji = '❓'
            detail_msg = ""
            
            if isinstance(result, dict):
                status = result.get('status')
                # 提取我们在任务函数里加的 msg 字段
                detail_msg = result.get('msg', '') 
                
                if status == 'success':
                    emoji = '✅'
                    success_count += 1
                elif status == 'captcha':
                    emoji = '⚠️'
                    has_captcha = True
                    detail_msg = detail_msg or '触发验证码中断'
                elif status == 'captcha_failed':
                    emoji = '❌'
                    has_captcha = True
                    captcha_reason = result.get('msg', '打码失败')
                    detail_msg = detail_msg or captcha_reason
                elif status == 'timeout':
                    emoji = '⏱️'
                    has_timeout = True
                    timeout_reason = detail_msg or '接口请求超时'
                    detail_msg = detail_msg or '接口请求超时，已放弃本次执行'
                elif status == 'stop':
                    emoji = '⏸️'
                    detail_msg = detail_msg or result.get('msg', '主动停止')
                else:
                    emoji = '❌'
                    detail_msg = detail_msg or result.get('error', '执行失败')
            else:
                emoji = '❌'
                detail_msg = "返回格式异常"

            # 拼接单行结果，例如：✅ 签到任务: 今日已签到过
            # 如果没有 detail_msg，就只显示任务名
            if detail_msg:
                msg_text += f"{emoji} {task_name}: {detail_msg}\n"
            else:
                msg_text += f"{emoji} {task_name}\n"

        if has_captcha:
            msg_text += "\n" + "-"*20 + "\n"
            msg_text += "⚠️ 警告：账号触发风控\n"
            if captcha_reason:
                msg_text += f"原因: {captcha_reason}\n"
            msg_text += "建议：手动登录APP或抓包更新参数"

        if has_timeout:
            msg_text += "\n" + "-"*20 + "\n"
            msg_text += "⏱️ 警告：接口请求超时，已放弃本次执行\n"
            if timeout_reason:
                msg_text += f"超时详情: {timeout_reason}\n"
            msg_text += (
                f"超时设置: 连接 {REQUEST_CONNECT_TIMEOUT:g}s / 读取 {REQUEST_READ_TIMEOUT:g}s\n"
                "可能原因：网络抖动、DNS 解析异常、代理/VPN、IP 被临时风控。\n"
                "建议：检查网络与 DNS 设置，切换网络后重试。"
            )

        title = f"QDJob 运行报告 ({success_count}/{total_count})"
        if has_timeout:
            title = f"QDJob 运行超时中止 ({success_count}/{total_count})"
        
        # 发送所有推送服务
        for push_service in user.push_services:
            service_name = push_service.__class__.__name__
            try:
                push_result = push_service.send(title, msg_text) # 变量名改成了 msg_text 避免与内层变量冲突
                if push_result.get('success'):
                    logger.info(f"[{service_name}] 推送成功")
                else:
                    logger.info(f"[{service_name}] 推送失败: {push_result.get('raw')}")
            except Exception as e:
                logger.error(f"[{service_name}] 推送异常: {str(e)}")


if __name__ == "__main__":
    app = MainApp()
    app.run()
