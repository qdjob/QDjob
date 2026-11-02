# QDjob Docker 部署指南

> ⚠️ **重要通知**：桌面版 GUI（`QDjob_editor.exe` / `GUI.py`）自 **v1.4.3** 起不再维护，功能不再更新。请统一使用网页版 WebUI（`QDjob_editor_web.exe`），本文中的配置编辑器均指 WebUI。

> 本指南详细介绍了 QDjob 项目的 Docker 部署方式，帮助您快速完成服务搭建。

## 📌 前置说明

在开始部署前，请注意以下关键点：

1. **镜像已内置网页版配置界面（WebUI）**：容器启动后，浏览器访问 `http://<主机IP>:33989` 即可完成全部配置，**无需**事先在本地用 `QDjob_editor_web` 生成配置文件
2. **访问口令**：建议通过环境变量 `QDJOB_WEBUI_PASSWORD` 设置访问口令；未设置时，任何能访问该端口的人都可以修改配置
   - **注意：建议避免使用中文用户名**（容器语言环境可能导致异常）
   - 容器启动时会自动在映射目录创建空的 `config.json` 和 `cookies` 文件夹
3. **目录映射**：Docker 容器将 `/app` 目录映射到宿主机目录，`config.json`、`cookies`、`logs`、`crontab.txt`、`devices.json`、`versions.json` 都存储在此
4. **定时方式**：默认由程序自身在运行期间按计划执行（进程内调度），因此**请让容器保持运行**；如需无 WebUI 的纯系统 cron 模式，可设置 `QDJOB_MODE=cron`

## 🐳 Docker 原生命令部署

### 1. 基础环境准备

```bash
# 确认 Docker 已正确安装
docker info
```
### 2. 创建配置目录（关键步骤）

```bash
# 创建宿主机配置目录（请替换为您的实际路径）
mkdir -p /your/data/path/QDjob
```

### 3. 配置用户（二选一）

- **方式一（推荐）**：跳过本步骤，直接按第 4 步启动容器，然后浏览器访问 `http://<主机IP>:33989` 在网页中配置
- **方式二**：事先使用 `QDjob_editor_web` 在本地配置好后，将 `config.json` 和 `cookies` 文件夹复制到 `/your/data/path/QDjob`

### 4. 启动容器

```bash
docker run -d \
  --name qdjob \
  --restart unless-stopped \
  -p 33989:33989 \
  -v /your/data/path/QDjob:/app \
  -e TZ=Asia/Shanghai \
  -e QDJOB_WEBUI_PASSWORD=你的访问口令 \
  janiquiz/qdjob:latest
```

> **注意**：`/your/data/path/QDjob` 需替换为您实际创建的目录路径；`-p 33989:33989` 用于将容器内的 WebUI 映射出来

启动后浏览器访问 `http://<主机IP>:33989`，输入访问口令即可开始配置。

### 5. 后续Docker镜像的更新和容器更新
1. 拉取更新后的 Docker 镜像：
```bash
docker pull janiquiz/qdjob:latest
```
2. 更新容器：
停止并删除旧容器
```bash
docker stop qdjob && docker rm qdjob
```
创建并启动新容器(原本配置好的用户数据会保留)
```bash
docker run -d \
  --name qdjob \
  --restart unless-stopped \
  -p 33989:33989 \
  -v /your/data/path/QDjob:/app \
  -e TZ=Asia/Shanghai \
  -e QDJOB_WEBUI_PASSWORD=你的访问口令 \
  janiquiz/qdjob:latest
```

## 📋 Docker Compose 部署

### 1. 创建目录结构

```bash
mkdir -p ~/QDjob
cd ~/QDjob
```

### 2. 创建 `docker-compose.yml` 文件

> 仓库根目录已提供可直接使用的 `docker-compose.yml`，也可按下方内容自行创建。

```yaml
services:
  qdjob:
    image: janiquiz/qdjob:latest
    container_name: qdjob
    restart: unless-stopped
    ports:
      - "33989:33989"          # 宿主机端口:容器WebUI端口
    volumes:
      - ./data:/app            # 宿主机目录映射到容器/app
    environment:
      - TZ=Asia/Shanghai
      - QDJOB_WEBUI_PASSWORD=你的访问口令
```

### 3. 配置用户（二选一）

- **方式一（推荐）**：直接启动服务后，浏览器访问 `http://<主机IP>:33989` 在网页中配置
- **方式二**：事先使用编辑器配置好后，将 `config.json` 和 `cookies` 文件夹复制到 `~/QDjob/data` 目录
  - 与上面类似，先使用 `QDjob_editor_web.exe` 生成有效配置

### 4. 启动服务

```bash
# 在 docker-compose.yml 所在目录执行
docker-compose up -d
```

### 5. 后续Docker镜像的更新和容器更新
1. 拉取更新后的 Docker 镜像：
到docker-compose.yml所在目录执行
```bash
docker compose pull
```
2. 更新容器：
```bash
docker compose up -d
```

## 🖥️ 宝塔面板部署指南

### 1. 安装宝塔面板

```bash
# 通用安装脚本
if [ -f /usr/bin/curl ];then curl -sSO https://download.bt.cn/install/install_panel.sh;else wget -O install_panel.sh https://download.bt.cn/install/install_panel.sh;fi;bash install_panel.sh ed8484bec
```

> 安装完成后，根据提示信息登录面板，并开放对应端口（默认 8888）

### 2. 安装 Docker 管理器

