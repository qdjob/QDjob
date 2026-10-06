# QDjob 配置编辑器 WebUI

用浏览器作为界面的配置编辑器，用于编辑 `config.json` 与 `cookies`，支持定时任务、手动执行与日志查看。
与桌面版 `GUI.py` 完全独立，二者可分别使用。

## 1. 直接运行（开发 / 本地测试）

```bash
# 在 qdjob 环境中
python QDjob_editor/webui.py --host 127.0.0.1 --port 33989 --password 你的口令 --workdir .
```

参数（也可用环境变量）：

| 参数 | 环境变量 | 默认 | 说明 |
|---|---|---|---|
| `--host` | `QDJOB_HOST` | `127.0.0.1` | 监听地址；容器内用 `0.0.0.0` |
| `--port` | `QDJOB_PORT` | `33989` | 监听端口（备选 42062） |
| `--workdir` | `QDJOB_WORKDIR` | 当前目录 | 工作目录（存放 config.json / cookies / logs / crontab.txt） |
| `--password` | `QDJOB_WEBUI_PASSWORD` | 空 | 访问口令；为空则使用已保存口令或不校验 |
| `--no-browser` | — | — | 启动后不自动打开浏览器 |
| `--no-tray` | — | — | 不启用系统托盘图标 |

启动后会**自动打开默认浏览器**（容器/无桌面环境自动跳过）。
打包版在桌面环境还会显示**系统托盘图标**（右键：打开界面 / 退出；双击：打开界面）。

访问口令可在 WebUI「概览 → 访问口令」中设置，设置后程序会**自动重启**以生效。

## 2. 目录约定

WebUI 与核心 QDjob 使用同一套约定：

```
<工作目录>/
  config.json        配置文件
  cookies/           各用户的 cookies
  logs/qidian.log    核心 QDjob 日志
  logs/login.log     编辑器日志
  logs/manual_run.log 手动执行输出
  devices.json       真实设备档案（在“真实设备”页添加）
  versions.json      软件版本表（可选，工作目录中的会优先于程序内置表）
  crontab.txt        定时表达式（分 时 日 月 周）
```

> 设备信息与软件版本相互独立：
> - 设备档案放在 **工作目录 `devices.json`**；
> - 软件版本表：内置在 **程序目录 `QDjob_editor/versions.json`**（打包后随程序），可在工作目录再放一份 `versions.json` 追加/覆盖。

## 3. 手动执行与定时

- **手动执行**：程序自动查找 QDjob——
  - 打包版：当前程序目录 → 本模块目录 → 工作目录 → PATH 中的 `QDjob` / `QDjob.exe`；
  - 源码版：回退到 `python QDjob/main.py`。
  执行时以工作目录为 cwd，输出写入 `logs/manual_run.log`。

- **定时任务（进程内调度，全平台一致）**：

  - 定时由 **WebUI 进程自身**负责：**只要程序在后台运行，就会按计划执行；程序退出即停止**。
  - 不再使用 Windows 任务计划程序（`schtasks`）或用户 crontab，无系统级副作用。
  - 时间表达式统一保存在 `crontab.txt`，支持完整 5 字段 cron：`*`、`a-b`、`a,b`、`*/n`、`a/n`。
  - 页面「定时执行方案」以图形化为主：每天 / 每周 / 每月 1 号 / 每隔 N 分钟 / 每隔 N 小时；
    更复杂的规则放在页面内**折叠区「自定义 crontab 表达式」**，点击展开后填写。

## 4. 日志查看

- 自动列出 `logs/` 下的当前日志与轮转日志（如 `login.log.2026-09-23`），并解析日期展示为 `login（2026-09-23）`。
- 支持按级别过滤与 tail 行数；仅允许读取 `logs/` 目录下的日志文件（防路径穿越）。

## 5. 登录方式说明（重要）

当前受风控影响：

- **手动填写 Cookies（主要方式）**：需要填写 **User Agent（必填）**、**ibex（必填）** 与 Cookies(JSON)。
  页面内置 Cookies 转换器，可直接粘贴抓包得到的 `appId=xxx; b=xxx;` 一键转 JSON；
  也可在页面内粘贴 curl 解析填入（不直接保存），可反复粘贴不同请求逐步补充（如先登录请求拿设备参数，再业务请求拿 Cookies），确认后点「保存 Cookies」。
