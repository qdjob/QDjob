# 起点阅读自动化任务  

## 简介
本项目支持自动化完成起点的签到、激励任务、抽奖等日常操作，支持多用户和多种推送方式。每天50点章节卡，追一两本书不是问题。为避免恶意利用本程序，目前最大仅支持配置3个账号。

## 主要功能
1. **主要实现的功能**  
   目前实现以下功能  
   - 手机验证码登录 (尚未完全完工，会提示风险无法使用，目前建议继续使用手动抓包)
   - 账号密码登录
   - 自动签到（每日签到）
   - 激励视频任务 10点+10点+20点=40点章节卡
   - 额外章节卡任务 (额外3次小视频) 10点章节卡
   - 每日抽奖任务
   - 游戏中心任务
   - 每周自动兑换章节卡(仅周日执行本任务)
   - 阅读时长上报(支持配置每日任务和手动在QDjob_editor中单次上报)
   - 章节卡信息推送(章节卡过期提醒)
   - 验证码处理(需要配置tokenid)

3. **多平台推送支持**  
   目前仅支持以下推送服务，如果有想要更多支持的推送服务，欢迎提issue。
   - 飞书群聊机器人(`webhookurl`, `secret`)，创建一个群，然后就可以为群内添加机器人
   - Server酱(`SCKEY`)
   - 企业微信推送
   - pushplus推送

4. **智能重试机制**  
   - 自动重试失败任务，默认最大重试3次（可配置重试次数）
   - 有一定概率遇到图形验证码，如果拥有tokenid，则会自动处理图形验证码，否则停止执行。

5. **完整日志系统**  
   - 支持按天分割日志
   - 可配置日志保留周期，默认是7天
   - 多级别日志记录（`DEBUG/INFO/ERROR`，默认`INFO`）

## 项目架构
```bash
📦 项目根目录
├── 📄 config.json               # 用户配置文件
├── 📄 README.md                 # 项目说明
├── 📄 usage.md                  # 使用方法说明
├── 📂 cookies                   # 用户cookies储存文件夹
│   └── 📄 username.json         # 用户cookies文件
├── 📂 QDjob                     # QDjob程序
│   ├── 🐍 Captcha.py            # 图形验证码处理模块
│   ├── 🐍 logger.py             # 日志模块
│   ├── 🐍 main.py               # 程序入口
│   ├── 🐍 push.py               # 推送服务模块
│   ├── 🐍 enctrypt_qidian.py    # 核心加密模块(不公开，避免项目寄掉)
│   └── 🐍 QDjob.py              # QDjob主体模块
└── 📂 QDjob_editor              # QDjob_editor程序
    ├── 🐍 captcha_verifier.py   # 图形验证码处理模块
    ├── 🐍 GUI.py                # 图形界面主体模块
    ├── 🐍 logger.py             # 日志模块
    ├── 🐍 enctrypt_qidian.py    # 核心加密模块(不公开，避免项目寄掉)
    ├── 🐍 Login.py              # 登录协议模块(不公开，避免被针对)
    ├── 📄 login_data.json       # 模拟设备信息数据(不公开，避免被针对)
    └── 📂 template              
        └── 📄 template.html     # 图形验证码渲染html
```

## 使用方法
[使用方法](https://github.com/JaniQuiz/QDjob/blob/main/usage.md)
[常见错误与解决方案](error_resolution.md)

 * 程序本体**免费使用**，仅自动过图形验证码功能需要获取tokenid(验证码指任务执行过程中的图形验证码，并非登录用到的手机验证码)  
 * 如何获取tokenid: [我的网站](https://shop.janiquiz.dpdns.org)
 * 售后问题请进入下方的TG群组或者邮箱联系

### 配置日常运行  
请在完成了上面的配置后，按照以下步骤实现每日自动托管运行。
1. **windows任务计划程序**  
将`QDjob.exe`程序放入计划任务中，并设置计划任务执行时间。详细请自行搜索相关教程。  
2. **`ztasker`(推荐)**  
使用`ztasker`来配置每日执行，比任务计划程序更加稳定。点这里：[官网网址](https://www.everauto.net/cn/index.html)

## 关于`issue`
* 如果发现任何问题，欢迎在`issue`中提出来，在提`issue`时请将日志等级改为`DEBUG`，并在日志内容中包含你所遇到的问题。

## TODO
 *  添加更多推送服务
 *  自动更新cookies来保持登录状态
 ······

## 赞助
如果你喜欢本项目，可以赞助支持：
<div style="display: flex; justify-content: center; gap: 20px;">
  <img src="./picture/vx.png" alt="微信赞助" style="width: 300px; height: auto;" />
  <img src="./picture/zfb.jpg" alt="支付宝赞助" style="width: 300px; height: auto;" />
</div>

## Contact
[点此加入Telegram群组](https://t.me/+6xMW_7YK0o1jMDE1)  
联系邮箱：janiquiz@163.com

## 叠甲
    本项目为个人项目，仅供学习交流使用，请勿用于非法用途，请于下载后24小时内删除。
    如有侵权，请联系删除。


<div align="center">
  Made with ❤️ by <a href="https://github.com/qdjob">qdjob</a>
  <br>
  如果这个项目对你有帮助，请考虑给一个 ⭐️
</div>

























