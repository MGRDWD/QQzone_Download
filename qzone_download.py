"""
QQ空间相册原图下载工具
按相册名/分类创建文件夹，保存原始质量JPG到指定目录
"""

import os
import re
import sys
import json
import time
import requests

# ============ 配置区 ============
SAVE_DIR = r"E:\qq"
# 请在浏览器登录QQ空间后，从开发者工具中获取以下信息
QQ_NUMBER = ""          # 你的QQ号
COOKIES_STR = ""        # 从浏览器复制的完整Cookie字符串
# ================================


class QZoneDownloader:
    def __init__(self, qq_number, cookies_str, save_dir):
        self.qq = qq_number
        self.save_dir = save_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"https://user.qzone.qq.com/{self.qq}/photo",
            "Origin": "https://user.qzone.qq.com",
        })
        self._parse_cookies(cookies_str)
        self.g_tk = self._calc_g_tk()
        print(f"[初始化] QQ: {self.qq}, g_tk: {self.g_tk}")
        print(f"[保存目录] {self.save_dir}")

    def _parse_cookies(self, cookies_str):
        self.cookies = {}
        if not cookies_str.strip():
            return
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, val = item.split("=", 1)
                self.cookies[key.strip()] = val.strip()
        self.session.cookies.update(self.cookies)

    def _calc_g_tk(self):
        p_skey = self.cookies.get("p_skey", "")
        hash_val = 5381
        for c in p_skey:
            hash_val += (hash_val << 5) + ord(c)
        return hash_val & 0x7FFFFFFF

    def _safe_filename(self, name):
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = name.strip('. ')
        return name if name else "未命名"

    def get_album_list(self):
        albums = []
        page_start = 0
        page_size = 100

        while True:
            url = (
                f"https://h5.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/fcg_list_album_v3"
                f"?g_tk={self.g_tk}"
                f"&hostUin={self.qq}"
                f"&uin={self.qq}"
                f"&appid=4"
                f"&inCharset=utf-8"
                f"&outCharset=utf-8"
                f"&source=qzone"
                f"&plat=qzone"
                f"&format=jsonp"
                f"&notice=0"
                f"&filter=1"
                f"&handset=4"
                f"&pageNumModeSort=40"
                f"&pageNumModeClass=15"
                f"&needUserInfo=1"
                f"&idcNum=4"
                f"&callbackFun=shine0"
                f"&callback=shine0_Callback"
                f"&pageStart={page_start}"
                f"&pageNum={page_size}"
            )

            resp = self.session.get(url, timeout=30)
            data = self._parse_jsonp(resp.text)

            if not data or data.get("code") != 0:
                print(f"[错误] 获取相册列表失败: {data}")
                break

            album_list = data.get("data", {}).get("albumListModeSort", [])
            if not album_list:
                album_list = data.get("data", {}).get("albumListModeClass", [])

            if not album_list:
                break

            for album in album_list:
                albums.append({
                    "id": album.get("id", ""),
                    "name": album.get("name", "未命名相册"),
                    "total": album.get("total", 0),
                    "classid": album.get("classid", 0),
                    "className": self._get_class_name(album.get("classid", 0)),
                })

            if len(album_list) < page_size:
                break
            page_start += page_size
            time.sleep(0.5)

        print(f"[相册] 共找到 {len(albums)} 个相册")
        return albums

    def _get_class_name(self, classid):
        class_map = {
            0: "未分类",
            1: "个人",
            2: "风景",
            3: "动物",
            4: "其他",
            100: "说说配图",
            101: "手机相册",
            102: "视频",
        }
        return class_map.get(classid, f"分类{classid}")

    def get_photo_list(self, album_id, album_name, total):
        photos = []
        page_start = 0
        page_size = 500

        while True:
            url = (
                f"https://h5.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/cgi_list_photo"
                f"?g_tk={self.g_tk}"
                f"&hostUin={self.qq}"
                f"&uin={self.qq}"
                f"&topicId={album_id}"
                f"&pageStart={page_start}"
                f"&pageNum={page_size}"
                f"&mode=0"
                f"&noTopic=0"
                f"&skipCmt498count=0"
                f"&singleurl=1"
                f"&batchId="
                f"&notice=0"
                f"&appid=4"
                f"&inCharset=utf-8"
                f"&outCharset=utf-8"
                f"&source=qzone"
                f"&plat=qzone"
                f"&format=jsonp"
                f"&callbackFun=shine0"
                f"&callback=shine0_Callback"
            )

            resp = self.session.get(url, timeout=30)
            data = self._parse_jsonp(resp.text)

            if not data or data.get("code") != 0:
                print(f"  [错误] 获取照片列表失败: {album_name}")
                break

            photo_list = data.get("data", {}).get("photoList", [])
            if not photo_list:
                break

            for photo in photo_list:
                raw_url = (
                    photo.get("raw")
                    or photo.get("origin_url")
                    or photo.get("url")
                    or photo.get("custom_url")
                    or ""
                )

                if photo.get("raw_upload"):
                    raw_url = photo["raw_upload"]

                if not raw_url:
                    continue

                raw_url = self._ensure_original_url(raw_url)

                photos.append({
                    "url": raw_url,
                    "name": photo.get("name", ""),
                    "desc": photo.get("desc", ""),
                    "lloc": photo.get("lloc", ""),
                    "shootTime": photo.get("shootTime", ""),
                    "uploadTime": photo.get("uploadtime", ""),
                })

            if len(photo_list) < page_size:
                break
            page_start += page_size
            time.sleep(0.3)

        return photos

    def _ensure_original_url(self, url):
        if not url:
            return url
        url = re.sub(r'/[0-9]+$', '', url)
        if url.startswith("http://"):
            url = url.replace("http://", "https://", 1)
        return url

    def _parse_jsonp(self, text):
        try:
            match = re.search(r'_Callback\((.*)\)\s*;?\s*$', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            print(f"  [解析错误] {e}")
        return None

    def download_photo(self, url, save_path):
        if os.path.exists(save_path):
            return True

        try:
            resp = self.session.get(url, timeout=60, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type and "octet-stream" not in content_type:
                print(f"    [跳过] 非图片内容: {content_type}")
                return False

            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True

        except requests.RequestException as e:
            print(f"    [下载失败] {e}")
            return False

    def run(self):
        if not self.qq or not self.cookies:
            print("=" * 60)
            print("错误：请先配置QQ号和Cookie！")
            print("=" * 60)
            print()
            print("使用步骤：")
            print("1. 用Chrome浏览器打开并登录 https://user.qzone.qq.com")
            print("2. 按F12打开开发者工具 → Network(网络)标签")
            print("3. 刷新页面，找到任意请求")
            print("4. 在请求头中找到 Cookie，复制完整内容")
            print("5. 将QQ号和Cookie填入本脚本顶部的配置区")
            print()
            print("或使用命令行参数：")
            print("  python qzone_download.py <QQ号> <Cookie字符串>")
            return

        os.makedirs(self.save_dir, exist_ok=True)

        print("\n[步骤1] 获取相册列表...")
        albums = self.get_album_list()
        if not albums:
            print("[失败] 未获取到相册，请检查Cookie是否过期")
            return

        total_photos = sum(a["total"] for a in albums)
        print(f"\n[统计] 共 {len(albums)} 个相册，约 {total_photos} 张照片")
        print("-" * 60)

        downloaded_count = 0
        failed_count = 0

        for i, album in enumerate(albums, 1):
            album_name = self._safe_filename(album["name"])
            class_name = self._safe_filename(album["className"])

            if class_name and class_name != "未分类":
                album_dir = os.path.join(self.save_dir, class_name, album_name)
            else:
                album_dir = os.path.join(self.save_dir, album_name)

            os.makedirs(album_dir, exist_ok=True)

            print(f"\n[{i}/{len(albums)}] 相册: {album['name']} (共{album['total']}张)")
            print(f"  保存到: {album_dir}")

            photos = self.get_photo_list(album["id"], album["name"], album["total"])
            if not photos:
                print(f"  [跳过] 相册为空或获取失败")
                continue

            album_downloaded = 0
            album_failed = 0

            for j, photo in enumerate(photos, 1):
                filename = self._generate_filename(photo, j)
                save_path = os.path.join(album_dir, filename)

                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    print(f"  [{j}/{len(photos)}] 已存在，跳过: {filename}")
                    album_downloaded += 1
                    downloaded_count += 1
                    continue

                print(f"  [{j}/{len(photos)}] 下载: {filename}", end=" ")

                success = self.download_photo(photo["url"], save_path)
                if success:
                    size_kb = os.path.getsize(save_path) / 1024
                    print(f"OK ({size_kb:.0f}KB)")
                    album_downloaded += 1
                    downloaded_count += 1
                else:
                    print("FAIL")
                    album_failed += 1
                    failed_count += 1

                time.sleep(0.2)

            # 校验本地照片数量
            local_jpg_count = len([
                f for f in os.listdir(album_dir)
                if f.lower().endswith((".jpg", ".jpeg"))
            ])
            expected = album["total"]
            api_count = len(photos)

            print(f"\n  [校验] 相册「{album['name']}」:")
            print(f"    QQ空间显示: {expected} 张")
            print(f"    API返回:    {api_count} 张")
            print(f"    本地已有:   {local_jpg_count} 张")
            print(f"    本次下载:   {album_downloaded} 成功, {album_failed} 失败")

            if local_jpg_count < api_count:
                print(f"    [警告] 本地少了 {api_count - local_jpg_count} 张，可能有下载失败")
            elif local_jpg_count >= expected:
                print(f"    [OK] 数量一致")

            time.sleep(0.5)

        print("\n" + "=" * 60)
        print(f"[完成] 下载: {downloaded_count} 张, 失败: {failed_count} 张")
        print(f"[保存位置] {self.save_dir}")
        print("=" * 60)

    def _generate_filename(self, photo, index):
        """生成文件名，index为相册内全局序号，保证唯一"""
        base = ""

        name = photo.get("name", "")
        if name and name.strip():
            base = self._safe_filename(name)
            if base.lower().endswith(".jpg") or base.lower().endswith(".jpeg"):
                base = base[:base.rfind(".")]

        if not base:
            shoot_time = photo.get("shootTime", "")
            if shoot_time:
                try:
                    ts = int(shoot_time)
                    if ts > 0:
                        base = time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
                except (ValueError, OSError):
                    pass

        if not base:
            upload_time = photo.get("uploadTime", "")
            if upload_time:
                try:
                    ts = int(upload_time)
                    if ts > 0:
                        base = "upload_" + time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
                except (ValueError, OSError):
                    pass

        if not base:
            base = "photo"

        return f"{base}_{index:04d}.jpg"


def main():
    import locale
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    qq = QQ_NUMBER
    cookies = COOKIES_STR

    if "--interactive" in sys.argv:
        print("=" * 60)
        print("        QQ空间相册原图下载工具")
        print("=" * 60)
        print()
        qq = input("请输入你的QQ号: ").strip()
        print()
        cookies = input("请粘贴Cookie字符串: ").strip()
        print()
    elif len(sys.argv) >= 3:
        qq = sys.argv[1]
        cookies = sys.argv[2]
    elif len(sys.argv) == 2 and sys.argv[1] != "--interactive":
        qq = sys.argv[1]

    cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    if not cookies and os.path.exists(cookie_file):
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = f.read().strip()
        print("[提示] 从 cookies.txt 读取Cookie")

    downloader = QZoneDownloader(qq, cookies, SAVE_DIR)
    downloader.run()


if __name__ == "__main__":
    main()
