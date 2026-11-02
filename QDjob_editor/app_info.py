"""
应用元信息（版本 / 作者 / 链接 / 声明）。

WebUI 与 GUI 共享同一份版本与作者信息，避免多处硬编码。
"""

VERSION = "v1.4.3"
AUTHOR = "JaniQuiz"
PROJECT = "QDjob"

GITHUB_URL = "https://github.com/qdjob/QDjob"
TELEGRAM_URL = "https://t.me/+6xMW_7YK0o1jMDE1"
XIANYU_URL = "https://www.goofish.com/item?id=1000811249803"

DISCLAIMER = "本项目为个人项目，仅供学习交流使用，请勿用于非法用途，如有侵权，请联系删除。"
TOKENID_NOTICE = "图形验证码自动处理功能需要获取 tokenid，您可以在我的咸鱼上购买。"


def meta_dict():
    return {
        "version": VERSION,
        "author": AUTHOR,
        "project": PROJECT,
        "github": GITHUB_URL,
        "telegram": TELEGRAM_URL,
        "xianyu": XIANYU_URL,
        "disclaimer": DISCLAIMER,
        "tokenid_notice": TOKENID_NOTICE,
    }

