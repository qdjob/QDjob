## 使用方法  
### 基础使用方式
由于本项目核心加密参数不公开，因此请下载release中的exe文件，并按照以下步骤使用。[常见错误与解决方案](error_resolution.md)  

配置编辑器提供两种：**网页版（WebUI，推荐，尤其适合 Docker / 远程 / 手机）** 与 **桌面版（GUI）**。二者编辑同一份配置，任选其一即可。

#### 方式一：网页版（WebUI，推荐）
1. **下载[release](https://github.com/JaniQuiz/QDjob/releases)中的`QDjob.exe`和`QDjob_editor_web.exe`文件，放到同一个目录下**

2. **运行`QDjob_editor_web.exe`**：程序转入后台并自动打开浏览器（默认 `http://127.0.0.1:33989`）。若未自动打开，手动访问该地址即可。
   - 端口 / 监听地址 / 访问口令等参数详见 [网页版(WebUI)使用说明](./WEBUI.md)
   - 建议首次使用在「概览 → 访问口令」中设置访问口令（设置后程序会自动重启生效）

3. **在网页中配置用户**（用户名、tokenid、登录、任务、推送，各项含义与桌面版一致，见下方“方式二”步骤2的说明）

4. **配置定时**：在「任务执行」页设置定时方案（图形化或自定义 cron 表达式），也可点「立即执行一次」手动运行
   - 定时由程序自身在运行期间执行，因此**需要程序保持运行**

#### 方式二：桌面版（GUI）
1. **下载[release](https://github.com/JaniQuiz/QDjob/releases)中的`QDjob.exe`和`QDjob_editor.exe`文件，放到同一个目录下**

2. **运行`QDjob_editor.exe`，软件会自动创建配置`config.json`文件，按照下面说明配置用户，目前最大支持3个账号**  
   - 日志等级，日志保留天数，失败重试次数等保持默认即可
   - 添加/编辑用户：
     - 用户名(必填)
     - 用户类型：只能选择captcha
     - tokenid(非必填)：用于自动处理图形验证码，通过[我的网站](https://shop.janiquiz.dpdns.org)或者[我的咸鱼主页](https://m.tb.cn/h.7YjEhOz?tk=2VRJfsPwg93)获取
     - 用户登录(必填)：
       - **手动输入cookies**（目前主要方式）：输入 User-Agent、ibex 与抓包得到的 cookies；网页版在「登录 → 手动填写 Cookies」中，内置字符串转 JSON 的转换器
       - 手机验证码登录：输入手机号获取验证码登录，成功后会保存设备信息用于后续登录（受风控策略影响，成功率不稳定）
       - 账号密码登录：输入账号密码登录，需先成功进行过手机验证码登录以生成设备信息（同样受风控影响）
       - **真实设备（推荐，降低风控）**：从真机抓包 curl（或手动输入抓包参数）导入设备指纹，登录时选用即可，详见下方“真实设备与软件版本”
     - 任务配置(必填)：需要执行的任务，默认全选
     - 推送服务(非必填)：执行完毕后将任务执行情况推送到指定的服务中。
   
3. **cookies说明**  
   一般通过抓包来获取cookies，起点并没有对抓包有什么限制，使用常用的抓包软件就行，这里放上[小黄鸟(过检测版)](https://wwqe.lanzouo.com/iImXX2y6ysje) 密码:`3bt2` 
   建议抓包接口：
    - 福利中心：`https://h5.if.qidian.com/argus/api/v2/video/adv/mainPage` 
    - 观看激励视频任务：`https://h5.if.qidian.com/argus/api/v1/video/adv/finishWatch`    
   
   需要抓取字段包括：
    - User-Agent(必填)：接口的`User-Agent`字段，必须包含`QDReaderAndroid/7.9.384/1466/1000032/OPPO/QDShowNativeLoading`字段，格式类似于
    ```bash
    Mozilla/5.0 (Linux; Android 13; PDEM10 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/109.0.5414.86 MQQBrowser/6.2 TBS/047601 Mobile Safari/537.36 QDJSSDK/1.0  QDNightStyle_1  QDReaderAndroid/7.9.384/1466/1000032/OPPO/QDShowNativeLoading
    ```
    - ibex(必填)：记录设备安全信息，内容较长（由抓包得到的字符串）。
    - cookies(必填)：记录账号登录信息，格式应当为json类型，下方示例中的11项为必须包含字段。本软件提供了字符串格式`cookies`的转换功能，可以将形如`a=b;c=d;...`的字符串转换成json类型，如果抓取到的格式并非json类型，需要进行转换后再进行保存。
   ```json
   {
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
   ```

4. **目录树**  
   当你配置完毕后，目录树结构应当如下：
   ```bash
    .
    ├── cookies/
    │   └── your_username.json
    ├── logs/                      # 日志(自动生成)
    ├── config.json
    ├── devices.json               # 真实设备档案(网页版添加后生成)
    ├── versions.json              # 软件版本表(网页版添加版本后生成)
    ├── crontab.txt                # 定时表达式(网页版设置定时后生成)
    ├── QDjob.exe
    └── QDjob_editor.exe / QDjob_editor_web.exe
   ```
   
5. **运行`QDjob.exe`程序，或在编辑器中点击执行任务**（网页版：「任务执行 → 立即执行一次」）

6. **执行程序**
   * `windows`: 执行`QDjob.exe`，或在`QDjob_editor.exe`中点击执行任务，或网页版「任务执行 → 立即执行一次」
   * `linux`:
     * 打开程序的属性设置，设置`QDjob`（及编辑器）可执行，然后执行`QDjob`即可
     * linux 上 GUI 支持有限，建议使用网页版`QDjob_editor_web`：赋予可执行权限后运行，浏览器访问 `http://127.0.0.1:33989`

### 部署到docker  
   见说明文档：[部署到docker自动执行](docker_config.md)  

### Pypi包管理(仅支持linux amd64架构)  
   由[盧瞳](https://github.com/2061360308)进行维护，可直接由pip命令进行安装
   ```bash
   pip install qdjobtool
   ```
   定时任务辅助脚本命令：
   ```bash
   QDjob_cron
   ```
   更新命令：
   ```bash
   pip install qdjobtool --upgrade
   ```

### 部署到任务面板自动执行

> 教程仅包含【青龙/白虎】面板，其他面板类似
> 
> `PyPi`下的`qdjobtool`包并不是唯一部署方式，有能力可以直接在脚本管理中上传QDjob可执行文件，搭配相关脚本或者bash命令实现部署，`qdjobtool`包只是简化了QDjob版本管理以及部署流程

   见说明文档：[部署到面板自动执行](panel_usage.md)

## 阅读时长上报使用说明(已经支持搜索功能，这里仅供参考)
1. **按照上面说明配置账号** 
2. **目前已经支持书籍搜索功能和章节列表获取功能，不过这里的书籍ID和章节ID获取方式仍可供参照**
3. **每日阅读时长上报功能需要配置所要阅读的书籍ID，每章阅读时长范围和上报总时长，软件会从章节列表中随机选择连续章节进行上报。**
4. **获取书籍ID和章节ID**，在起点官网上找到你要上报时长的书籍，查看其网址  
   提取书籍ID: 
   ![bookid](picture/bookid.png)
   提取书籍ID和章节ID: 
   ![chapterid](picture/chapterid.png)
5. **配置上报数据**，打开`QDjob_editor`，选中用户，打开阅读时长上报界面，将上面的书籍ID和章节ID填入，配置阅读时长和阅读结束时间，程序会自动计算阅读开始时间，添加记录。**建议单次上报时至少上报2条记录**，否则会影响时间统计。
6. **点击确认上报**  
注：上报时长和阅读时间都设定有随机延迟，因此出现9.99分钟为正常现象。

## 真实设备与软件版本（降低风控）
风控本质是设备风控，使用**真机抓包得到的设备指纹**可显著降低风控概率。

1. 抓真机登录请求（手机验证码登录或账号密码登录均可，二者设备参数相同），复制其 `curl`。下面三种选择其中一个即可。[具体抓包过程](./realphone.md)
   - **验证码登录**：
      - `https://ptlogin.yuewen.com/sdk/sendphonecode`(获取验证码)
      - `https://ptlogin.yuewen.com/sdk/phonecodelogin`(填写验证码后点击登录)
   - **账号密码登录**：
      - `https://ptlogin6.qidian.com/sdk/staticlogin`(填写账号密码后点击登录)
2. 打开网页版「真实设备 → 添加设备」：
   - 方式①粘贴 `curl` 一键解析（推荐）
   - 方式②逐个粘贴抓包参数（`ibex` 必填）
   - 方式③手动填写完整设备字段
3. 解析会得到 `brand / model / board / cpu_abi / device_name / android_version / build_id / qid / phone_security`，以及 `ibex` 设备指纹
4. 填写自定义设备名称后保存；**保存时会一并记录解析到的软件版本**
5. 之后在用户详情「登录 → 登录设备」选择该设备，软件版本会**自动选中**（若不在版本表中会自动新增），再走登录即可
6. **（可选，次要方式）从 HAR 一键导入**：若抓包工具支持直接导出 `.har` 文件，可在网页版「用户管理」页点「📥 从 HAR 导入」，
   选择该文件即可**自动识别起点昵称**，并一次完成「新建 / 更新用户 + 保存账号凭据 + 写入设备档案 + 登记版本表」；
   推荐仍优先使用上面的 curl 导入方式。

> 网页版「用户详情 → 登录」页的折叠区「**① 从抓包 curl 快速填入（推荐）**」支持直接粘贴整段 `curl`，
> 自动填入 User-Agent / ibex / Cookies（**只填表单、不直接保存**），可反复粘贴不同请求逐步补充；
> 在设备弹窗里解析 curl 时若同时提取到账号凭据，也会提示你到这里补充。

*注：真实设备需要是你已经登陆过的并且没有风险的设备*

软件版本表（与设备无关）位置：
- 内置：`QDjob_editor/versions.json`
- 覆盖/追加：工作目录下的 `versions.json`

## 额外说明
   * 关于状态检测（网页版在用户详情「基本信息 → 🔎 状态检测」）：
       - **检测登录状态**：仅检测基础 cookies 有效性（用户资料接口）
          - 主页面登录状态影响：签到，阅读时长上报，每日抽奖
       - **检测账号风险**：除基础有效性外，还会检测福利中心接口与账号风控等级（`BanId`）
          - 福利中心登录状态影响：章节卡获取等激励相关的任务
          - 风控等级：`BanId=1` 为设备风控（需在真实设备上处理）；`BanId=2` 为验证码风控（可手动过一次验证码或配置 tokenid）
   * 关于`arm64`格式：
       - 可以使用在`安卓端termux`或者`树莓派`等arm64架构的linux系统来执行本程序 
       - GUI 图形界面暂无法打包到 arm64，可直接使用**网页版`QDjob_editor_web`**：运行后浏览器访问 `http://127.0.0.1:33989` 进行配置
       - 也可以在其它平台用编辑器配置好后，复制 `cookies`、`config.json`（及 `devices.json`、`versions.json`）到 arm64 系统下执行
   * 关于报毒问题：
       - **解决方案一：关闭windows defender自带的实时扫描**  打开设置->更新与安全->Windows安全中心->打开windows安全中心，左边点击「病毒和威胁」，然后找到「实时扫描」并关闭
       - **解决方案二：使用standalone打包版本**  在[release](https://github.com/JaniQuiz/QDjob/releases)中找到`QDjob_windows_standalone.zip`使用，详细见下面说明。
   * 关于`standalone`模式打包版本：
       - 该版本用于解决部分电脑对本程序报毒问题。
       - `QDjob`和`QDjob_editor`在该版本被打包到了一起，其他依赖文件和文件夹默认隐藏。
       - 请不要单独移动`QDjob`或者`QDjob_editor`，否则可能会导致程序无法运行，如果需要移动，请将整个文件夹一起移动。