- **从 HAR 一键导入（推荐）**：在**用户列表页**点「从 HAR 导入」，选择抓包导出的 `.har` 文件（无需在抓包工具里找具体请求，整个文件直接导入）：
  - 自动识别**起点昵称**：同名用户不存在则新建用户、已存在则更新该用户（未识别到昵称时可手动指定导入目标）；
  - 一次性保存账号凭据（Cookies / UA / ibex），并把解析到的设备指纹写入「真实设备」档案、软件版本登记到版本表。
- 手机验证码登录 / 账号密码登录：**暂不可用**（页面已标注）。
- 设备信息：可在用户详情页查看、编辑或随机生成；登录功能完善前非必填。
- **真实设备（推荐，降低风控）**：在「真实设备」页从真机抓包 curl 导入设备指纹，然后在用户详情「登录」页选择该设备 + 软件版本，即可用真机指纹登录。

## 6. Docker 部署（推荐给容器用户）

镜像内同时包含核心 QDjob 与 WebUI（不含 GUI）。

```bash
docker run -d \
  -p 33989:33989 \
  -e QDJOB_MODE=both \
  -e QDJOB_WEBUI_PASSWORD=你的口令 \
  -e TZ=Asia/Shanghai \
  -v qdjob_data:/app \
  janiquiz/qdjob:latest
```

模式 `QDJOB_MODE`：

- `webui`（默认）/ `both`：运行 WebUI，定时由**进程内调度**负责（推荐）；
- `cron`：仅运行系统 cron（兼容旧行为，无 WebUI、无进程内调度；读取 `crontab.txt`）。

> 因为定时由 WebUI 进程负责，请让容器保持运行（建议加 `--restart unless-stopped`）。

数据卷 `/app` 保存 `config.json`、`cookies/`、`logs/`、`crontab.txt`。访问 `http://<主机>:33989` 即可配置。
（容器内不显示托盘、不自动开浏览器；口令由 `QDJOB_WEBUI_PASSWORD` 管理时无法在页面修改。）

## 7. 安全提示


- 请务必设置 `QDJOB_WEBUI_PASSWORD`，尤其是把端口映射到公网时；cookies 属于敏感凭据。
- WebUI 默认仅监听 `127.0.0.1`；容器内由 entrypoint 设为 `0.0.0.0`。

## 8. 真实设备与软件版本

### 8.1 方式①：从抓包 curl 导入（推荐，降低风控）
[详细抓取教程](./realphone.md)
1. 用抓包工具（Fiddler / Charles / Reqable / mitmproxy 等）抓真机**登录请求**，复制其 **curl**；
   - 手机验证码登录、账号密码登录均可，二者设备参数一致（密码字段与设备无关）。
2. 打开 WebUI「真实设备 → 添加设备」，把 curl 粘贴到「① 从抓包 curl 导入」，点「解析并填入」；
3. 自动得到 `brand / model / board / cpu_abi / device_name / android_version / build_id / qid / qidth / phone_security`，
   以及 **ibex 设备指纹模板**（登录时注入新时间戳，逐字节还原真机指纹）；
4. 补全抓包中无法获得的项（分辨率等，可保持默认），填写一个自定义「设备名称」，保存。

> curl 解析器支持 bash 与 Windows cmd（`^` 续行）两种风格，自动识别 `-H` 头部
> （User-Agent / Cookie / ibex）、URL query 与 `-d` / `--data*` 请求体参数。
> 同一个 curl 解析出的 Cookies / UA / ibex 也可在用户详情页「登录」处再次粘贴，逐步填入账号凭据。

### 10.2 方式②：手动输入抓包参数（默认折叠）

在弹窗「② 手动输入抓包参数」中逐个粘贴抓包字段，点「解析并填入」：

