# push.py
import base64
import hashlib
import hmac
from datetime import datetime
import requests
import json
import logging
import re
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# 推送内容中常见的违规/审计敏感信息
_URL_RE = re.compile(r"https?://[^\s，。；、）】]+", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_DIGITS_RE = re.compile(r"\d{6,}")


def sanitize_push_text(text: str) -> str:
    """脱敏推送内容中的 URL、IP、邮箱和连续数字，供违规重试使用"""
    text = "" if text is None else str(text)
    text = _URL_RE.sub("[链接]", text)
    text = _IPV4_RE.sub("[IP]", text)
    text = _EMAIL_RE.sub("[邮箱]", text)
    text = _DIGITS_RE.sub("[数字]", text)
    return text


class PushService(ABC):
    """推送服务基类"""
    def __init__(self):
        self.name = self.__class__.__name__.lower()
        self._validate_config()
    
    @abstractmethod
    def send(self, title: str, content: str) -> dict:
        """发送推送消息，返回包含成功状态的字典"""
        pass
    
    @abstractmethod
    def _validate_config(self):
        """验证配置有效性"""
        pass

class FeiShu(PushService):
    """飞书机器人推送"""
    # 飞书内容审计/敏感信息相关错误码：230022 敏感信息，230028 DLP 审查未通过
    _AUDIT_ERROR_CODES = (230022, 230028)
    _AUDIT_HINTS = ("敏感", "审计", "audit", "sensitive", "dlp", "内容安全")
    # 硬上限：最多发送 3 次；脱敏后内容无变化时提前停止
    MAX_ATTEMPTS = 3

    def __init__(self, webhook_url: str, havesign: bool, secret: str = ""):
        self.havesign = havesign
        self.secret = secret
        self.webhook_url = webhook_url
        super().__init__()

    def _validate_config(self):
        """验证飞书配置"""
        # 验证webhook_url格式
        if not self.webhook_url.startswith("https://open.feishu.cn/open-apis/bot/v2/hook/"):
            logger.warning(f"[飞书配置] webhook_url 格式不推荐，建议使用飞书官方webhook地址")
        
        # 验证签名配置
        if self.havesign and not isinstance(self.secret, str):
            logger.warning(f"[飞书配置] secret 必须为字符串类型，当前类型: {type(self.secret)}")
            raise ValueError("secret 必须为字符串类型")

        # 验证签名配置
        if self.havesign and not self.secret:
            raise ValueError("启用签名校验必须提供secret")
    
    def gen_sign(self, timestamp: int) -> str:
        """生成签名"""
        string_to_sign = f'{timestamp}\n{self.secret}'
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode('utf-8')
    
    def creatcard(self, title: str, content: str) -> dict:
        """创建卡片消息"""
        return {
            "config": {"update_multi": True},
            "elements": [{
                "tag": "markdown",
                "content": content,
                "text_align": "left",
                "text_size": "normal"
            }],
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            }
        }
    
    def send(self, title: str, content: str) -> dict:
        """发送卡片消息；触发内容审计时脱敏并有限重试"""
        title = "" if title is None else str(title)
        content = "" if content is None else str(content)
        result = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            result = self._send_once(title, content)
            if result.get("success"):
                return result

            if attempt < self.MAX_ATTEMPTS and self._is_audit_rejected(result):
                cleaned_title = sanitize_push_text(title)
                cleaned_content = sanitize_push_text(content)
                if (cleaned_title, cleaned_content) != (title, content):
                    logger.warning(f"[飞书推送] 内容触发审计，已脱敏并重试 ({attempt + 1}/{self.MAX_ATTEMPTS})")
                    title, content = cleaned_title, cleaned_content
                    continue
            return result

        return result

    def _send_once(self, title: str, content: str) -> dict:
        """执行一次卡片推送"""
        try:
            timestamp = int(datetime.now().timestamp())
            card = self.creatcard(title, content)

            payload = {
                "msg_type": "interactive",
                "card": card,
            }

            if self.havesign:
                payload["sign"] = self.gen_sign(timestamp)
                payload["timestamp"] = timestamp

            response = requests.post(url=self.webhook_url, json=payload, timeout=10)

            # 飞书内容审计错误可能以 HTTP 400 + JSON 错误体返回，需先保留 body 再判断
            result = None
            try:
                result = response.json()
            except ValueError:
                result = None

            if response.status_code >= 400 and not isinstance(result, dict):
                response.raise_for_status()

            success = (
                response.status_code < 400
                and isinstance(result, dict)
                and result.get("code") == 0
            )
            if not success:
                logger.debug(f"[飞书推送] 返回异常: {result}")

            return {
                "success": success,
                "raw": result,
                "service": "feishu"
            }

        except Exception as e:
            # webhook_url 本身含凭证，异常信息中需要脱敏
            error = self._redact(str(e))
            logger.error(f"[飞书推送] 发送异常: {error}")
            return {
                "success": False,
                "error": error,
                "service": "feishu"
            }

    def _is_audit_rejected(self, result: dict) -> bool:
        """判断是否由飞书内容审计/敏感信息规则拒绝"""
        raw = result.get("raw")
        if not isinstance(raw, dict):
            return False
        try:
            if int(raw.get("code")) in self._AUDIT_ERROR_CODES:
                return True
        except (TypeError, ValueError):
            pass
        text = str(raw.get("msg") or raw.get("message") or "")
        return any(hint in text.lower() for hint in self._AUDIT_HINTS)

    def _redact(self, text: str) -> str:
        """避免 webhook 凭证随异常信息写入日志"""
        if isinstance(self.webhook_url, str) and self.webhook_url:
            return text.replace(self.webhook_url, "***")
        return text

