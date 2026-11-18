# push.py
import base64
import hashlib
import hmac
from datetime import datetime
import requests
import json
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

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
        """发送卡片消息"""
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
            response.raise_for_status()
            result = response.json()
            
            success = result.get("code") == 0
            if not success:
                logger.debug(f"[飞书推送] 返回异常: {result}")
            
            return {
                "success": success,
                "raw": result,
                "service": "feishu"
            }
            
        except Exception as e:
            logger.error(f"[飞书推送] 发送异常: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "service": "feishu"
            }

class ServerChan(PushService):
    """Server酱推送"""
    def __init__(self, sckey: str):
        self.sckey = sckey
        super().__init__()

    def _validate_config(self):
        """验证Server酱配置"""
        if not self.sckey.startswith("SCU"):
            logger.warning(f"[Server酱配置] sckey 格式不推荐，建议使用标准格式")
    
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
            
            success = result.get("errno") == 0
            if not success:
                logger.debug(f"[Server酱] 返回异常: {result}")
            
            return {
                "success": success,
                "raw": result,
                "service": "serverchan"
            }
            
        except Exception as e:
            logger.error(f"[Server酱] 发送异常: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "service": "serverchan"
            }
        
class QiweiPush(PushService):
    """Qiwei推送"""

    def __init__(self, webhook_url: str, userids:list, phoneids:list):
        self.webhook_url = webhook_url
        self.userids = userids
        self.phoneids = phoneids
        super().__init__()

    def _validate_config(self):
        """验证Qiwei配置"""
        if not self.webhook_url:
            logger.warning(f"[Qiwei配置] webhook_url 不能为空")

    def send(self, title: str, content: str) -> dict:
        """发送文本消息"""
        try:
            url = self.webhook_url
            data = {
                "msgtype": "text",
                "text": {
                    "content": f'## {title} \n {content}',
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
            logger.error(f"[Qiwei企业微信] 发送异常: {str(e)}")
            return {"success": False, "error": str(e), "service": "qiwei"}
        
class PushPlus(PushService):
    """PushPlus推送"""

    def __init__(self, token: str, topic: str):
        self.token = token
        self.topic = topic
        super().__init__()

    def _validate_config(self):
        """验证PushPlus配置"""
        if not self.token:
            logger.warning(f"[PushPlus配置] token 不能为空")

    def send(self, title: str, content: str) -> dict:
        """发送文本消息"""
        try: 
            url = f"http://www.pushplus.plus/send"
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
            success = result.get("code") == 200
            if not success:
                logger.debug(f"[PushPlus] 推送异常: {result}")
            return {"success": success, "raw": result, "service": "pushplus"}
            

        except Exception as e:
            logger.error(f"[PushPlus] 推送异常: {str(e)}")
            return {"success": False, "error": str(e), "service": "pushplus"}
        


class Qmsg(PushService):
    """Qmsg酱 v3 推送（QQ 消息）"""

    API_BASE = "https://qmsg.zendee.cn/v3/send/"
    # 官方限制：msg 最长 1800 个字符，超长会被拒绝
    MAX_LENGTH = 1800

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

    def build_msg(self, title: str, content: str) -> str:
        """拼装推送内容并裁剪到官方长度上限"""
        msg = f"{title}\n{content}" if title else str(content or "")
        if not msg.strip():
            msg = "（无内容）"
        if len(msg) > self.MAX_LENGTH:
            msg = msg[: self.MAX_LENGTH - 3] + "..."
        return msg

    def send(self, title: str, content: str) -> dict:
        """发送文本消息"""
        if not self.key:
            logger.error("[Qmsg] 推送失败: 未配置 key")
            return {"success": False, "error": "未配置 qmsg key", "service": "qmsg"}

        try:
            url = f"{self.API_BASE}{self.key}"
            data = {"msg": self.build_msg(title, content)}
            if self.group:
                data["group"] = self.group

            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            # 官方约定：以 success 字段判断业务是否成功（code 仅 0/500）
            success = result.get("success") is True
            if not success:
                logger.debug(f"[Qmsg] 推送异常: {result}")

            return {"success": success, "raw": result, "service": "qmsg"}

        except Exception as e:
            logger.error(f"[Qmsg] 推送异常: {str(e)}")
            return {"success": False, "error": str(e), "service": "qmsg"}


# 新增推送服务只需继承PushService基类
class Telegram(PushService):
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
    
    def send(self, title: str, content: str) -> dict:
        # 实现Telegram推送逻辑
        pass








