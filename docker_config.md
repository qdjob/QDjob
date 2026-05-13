# QDjob Docker 部署指南

> 本指南详细介绍了 QDjob 项目的 Docker 部署方式，帮助您快速完成服务搭建。

## 📌 前置说明

在开始部署前，请注意以下关键点：

1. **配置生成原理**：QDjob 容器需要`config.json`和`cookies`文件夹才能正常运行
2. **配置工具**：必须使用 `QDjob_editor`生成有效配置
   - **注意：docker部署不支持使用中文用户名**
   - 容器启动时会自动在映射目录创建空的`config.json`和`cookies`文件夹
   - 但这些空文件无法直接使用，需要通过 `QDjob_editor` 进行配置用户
3. **目录映射**：Docker 容器将 `/app` 目录映射到宿主机目录，所有配置文件都存储在此

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

### 3. 生成配置文件

1. 在[release](https://github.com/JaniQuiz/QDjob/releases)中下载并运行对应架构的`QDjob_editor`
2. 在编辑器中配置用户
3. 将生成的`config.json`和`cookies`文件夹复制到 `/your/data/path/QDjob`

### 4. 启动容器

```bash
docker run -d \
  --name qdjob \
  --restart unless-stopped \
  -v /your/data/path/QDjob:/app \
  -e TZ=Asia/Shanghai \
  janiquiz/qdjob:latest
```

> **注意**：`/your/data/path/QDjob` 需替换为您实际创建的目录路径

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
  -v /your/data/path/QDjob:/app \
  -e TZ=Asia/Shanghai \
  janiquiz/qdjob:latest
```

## 📋 Docker Compose 部署

### 1. 创建目录结构

```bash
mkdir -p ~/QDjob
cd ~/QDjob
```

### 2. 创建 `docker-compose.yml` 文件

```yaml
version: '3'
services:
  qdjob:
    image: janiquiz/qdjob:latest
    container_name: qdjob
    restart: unless-stopped
    volumes:
      - ./data:/app  # 宿主机目录映射到容器/app
    environment:
      - TZ=Asia/Shanghai
```

### 3. 生成配置文件

1. 与上面类似，先使用 `QDjob_editor.exe` 生成有效配置
2. 将`config.json`和`cookies`文件夹复制到 `~/QDjob/data` 目录

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
# 使用 QDjob_editor 生成配置后，将文件上传至 /www/wwwroot/QDjob/data

docker run -d \
  --name qdjob \
  --restart unless-stopped \
  -v /www/wwwroot/QDjob/data:/app \
  -e TZ=Asia/Shanghai \
  janiquiz/qdjob:latest
```

#### 方式二：Docker Compose 部署

1. 进入 Docker 管理器 → 容器编排 → 编排模板 → 添加  
![docker](picture/bt_docker_muban.webp)
2. 填写模板名称（如QDjob），内容如下：

```yaml
version: '3'
services:
  qdjob:
    image: janiquiz/qdjob:latest
    container_name: qdjob
    restart: unless-stopped
    volumes:
      - /www/wwwroot/QDjob/data:/app
    environment:
      - TZ=Asia/Shanghai
```

3. 保存后，点击"使用模板" → 创建容器
4. **关键步骤**：使用 `QDjob_editor` 生成配置后，通过宝塔文件管理上传至 `/www/wwwroot/QDjob/data`

### 4. 配置文件上传指南

1. 在宝塔面板中，进入 **文件** → 找到 `/www/wwwroot/QDjob/data`
2. 将本地通过 `QDjob_editor` 生成的以下文件上传：
   - `config.json`
   - `cookies`文件夹（包含所有账号的 cookie 文件）
3. 确保文件权限正确（通常默认即可），配置完毕后目录树结构如下：

![配置文件上传示意图](picture/bt_docker_filetree.webp)

## ⚙️ 配置原理详解

### QDjob 配置工作流程

1. **容器启动时**：
   - 检查映射的 `/app` 目录
   - 如不存在`config.json`和`cookies`，则创建空文件/文件夹

2. **但空配置无法使用**：
   - 容器需要有效的账号配置才能执行任务
   - 这就是为什么必须使用 `QDjob_editor` 生成配置


### 定时任务配置

默认任务执行时间为每天中午 12:00，如需修改，请参照下方Cron表达式说明自行修改`crobtab.txt`文件

**Cron 表达式结构**：

| 字段位置 | 1    | 2    | 3    | 4    | 5    |
|----------|------|------|------|------|------|
| 含义     | 分钟 | 小时 | 日期 | 月份 | 星期 |
| 取值范围 | 0-59 | 0-23 | 1-31 | 1-12 | 0-7  |

> 示例：`0 8 * * *` 表示每天早上 8:00 执行任务

## 📎 附录

### 常见问题

1. **Q：容器启动后任务不执行？**
  - A：请确认已通过 `QDjob_editor` 生成有效配置，并上传至正确目录

2. **Q：如何查看容器日志？**
  - A：查看logs目录下的日志文件或者使用docker命令查看
      ```bash
      docker logs qdjob(容器名称)
      ```

3. **Q：如何重启服务？**
  - A：使用docker命令重启
      ```bash
      docker restart qdjob(容器名称)
      ```

### 完整配置目录结构

```bash
/your/data/path/QDjob (宿主机目录)
├── config.json         # 主配置文件
├── crontab.txt         # 定时任务配置
└── cookies/            # 存放所有账号的cookie
    ├── account1.json
    ├── account2.json
    └── ...
```

> 重要提示：所有配置必须通过 `QDjob_editor` 生成后才能使用，容器不会自动生成有效配置！