class ServerChan(PushService):
    """Server酱推送"""
    def __init__(self, sckey: str):
        self.sckey = sckey
        super().__init__()

    def _validate_config(self):
        """验证Server酱配置"""
        if not self.sckey.startswith("SCU"):
            logger.warning(f"[Server酱配置] sckey 格式不推荐，建议使用标准格式")

    def _redact(self, text: str) -> str:
        """避免 sckey 随异常信息写入日志"""
        if isinstance(self.sckey, str) and self.sckey:
            return text.replace(self.sckey, "***")
        return text

    def send(self, title: str, content: str) -> dict:
        """发送文本消息"""
        try:
            url = f"https://sc.ftqq.com/{self.sckey}.send"
            data = {
                "text": title,
                "desp": content
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            success = result.get("errno") == 0 or result.get("code") == 0
            if not success:
                logger.debug(f"[Server酱] 返回异常: {result}")
            
            return {
                "success": success,
                "raw": result,
                "service": "serverchan"
            }
            
        except Exception as e:
            error = self._redact(str(e))
            logger.error(f"[Server酱] 发送异常: {error}")
            return {
                "success": False,
                "error": error,
                "service": "serverchan"
            }
        
class QiweiPush(PushService):
    """Qiwei推送"""
    # 企业微信群机器人 text 消息 content 上限 2048 字节（UTF-8）
    MAX_CONTENT_BYTES = 2048

    def __init__(self, webhook_url: str, userids:list, phoneids:list):
        self.webhook_url = webhook_url
        self.userids = userids
        self.phoneids = phoneids
        super().__init__()

    def _validate_config(self):
        """验证Qiwei配置"""
        if not self.webhook_url:
            logger.warning(f"[Qiwei配置] webhook_url 不能为空")

    def _truncate_bytes(self, text: str, limit: int) -> str:
        """按 UTF-8 字节数截断，避免截断半个多字节字符"""
        text = "" if text is None else str(text)
        data = text.encode("utf-8")
        if len(data) <= limit:
            return text
        return data[: limit - 3].decode("utf-8", errors="ignore") + "..."

    def _redact(self, text: str) -> str:
        """避免 webhook 凭证随异常信息写入日志"""
        if isinstance(self.webhook_url, str) and self.webhook_url:
            return text.replace(self.webhook_url, "***")
        return text

    def send(self, title: str, content: str) -> dict:
        """发送文本消息"""
        title = "" if title is None else str(title)
        content = "" if content is None else str(content)
        try:
            url = self.webhook_url
            text = self._truncate_bytes(f'## {title} \n {content}', self.MAX_CONTENT_BYTES)
            data = {
                "msgtype": "text",
                "text": {
                    "content": text,
                },
            }
            if self.userids != []: 
                data["text"]["mentioned_list"] = self.userids
            if self.phoneids != []: 
                data["text"]["mentioned_mobile_list"] = self.phoneids

            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            success = result.get("errcode") == 0

            if not success:
                logger.debug(f"[Qiwei企业微信] 返回异常: {result}")

            return {"success": success, "raw": result, "service": "qiwei"}

        except Exception as e:
            error = self._redact(str(e))
            logger.error(f"[Qiwei企业微信] 发送异常: {error}")
            return {"success": False, "error": error, "service": "qiwei"}
        
class PushPlus(PushService):
    """PushPlus推送"""
    # 硬上限：最多发送 3 次；脱敏后内容无变化时提前停止
    MAX_ATTEMPTS = 3
    # 999 为服务端验证错误，仅在返回文案明确指向内容违规时才重试
    _CONTENT_HINTS = ("敏感", "违规", "审计", "非法", "不合法", "禁止")

    def __init__(self, token: str, topic: str):
        self.token = token
        self.topic = topic
        super().__init__()

    def _validate_config(self):
        """验证PushPlus配置"""
        if not self.token:
            logger.warning(f"[PushPlus配置] token 不能为空")

    def send(self, title: str, content: str) -> dict:
        """发送文本消息；服务端判定内容违规时脱敏并有限重试"""
        title = "" if title is None else str(title)
        content = "" if content is None else str(content)
        result = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            result = self._send_once(title, content)
            if result.get("success"):
                return result

            if attempt < self.MAX_ATTEMPTS and self._is_content_rejected(result):
                cleaned_title = sanitize_push_text(title)
                cleaned_content = sanitize_push_text(content)
                if (cleaned_title, cleaned_content) != (title, content):
                    logger.warning(f"[PushPlus] 内容疑似违规，已脱敏并重试 ({attempt + 1}/{self.MAX_ATTEMPTS})")
                    title, content = cleaned_title, cleaned_content
                    continue
            return result

        return result

    def _is_content_rejected(self, result: dict) -> bool:
        """判断 999 验证错误是否由内容违规导致"""
        raw = result.get("raw")
        if not isinstance(raw, dict):
            return False
        try:
            if int(raw.get("code")) != 999:
                return False
        except (TypeError, ValueError):
            return False
        text = str(raw.get("msg") or raw.get("message") or "")
        return any(hint in text for hint in self._CONTENT_HINTS)

    def _send_once(self, title: str, content: str) -> dict:
        """执行一次推送请求"""
        try: 
            url = "http://www.pushplus.plus/send"
            headers = {
                'Content-Type':'application/json'
            }
            data = {
                "token":self.token,
                "title":title,
                "content":content,
            }
            if self.topic:
                data["topic"] = self.topic
            data=json.dumps(data).encode(encoding='utf-8')
            response = requests.post(url, data=data, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            success = isinstance(result, dict) and result.get("code") == 200
            if not success:
                logger.debug(f"[PushPlus] 推送异常: {result}")
            return {"success": success, "raw": result, "service": "pushplus"}
            

        except Exception as e:
            logger.error(f"[PushPlus] 推送异常: {str(e)}")
            return {"success": False, "error": str(e), "service": "pushplus"}
        

class Qmsg(PushService):
    """Qmsg酱 v3 推送（QQ 消息）"""

    API_BASE = "https://qmsg.zendee.cn/v3/send/"
    STATUS_BASE = "https://qmsg.zendee.cn/v3/msg/status/"
    # 官方限制：msg 最长 1800 个字符，超长会被拒绝
    MAX_LENGTH = 1800
    # 官方限流：同一 key 每 3 秒最多提交一次推送
    SEND_INTERVAL = 3.0
    # 硬上限：最多发送 3 次；清洗后内容无变化时提前停止
    MAX_ATTEMPTS = 3
    # 异步状态查询：最多 3 次，每次间隔 1 秒
    STATUS_POLL_TIMES = 3
    STATUS_POLL_INTERVAL = 1.0

    # 官方明确禁止的内容：URL、IPv4、连续数字
    _VIOLATION_HINTS = ("违规", "敏感", "禁止", "非法", "连续数字", "链接", "URL", "IP地址")

    def __init__(self, key: str, group: str = ""):
        self.key = key
        self.group = group or ""
        super().__init__()

    def _validate_config(self):
        """验证Qmsg配置"""
        if not self.key:
            logger.warning(f"[Qmsg配置] key 不能为空")
        elif not isinstance(self.key, str):
            raise ValueError("Qmsg 推送 key 必须为字符串类型")
        if not isinstance(self.group, str):
            raise ValueError("Qmsg 推送 group 必须为字符串类型")

    def _truncate(self, msg: str) -> str:
        """裁剪到官方长度上限"""
        if len(msg) > self.MAX_LENGTH:
            return msg[: self.MAX_LENGTH - 3] + "..."
        return msg

    def build_msg(self, title: str, content: str) -> str:
        """拼装推送内容并裁剪到官方长度上限"""
        content = "" if content is None else str(content)
        msg = f"{title}\n{content}" if title else content
        if not msg.strip():
            msg = "（无内容）"
        return self._truncate(msg)

    def sanitize_msg(self, msg: str) -> str:
        """清洗官方明确禁止的内容，用于违规后的重试"""
        return self._truncate(sanitize_push_text(msg))

    def _send_once(self, msg: str) -> dict:
        """执行一次推送请求"""
        try:
            data = {"msg": msg}
            if self.group:
                data["group"] = self.group

            response = requests.post(f"{self.API_BASE}{self.key}", data=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            # 官方约定：以 success 字段判断业务是否成功（code 仅 0/500）
            success = isinstance(result, dict) and result.get("success") is True
            if not success:
                logger.debug(f"[Qmsg] 推送异常: {result}")

            return {"success": success, "raw": result, "service": "qmsg"}

        except Exception as e:
            # key 位于 URL 路径中，异常信息可能带出 key，日志与返回值需脱敏
            error = self._redact_key(str(e))
            logger.error(f"[Qmsg] 推送异常: {error}")
            return {"success": False, "error": error, "service": "qmsg"}

    def _query_status(self, msg_id: int):
        """查询异步消息状态，返回 0/1/2/-1，查询失败返回 None"""
        try:
            response = requests.get(
                f"{self.STATUS_BASE}{self.key}",
                params={"msgId": msg_id},
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            if isinstance(result, dict) and result.get("success") is True:
                try:
                    return int(result.get("data"))
                except (TypeError, ValueError):
                    return None
        except Exception as e:
            logger.debug(f"[Qmsg] 状态查询异常: {self._redact_key(str(e))}")
        return None

    def _poll_status(self, msg_id: int):
        """等待异步状态落定；0/超时视为已提交，不再重复推送"""
        for _ in range(self.STATUS_POLL_TIMES):
            time.sleep(self.STATUS_POLL_INTERVAL)
            status = self._query_status(msg_id)
            if status in (1, 2, -1):
                return status
        return None

    def _is_violation(self, result: dict) -> bool:
        """判断发送失败是否由内容违规导致"""
        raw = result.get("raw")
        text = ""
        if isinstance(raw, dict):
            text = str(raw.get("message") or raw.get("msg") or "")
        text = text or str(result.get("error") or "")
        return any(hint in text for hint in self._VIOLATION_HINTS)

    def _redact_key(self, text: str) -> str:
        """避免 key 随异常信息写入日志"""
        if isinstance(self.key, str) and self.key:
            return text.replace(self.key, "***")
        return text

    def _wait_before_retry(self, sent_at: float) -> None:
        """遵守官方 3 秒限流"""
        remaining = self.SEND_INTERVAL - (time.monotonic() - sent_at)
        if remaining > 0:
            time.sleep(remaining)

    def send(self, title: str, content: str) -> dict:
        """发送文本消息；确认违规时清洗内容并有限重试"""
        if not self.key:
            logger.error("[Qmsg] 推送失败: 未配置 key")
            return {"success": False, "error": "未配置 qmsg key", "service": "qmsg"}

        msg = self.build_msg(title, content)
        result = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            sent_at = time.monotonic()
            result = self._send_once(msg)

            if not result.get("success"):
                # 发送阶段即被判定违规时，清洗后重试
                if attempt < self.MAX_ATTEMPTS and self._is_violation(result):
                    cleaned = self.sanitize_msg(msg)
                    if cleaned != msg:
                        logger.warning(f"[Qmsg] 内容疑似违规，已清洗并重试 ({attempt + 1}/{self.MAX_ATTEMPTS})")
                        msg = cleaned
                        self._wait_before_retry(sent_at)
                        continue
                return result

            # 发送成功后再查异步状态：2 表示消息违规
            raw = result.get("raw")
            msg_id = raw.get("data") if isinstance(raw, dict) else None
            if not isinstance(msg_id, int) or isinstance(msg_id, bool) or msg_id <= 0:
                return result

            status = self._poll_status(msg_id)
            if status == 2:
                cleaned = self.sanitize_msg(msg)
                if attempt < self.MAX_ATTEMPTS and cleaned != msg:
                    logger.warning(f"[Qmsg] 消息违规，已清洗并重试 ({attempt + 1}/{self.MAX_ATTEMPTS})")
                    msg = cleaned
                    self._wait_before_retry(sent_at)
                    continue
                logger.error("[Qmsg] 消息内容违规，已停止重试")
                return {"success": False, "error": "消息内容违规，已停止重试", "raw": raw, "service": "qmsg"}
            if status == -1:
                logger.error("[Qmsg] 消息发送失败")
                return {"success": False, "error": "消息发送失败", "raw": raw, "service": "qmsg"}
            return result

        return result

# 新增推送服务只需继承PushService基类
class Telegram(PushService):
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
    
    def send(self, title: str, content: str) -> dict:
        # 实现Telegram推送逻辑
        pass








