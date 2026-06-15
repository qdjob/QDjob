import requests, base64, json
import os

from logger import LoggerManager

# 安全获取已配置的logger实例
try:
    logger = LoggerManager().logger
except RuntimeError:
    logger = LoggerManager().setup_basic_logger()
    logger.warning("Captcha模块: 日志系统在使用前被基础配置，可能意味着此模块被单独运行")


temp_path = "temp"
if not os.path.exists(temp_path):
    os.mkdir(temp_path)

headers = {
    'Host': 'turing.captcha.qcloud.com',
    'Connection': 'keep-alive',
    'User-Agent': '',
    'Accept': '*/*',
    'X-Requested-With': 'com.qidian.QDReader',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Dest': 'script',
    'Referer': 'https://turing.captcha.qcloud.com/template/drag_ele.html',
    'Accept-Language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en-US;q=0.7,en;q=0.6',
}

def get_res_json(captcha_id):
    UA = base64.b64encode(headers['User-Agent'].encode('utf-8')).decode('utf-8')
    url = "https://turing.captcha.qcloud.com/cap_union_prehandle"
    params = {
        # "aid": "198420051",
        "aid": captcha_id,
        "protocol": "https",
        "accver": "1",
        "showtype": "popup",
        "ua": UA,
        "noheader": "0",
        "fb": "1",
        "aged": "0",
        "enableAged": "0",
        "enableDarkMode": "0",
        "grayscale": "1",
        "clientype": "1",
        "cap_cd": "",
        "uid": "",
        "lang": "zh-cn",
        "entry_url": "https://h5.if.qidian.com/new/welfareCenter/",
        "elder_captcha": "0",
        "js": "/tcaptcha-frame.97a921e6.js",
        "login_appid": "",
        "wb": "1",
        "subsid": "1",
        "callback": "_aq_396533",  # 每次都会变，应该不会校验这个参数，只是作为返回json的头
        "sess": ""
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        logger.error(f'获取验证码信息失败：{response.text}')
        return False
    res = response.text.split('(')[1].split(')')[0]
    return json.loads(res)

def save_img(icon_img_url, bg_img_url):
    path_icon = os.path.join(temp_path, 'icon.jpg')
    path_bg = os.path.join(temp_path, 'bg.jpg')
    response_icon = requests.get(url=icon_img_url)
    if response_icon.status_code != 200:
        logger.error(f'获取icon图片失败：{response_icon.text}')
        return False,'',''
    
    with open(path_icon, 'wb') as f:
        f.write(response_icon.content)
    logger.info(f'保存icon图片成功：{path_icon}')

    response_bg = requests.get(url=bg_img_url)
    if response_bg.status_code != 200:
        logger.error(f'获取bg图片失败：{response_bg.text}')
        return False,'',''
    
    with open(path_bg, 'wb') as f:
        f.write(response_bg.content)
    logger.info(f'保存bg图片成功：{path_bg}')
    return True, path_icon, path_bg

def save_tdc(url_tdc):
    path_tdc = os.path.join(temp_path, 'tdc.js')
    response_tdc = requests.get(url=url_tdc, headers=headers)
    if response_tdc.status_code != 200:
        logger.error(f'获取TDC失败：{response_tdc.text}')
        return False
    with open(path_tdc, 'wb') as f:
        f.write(response_tdc.content)
    logger.info(f'保存TDC成功：{path_tdc}')
    return path_tdc

def get_collect_eks(tokenid, icon_path, bg_path, tdc_js_path, user_agent):
    url = 'https://janiquiz.dpdns.org/gettxcollect'

    files = {
        'icon': open(icon_path , 'rb'),
        'bg': open(bg_path, 'rb'),
        'tdc_js': open(tdc_js_path, 'rb')
    }

    data = {
        'tokenid': tokenid,
        'user_agent': user_agent
    }

    response = requests.post(url=url, data=data, files=files)
    res = response.json()
    if response.status_code != 200:
        logger.error(f'获取验证码信息失败：{res}')
        return False
    logger.info(f'获取验证码信息成功：执行时间：{res.get("processing_time")}')
    logger.info(f'当前tokenid剩余次数：{"不限制"if(res.get("remaining_calls")==-1) else res.get("remaining_calls")}')
    logger.debug(f'返回验证码信息：{json.dumps(res["data"],indent=2)}')
    return res

def get_ans(positions):
    ans_json = []
    for i,position in enumerate(positions):
        ans_json.append({"elem_id": i+1, "type": "DynAnswerType_POS", "data": f"{position[0]},{position[1]}"})
    return json.dumps(ans_json, separators=(',', ':'))

def get_pow_params(tokenid, prefix, md5):
    url = 'https://janiquiz.dpdns.org/gettxpower'
    data = {
        'tokenid': tokenid,
        'prefix': prefix,
        'md5': md5
    }
    response = requests.post(url=url, data=data)
    if response.status_code != 200:
        logger.error(f'获取pow参数失败：{response.text}')
        return False
    logger.info(f'获取pow参数成功')
    logger.debug(f'获取power参数成功：{response.text}')
    return json.loads(response.text)

def get_verify(collect, eks, sess, ans, pow_answer, pow_calc_time):
    url = "https://turing.captcha.qcloud.com/cap_union_new_verify"
    data = {
        "collect": collect,
        "tlg":  str(len(collect)),
        "eks": eks,
        "sess": sess,
        "ans": ans,
        "pow_answer": pow_answer,
        "pow_calc_time": pow_calc_time
    }
    return requests.post(url, headers=headers, data=data)


def main(tokenid, captcha_a_id, user_agent):
    headers.update({'User-Agent': user_agent})

    logger.info('开始获取验证码信息')
    res_json = get_res_json(captcha_a_id)
    if not res_json:
        return False
    sess = res_json.get('sess')
    data = res_json.get('data')

    logger.info('开始保存验证码图片')
    icon_img_url = 'https://turing.captcha.qcloud.com' + data.get('dyn_show_info')['sprite_url']
    bg_img_url = 'https://turing.captcha.qcloud.com' + data.get('dyn_show_info')['bg_elem_cfg']['img_url']  # 背景图
    status, icon_path, bg_path = save_img(icon_img_url, bg_img_url)
    if not status:
        return False

    logger.info('开始保存动态TDC')
    url_tdc = 'https://turing.captcha.qcloud.com' + data.get('comm_captcha_cfg')['tdc_path']  # 动态TCD地址
    tdc_js_path = save_tdc(url_tdc=url_tdc)
    if not tdc_js_path:
        return False

    res = get_collect_eks(tokenid, icon_path, bg_path, tdc_js_path, user_agent)
    if not res:
        return False
    collect = res.get('data').get('collect')
    eks = res.get('data').get('eks')
    positions = res.get('data').get('positions')
    ans = get_ans(positions=positions)
    logger.debug(f'获取的ans：{ans}')

    logger.info('开始获取pow参数')
    prefix = data.get('comm_captcha_cfg')['pow_cfg']['prefix']
    md5 = data.get('comm_captcha_cfg')['pow_cfg']['md5']
    power = get_pow_params(tokenid=tokenid,prefix=prefix, md5=md5)
    if not power:
        return False
    pow_answer = power.get('data').get('pow_answer')
    pow_calc_time = power.get('data').get('pow_calc_time')

    logger.info('开始发送验证')
    verify_res = get_verify(collect, eks, sess, ans, pow_answer, pow_calc_time)
    verify_res = verify_res.json()
    logger.debug(f'验证结果：{verify_res}')
    if verify_res.get('errorCode') == "0":
        logger.info('验证成功')
        randstr = verify_res.get('randstr')
        ticket = verify_res.get('ticket')
        return {'code': 0,'randstr': randstr, 'ticket': ticket}
    elif verify_res.get('errorCode') == "12":
        logger.error('验证失败，设备指纹未完全通过验证')
        return {'code': 12,'message':'设备指纹未完全通过验证'}
    elif verify_res.get('errorCode') == "50":
        logger.error('验证失败，模型识别点位出错，请重试')
        return {'code': 50, 'message':'模型识别点位出错，请重试'}
    else:
        logger.error(f'验证失败，未知错误')
        return {'code': 666,'message':'未知错误'}
    

def save_img_slider(bg_img_url):
    path_bg = os.path.join(temp_path, 'bg.jpg')

    response_bg = requests.get(url=bg_img_url)
    if response_bg.status_code != 200:
        logger.error(f'获取bg图片失败：{response_bg.text}')
        return False,''
    
    with open(path_bg, 'wb') as f:
        f.write(response_bg.content)
    logger.info(f'保存bg图片成功：{path_bg}')
    return True, path_bg

def get_collect_eks_slider(tokenid, init_pos, bg_path, tdc_js_path, user_agent):
    url = 'https://janiquiz.dpdns.org/gettxcollectslider'

    files = {
        'bg': open(bg_path, 'rb'),
        'tdc_js': open(tdc_js_path, 'rb')
    }

    data = {
        'tokenid': tokenid,
        'user_agent': user_agent,
        'init_pos': json.dumps(init_pos)
    }

    response = requests.post(url=url, data=data, files=files)
    res = response.json()
    if response.status_code != 200:
        logger.error(f'获取验证码信息失败：{res}')
        return False
    logger.info(f'获取验证码信息成功：执行时间：{res.get("processing_time")}')
    logger.info(f'当前tokenid剩余次数：{"不限制"if(res.get("remaining_calls")==-1) else res.get("remaining_calls")}')
    logger.debug(f'返回验证码信息：{json.dumps(res["data"],indent=2)}')
    return res

def get_ans_slider(positions):
    ans_json = []
    ans_json.append([{"elem_id":1,"type":"DynAnswerType_POS","data":f"{positions[0]},{positions[1]}"}])
    return json.dumps(ans_json, separators=(',', ':'))

def get_pow_params_slider(tokenid, prefix, md5):
    url = 'https://janiquiz.dpdns.org/gettxpower'
    data = {
        'tokenid': tokenid,
        'prefix': prefix,
        'md5': md5
    }
    response = requests.post(url=url, data=data)
    if response.status_code != 200:
        logger.error(f'获取pow参数失败：{response.text}')
        return False
    logger.info(f'获取pow参数成功')
    logger.debug(f'获取power参数成功：{response.text}')
    return json.loads(response.text)

def get_verify_slider(collect, eks, sess, ans, pow_answer, pow_calc_time):
    url = "https://turing.captcha.qcloud.com/cap_union_new_verify"
    data = {
        "collect": collect,
        "tlg":  str(len(collect)),
        "eks": eks,
        "sess": sess,
        "ans": ans,
        "pow_answer": pow_answer,
        "pow_calc_time": pow_calc_time
    }
    return requests.post(url, headers=headers, data=data)

def main_slider(tokenid,captcha_a_id, user_agent):
    headers.update({'User-Agent': user_agent})

    logger.info('开始获取验证码信息')
    res_json = get_res_json(captcha_a_id)
    if not res_json:
        return False
    sess = res_json.get('sess')
    data = res_json.get('data')

    logger.info('开始保存验证码图片')
    bg_img_url = 'https://turing.captcha.qcloud.com' + data.get('dyn_show_info')['bg_elem_cfg']['img_url']  # 背景图
    status, bg_path = save_img_slider(bg_img_url)
    if not status:
        return False

    logger.info('开始保存动态TDC')
    url_tdc = 'https://turing.captcha.qcloud.com' + data.get('comm_captcha_cfg')['tdc_path']  # 动态TCD地址
    tdc_js_path = save_tdc(url_tdc=url_tdc)
    if not tdc_js_path:
        return False
    
    logger.info('开始获取初始化滑块位置')
    try:
        init_pos = data.get('dyn_show_info')['fg_elem_list'][1]['init_pos']
        print(init_pos)
    except Exception as e:
        logger.error(f'获取初始化滑块位置失败：{e}')
        return False

    res = get_collect_eks_slider(tokenid, init_pos, bg_path, tdc_js_path, user_agent)
    if not res:
        return False
    collect = res.get('data').get('collect')
    eks = res.get('data').get('eks')
    positions = res.get('data').get('positions')
    ans = get_ans_slider(positions=positions)
    logger.debug(f'获取的ans：{ans}')

    logger.info('开始获取pow参数')
    prefix = data.get('comm_captcha_cfg')['pow_cfg']['prefix']
    md5 = data.get('comm_captcha_cfg')['pow_cfg']['md5']
    power = get_pow_params_slider(tokenid=tokenid,prefix=prefix, md5=md5)
    if not power:
        return False
    pow_answer = power.get('data').get('pow_answer')
    pow_calc_time = power.get('data').get('pow_calc_time')

    logger.info('开始发送验证')
    verify_res = get_verify_slider(collect, eks, sess, ans, pow_answer, pow_calc_time)
    verify_res = verify_res.json()
    logger.debug(f'验证结果：{verify_res}')
    if verify_res.get('errorCode') == "0":
        logger.info('验证成功')
        randstr = verify_res.get('randstr')
        ticket = verify_res.get('ticket')
        return {'code': 0,'randstr': randstr, 'ticket': ticket}
    elif verify_res.get('errorCode') == "12":
        logger.error('验证失败，设备指纹未完全通过验证')
        return {'code': 12,'message':'设备指纹未完全通过验证'}
    elif verify_res.get('errorCode') == "50":
        logger.error('验证失败，模型识别点位出错，请重试')
        return {'code': 50, 'message':'模型识别点位出错，请重试'}
    else:
        logger.error(f'验证失败，未知错误')
        return {'code': 666,'message':'未知错误'}

if __name__ == '__main__':
    tokenid = 'test'
    # captcha_a_id = '198420051'
    captcha_a_id = '1600000770'
    user_agent = 'Mozilla/5.0 (Linux; Android 13; PDEM10 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/109.0.5414.86 MQQBrowser/6.2 TBS/047823 Mobile Safari/537.36 QDJSSDK/1.0  QDNightStyle_1  QDReaderAndroid/7.9.412/1606/1000027/OPPO/QDShowNativeLoading'
    # main(tokenid=tokenid, captcha_a_id=captcha_a_id, user_agent=user_agent)
    main_slider(tokenid=tokenid, captcha_a_id=captcha_a_id, user_agent=user_agent)



