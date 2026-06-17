"""
QQ空间扫码登录模块
获取二维码 → 用户扫码 → 提取Cookie
"""

import os
import re
import sys
import time
import requests


APPID = "549000912"
LOGIN_URL = "https://xui.ptlogin2.qq.com/cgi-bin/xlogin"
QRSHOW_URL = "https://ssl.ptlogin2.qq.com/ptqrshow"
QRLOGIN_URL = "https://ssl.ptlogin2.qq.com/ptqrlogin"
CHECK_SIG_REFER = "https://xui.ptlogin2.qq.com"


def _calc_ptqrtoken(qrsig):
    val = 0
    for c in qrsig:
        val += (val << 5) + ord(c)
    return val & 0x7FFFFFFF


def qr_login():
    """扫码登录QQ空间，返回 (qq_number, cookies_str) 或 (None, None)"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })

    # 1. 访问登录页获取初始Cookie
    session.get(
        LOGIN_URL,
        params={
            "appid": APPID,
            "daid": "5",
            "pt_no_auth": "1",
            "s_url": "https://qzone.qq.com",
        },
        timeout=15,
    )

    # 2. 获取二维码图片
    resp = session.get(
        QRSHOW_URL,
        params={
            "appid": APPID,
            "e": "2",
            "l": "M",
            "s": "3",
            "d": "72",
            "t": str(time.time()),
        },
        timeout=15,
    )

    qrsig = session.cookies.get("qrsig", "")
    if not qrsig:
        print("[登录失败] 无法获取二维码签名")
        return None, None

    # 保存并打开二维码图片
    script_dir = os.path.dirname(os.path.abspath(__file__))
    qr_path = os.path.join(script_dir, "_qrcode.png")
    with open(qr_path, "wb") as f:
        f.write(resp.content)

    print(f"[二维码] 已保存到: {qr_path}")
    print("[提示] 请用手机QQ扫描二维码...")

    if sys.platform == "win32":
        os.startfile(qr_path)
    elif sys.platform == "darwin":
        os.system(f'open "{qr_path}"')
    else:
        os.system(f'xdg-open "{qr_path}" 2>/dev/null &')

    # 3. 轮询扫码状态
    ptqrtoken = _calc_ptqrtoken(qrsig)

    while True:
        time.sleep(2)
        resp = session.get(
            QRLOGIN_URL,
            params={
                "u1": "https://qzone.qq.com",
                "ptqrtoken": str(ptqrtoken),
                "ptredirect": "0",
                "h": "1",
                "t": "1",
                "g": "1",
                "from_ui": "1",
                "ptlang": "2052",
                "action": f"0-0-{int(time.time() * 1000)}",
                "js_ver": "24112817",
                "js_type": "1",
                "pt_uistyle": "40",
                "appid": APPID,
                "daid": "5",
                "has_resolve": "1",
            },
            timeout=15,
        )

        text = resp.text
        code_match = re.search(r"ptuiCB\('(\d+)'", text)
        if not code_match:
            print("  [错误] 无法解析登录状态")
            continue

        code = code_match.group(1)

        if code == "66":
            print("  等待扫码...", end="\r")
        elif code == "67":
            print("  已扫码，请在手机上确认...    ", end="\r")
        elif code == "65":
            print("\n[二维码已过期] 请重新运行")
            _cleanup_qr(qr_path)
            return None, None
        elif code == "0":
            print("\n[登录成功]")
            # 提取跳转URL
            url_match = re.search(r"'(https?://[^']+)'", text)
            if not url_match:
                print("[错误] 无法提取跳转URL")
                _cleanup_qr(qr_path)
                return None, None

            redirect_url = url_match.group(1)

            # 4. 访问跳转URL获取完整Cookie
            session.get(redirect_url, timeout=15, allow_redirects=True)

            # 提取QQ号和Cookie
            uin = session.cookies.get("uin", "")
            qq_number = re.sub(r"^o0*", "", uin)

            cookie_parts = []
            for cookie in session.cookies:
                cookie_parts.append(f"{cookie.name}={cookie.value}")
            cookies_str = "; ".join(cookie_parts)

            # 保存Cookie到文件
            cookie_file = os.path.join(script_dir, "cookies.txt")
            with open(cookie_file, "w", encoding="utf-8") as f:
                f.write(cookies_str)
            print(f"[Cookie已保存] {cookie_file}")

            _cleanup_qr(qr_path)
            return qq_number, cookies_str
        else:
            msg_match = re.search(r"ptuiCB\('[^']*','[^']*','[^']*','[^']*','([^']*)'", text)
            msg = msg_match.group(1) if msg_match else f"未知状态码: {code}"
            print(f"\n[登录失败] {msg}")
            _cleanup_qr(qr_path)
            return None, None


def _cleanup_qr(qr_path):
    try:
        if os.path.exists(qr_path):
            os.remove(qr_path)
    except OSError:
        pass


if __name__ == "__main__":
    qq, cookies = qr_login()
    if qq:
        print(f"QQ号: {qq}")
        print(f"Cookie长度: {len(cookies)} 字符")
    else:
        print("登录失败")