| 字段 | 是否必需 | 说明 |
|---|---|---|
| `ibex` | **必需** | 设备指纹；解析后得到 qid、品牌型号、phone_security 等 |
| `devicetype` | 可选 | 形如 `Lenovo_TB128FU`（品牌_型号） |
| `devicename` | 可选 | 形如 `小新Pad 2022` |
| `osversion` | 可选 | 形如 `Android12_7.9.420_1656`（含 Android 版本与软件版本） |
| `version` | 可选 | 版本编号，如 `1656` |
| `sdkversion` | 可选 | 如 `401` |
| `signature` | 可选 | **非必需**，仅在未填 ibex 时用于兜底提取 qid |

> **关于 `signature`**：它是用 `qid + 当前时间` 生成的（`encode_signature`），程序在每次请求时会**自行重新生成**，
> 所以**不需要从抓包保存**。抓包里的 `signature` 唯一用途是「没有 ibex 时兜底取出 qid」。

### 8.3 方式③：完整设备字段（手动填写，已折叠）

在「③ 设备字段（完整，可手动修改/补充）」中逐个填写全部字段。其中 `brand / model / qid / phone_security` 为必需项；
没有 ibex 指纹时程序会用通用算法生成，保真度不如方式①②。

> 说明：分辨率、`phone_security_over`、`android_id/jpush_id` 不在登录包中，缺省不影响主要使用；
> `phone_security_over` 缺省时自动等于 `phone_security`。
> 另有「用户列表页 → 从 HAR 导入」可一键新建/更新用户并自动登记设备档案（见「登录方式说明」）。

### 8.4 登录时选择设备与版本

在用户详情 →「登录」页的「🧬 登录设备」卡片中：

- **设备来源**：`随机生成设备` 或你保存的真实设备；
- **软件版本**：默认**自动选中该设备保存的版本**（也可手动改选其它版本）；
  若该版本不在版本表中（例如你还没补充新版本信息），切换设备时会**自动加入版本表**；
- 点「准备登录设备」后，再走手机验证码 / 账号密码登录即可；
- 卡内折叠区「查看 / 编辑当前设备信息」可查看/编辑当前会话设备 JSON，并「保存到该用户」。

> 保存设备档案时，解析到的软件版本会一并记录到该设备（方式①②会自动填入；方式③的版本字段为**可选**，可留空）。

### 8.5 软件版本表放哪里

版本号与设备无关，单独维护：

- **内置（随程序打包）**：`QDjob_editor/versions.json`
- **工作目录覆盖/追加（无需重新打包）**：`<工作目录>/versions.json`

格式（`version` / `versioncode` / `sdkversion`）：

```json
{
  "versions": [
    { "version": "7.9.420", "versioncode": "1656", "sdkversion": "401" },
    { "version": "7.9.432", "versioncode": "1736", "sdkversion": "401" }
  ]
}
```

也可以在「真实设备」页底部的「软件版本」卡片里直接添加（会写入工作目录 `versions.json`）。

## 9. 状态检测与风控等级

用户详情「基本信息 → 🔎 状态检测」提供四项，含义不同：

| 按钮 | 检测范围 |
|---|---|
| 检测 tokenid | tokenid 的有效期与剩余调用次数 |
| 检测登录状态 | **仅**基础 cookies 有效性（用户资料接口是否返回昵称） |
| 检测账号风险 | **更全面**：基础有效性 + 福利中心接口 + 账号风控等级（`RiskConf.BanId`） |
| 刷新 Cookies | 重新登录 druidv6 获取新的 cmfuToken |

风控等级（`RiskConf.BanId`；返回中没有 `RiskConf` 即表示无风控）：

| BanId | 含义 | 建议 |
|---|---|---|
| （无 RiskConf） | 无风控 | 正常使用 |
| `1` | 设备风控 | 设备环境异常（root / 模拟器 / 指纹异常等），本项目无法自动解决，需在真实设备上处理 |
| `2` | 验证码风控 | 后续执行任务可能触发验证码；可在真实设备手动通过一次验证码，或配置 tokenid 自动过验证码 |
| 其他 | 未知风控 | 把检测结果反馈给作者以补充处理方案 |

检测结果会**同时**显示在按钮附近（持久）与右上角（Toast），避免错过。
