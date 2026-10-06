## 如何抓包获取真实设备数据

**注意事项**

- 只有7.9.430及以前的版本可以简单抓包，7.9.430版本及以后的由于360加固自带反抓包，需要额外手段才能抓包。

- 真实设备必须是你自己账号已经登录过一段时间，并且能正常领取奖励的设备。

**教程正文**

1. 打开抓包软件

   <img src="./picture/realphone_1.jpg" alt="realphone_1" style="zoom:33%;" />

2. 切换到起点，然后自己选择`手机验证码登录`或者`账号密码登录`

   - **验证码登录**：
      - `https://ptlogin.yuewen.com/sdk/sendphonecode`(获取验证码)
      - `https://ptlogin.yuewen.com/sdk/phonecodelogin`(填写验证码后点击登录)
   - **账号密码登录**：
      - `https://ptlogin6.qidian.com/sdk/staticlogin`(填写账号密码后点击登录)

   <img src="./picture/realphone_2.jpg" alt="realphone_2" style="zoom:33%;" />

3. 这里演示选择账号密码登录，验证码登录的方法类似。

   <img src="./picture/realphone_3.jpg" alt="realphone_3" style="zoom:33%;" />

4. 登录成功

   <img src="./picture/realphone_4.jpg" alt="realphone_4" style="zoom:33%;" />



5. 回到小黄鸟，点击上面的搜索

   <img src="./picture/realphone_5.jpg" alt="realphone_5" style="zoom:33%;" />

6. 找到url关键词

   <img src="./picture/realphone_6.jpg" alt="realphone_6" style="zoom:33%;" />

7. 输入ptlogin来寻找目标url

   <img src="./picture/realphone_7.jpg" alt="realphone_7" style="zoom:33%;" />

8. 回到主界面可以看到账号密码登录的目标url

   <img src="./picture/realphone_8.jpg" alt="realphone_8" style="zoom:33%;" />

9. 长按，复制curl。或者点进去，点击请求，选中下方的预览，一项一项地进行填入。

   <img src="./picture/realphone_9.jpg" alt="picture_9" style="zoom:33%;" />

   <img src="./picture/realphone_10.jpg" alt="realphone_10" style="zoom:33%;" />

10. 把抓到的内容填进网页版：

    - **推荐**：打开「真实设备 → 添加设备」，把 curl 粘贴到「**① 从抓包 curl 导入（推荐）**」并点「解析并填入」，
      会自动识别设备指纹与 ibex；补全分辨率等信息、填写设备名称后保存即可。
    - 同一条 curl 里若带有账号凭据，还可以粘贴到用户详情「**登录 → ① 从抓包 curl 快速填入**」，
      把 User-Agent / ibex / Cookies 一并填入（可反复粘贴不同请求逐步补充，确认后再保存）。
    - 若抓包工具支持直接导出 `.har` 文件，也可以在「用户管理」页点「📥 从 HAR 导入」一键完成建号与导入
      （**推荐仍优先使用上面的 curl 方式**）。