1. 进入宝塔面板
2. 软件商店 → 搜索 "Docker" → 安装 Docker 管理器

### 3. 部署 QDjob

#### 方式一：命令行部署

1. 打开宝塔面板的终端
2. 执行以下命令：

```bash
mkdir -p /www/wwwroot/QDjob/data

docker run -d \
  --name qdjob \
  --restart unless-stopped \
  -p 33989:33989 \
  -v /www/wwwroot/QDjob/data:/app \
  -e TZ=Asia/Shanghai \
  -e QDJOB_WEBUI_PASSWORD=你的访问口令 \
  janiquiz/qdjob:latest
```

> 启动后，浏览器访问 `http://<面板服务器IP>:33989` 进行配置（注意在宝塔「安全」中放行该端口）

#### 方式二：Docker Compose 部署

1. 进入 Docker 管理器 → 容器编排 → 编排模板 → 添加  
![docker](picture/bt_docker_muban.webp)
2. 填写模板名称（如QDjob），内容如下：

```yaml
services:
  qdjob:
    image: janiquiz/qdjob:latest
    container_name: qdjob
    restart: unless-stopped
    ports:
      - "33989:33989"
    volumes:
      - /www/wwwroot/QDjob/data:/app
    environment:
      - TZ=Asia/Shanghai
      - QDJOB_WEBUI_PASSWORD=你的访问口令
```

3. 保存后，点击"使用模板" → 创建容器
4. **配置用户（二选一）**：
   - **方式一（推荐）**：浏览器访问 `http://<面板服务器IP>:33989`（先在宝塔「安全」放行该端口）在网页中配置
   - **方式二**：使用 `QDjob_editor_web` 生成配置后，通过宝塔文件管理上传至 `/www/wwwroot/QDjob/data`

### 4. 配置文件上传说明（方式二）

1. 在宝塔面板中，进入 **文件** → 找到 `/www/wwwroot/QDjob/data`
2. 将本地通过 `QDjob_editor_web` 生成的以下文件上传：
   - `config.json`
   - `cookies`文件夹（包含所有账号的 cookie 文件）
3. 确保文件权限正确（通常默认即可），配置完毕后目录树结构如下：

![配置文件上传示意图](picture/bt_docker_filetree.webp)

## ⚙️ 配置原理详解

### QDjob 配置工作流程

1. **容器启动时**：
   - 检查映射的 `/app` 目录
   - 如不存在 `config.json` 和 `cookies`，则创建空文件/文件夹

2. **推荐配置方式**：
   - 容器内置网页版（WebUI），浏览器访问 `http://<主机IP>:33989` 即可完成用户、真实设备、定时方案等全部配置

3. **也可以离线配置**：
   - 使用 `QDjob_editor_web` 在本地生成配置后，复制到映射目录

### 定时任务配置

默认任务执行时间为每天中午 12:00，**推荐在网页版「任务执行」页设置**（支持图形化与自定义 cron 表达式），保存后写入 `crontab.txt`；也可按下方说明手工修改该文件。

**Cron 表达式结构**：

| 字段位置 | 1    | 2    | 3    | 4    | 5    |
|----------|------|------|------|------|------|
| 含义     | 分钟 | 小时 | 日期 | 月份 | 星期 |
| 取值范围 | 0-59 | 0-23 | 1-31 | 1-12 | 0-7  |

> 示例：`0 8 * * *` 表示每天早上 8:00 执行任务

**执行方式说明**：

- 默认由程序自身在运行期间按计划执行（**进程内调度**），因此**容器需要保持运行**（建议使用 `--restart unless-stopped`）
- 若设置环境变量 `QDJOB_MODE=cron`，则由容器内的系统 cron 执行（无 WebUI），此时同样读取 `crontab.txt`

## 📎 附录

### 常见问题

1. **Q：容器启动后任务不执行？**
  - A：请确认已配置有效用户（推荐直接在容器内置的网页版中配置），并让容器保持运行（进程内定时需要程序在运行）

2. **Q：网页版（WebUI）打不开 / 无法访问？**
  - A：请确认启动命令包含 `-p 33989:33989`；若在云服务器或宝塔面板上，还需在安全组/防火墙放行该端口；浏览器访问 `http://<主机IP>:33989`

3. **Q：忘记访问口令了？**
  - A：删除映射目录下的 `.webui_auth.json` 后重启容器即可清除口令；也可在启动时用 `-e QDJOB_WEBUI_PASSWORD=新口令` 覆盖

4. **Q：如何查看容器日志？**
  - A：在网页版「日志」页查看，或查看logs目录下的日志文件，也可使用docker命令查看
      ```bash
      docker logs qdjob(容器名称)
      ```

5. **Q：如何重启服务？**
  - A：使用docker命令重启
      ```bash
      docker restart qdjob(容器名称)
      ```

### 完整配置目录结构

```bash
/your/data/path/QDjob (宿主机目录)
├── config.json         # 主配置文件
├── cookies/            # 存放所有账号的cookie
│   ├── account1.json
│   ├── account2.json
│   └── ...
├── devices.json        # 真实设备档案（网页版添加后生成）
├── versions.json       # 软件版本表（网页版添加版本后生成）
├── crontab.txt         # 定时表达式（网页版设置定时后生成）
└── logs/               # 日志目录（自动生成）
```

> 提示：推荐直接使用容器内置的网页版（WebUI）进行配置；也可用 `QDjob_editor_web` 生成配置后上传。

