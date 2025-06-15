import configparser
import json
import pathlib
import os
from time import sleep

import requests
from playwright.sync_api import sync_playwright

from conf import BASE_DIR, XHS_SERVER

config = configparser.RawConfigParser()
config.read('accounts.ini')


def sign_local(uri, data=None, a1="", web_session=""):
    for retry_count in range(10):
        try:
            with sync_playwright() as playwright:
                stealth_js_path = pathlib.Path(BASE_DIR / "utils/stealth.min.js")
                chromium = playwright.chromium

                # Docker 环境兼容的浏览器启动参数
                launch_args = [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',
                    '--disable-javascript-harmony-shipping',
                    '--disable-ipc-flooding-protection',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-client-side-phishing-detection',
                    '--disable-sync',
                    '--disable-translate',
                    '--disable-default-apps',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--memory-pressure-off',
                    '--max_old_space_size=4096',
                    '--single-process'
                ]

                # 检测是否在 Docker 环境中运行
                is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_ENV') == '1'
                
                browser = chromium.launch(
                    headless=True,
                    args=launch_args if is_docker else ['--no-sandbox', '--disable-dev-shm-usage']
                )

                browser_context = browser.new_context(
                    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                
                # 检查 stealth.min.js 文件是否存在
                if stealth_js_path.exists():
                    browser_context.add_init_script(path=stealth_js_path)
                else:
                    print(f"Warning: stealth.min.js not found at {stealth_js_path}")
                
                context_page = browser_context.new_page()
                
                # 设置超时
                context_page.set_default_timeout(30000)  # 30秒超时
                
                try:
                    context_page.goto("https://www.xiaohongshu.com", wait_until='networkidle')
                except Exception as e:
                    print(f"Page load warning (retry {retry_count + 1}): {e}")
                    context_page.goto("https://www.xiaohongshu.com")
                
                browser_context.add_cookies([
                    {'name': 'a1', 'value': a1, 'domain': ".xiaohongshu.com", 'path': "/"}]
                )
                context_page.reload(wait_until='networkidle')
                
                # 增加等待时间，确保页面完全加载
                sleep(3 if is_docker else 2)
                
                # 检查签名函数是否存在
                try:
                    sign_function_exists = context_page.evaluate("typeof window._webmsxyw === 'function'")
                    if not sign_function_exists:
                        print(f"Warning: window._webmsxyw not found (retry {retry_count + 1})")
                        browser.close()
                        sleep(1)
                        continue
                except Exception as e:
                    print(f"Error checking sign function (retry {retry_count + 1}): {e}")
                    browser.close()
                    sleep(1)
                    continue
                
                encrypt_params = context_page.evaluate("([url, data]) => window._webmsxyw(url, data)", [uri, data])
                browser.close()
                
                return {
                    "x-s": encrypt_params["X-s"],
                    "x-t": str(encrypt_params["X-t"])
                }
                
        except Exception as e:
            print(f"Sign attempt {retry_count + 1} failed: {e}")
            # 这儿有时会出现 window._webmsxyw is not a function 或未知跳转错误，因此加一个失败重试趴
            if retry_count < 9:  # 不是最后一次重试
                sleep(1 + retry_count * 0.5)  # 递增延迟
            pass
    raise Exception("重试了这么多次还是无法签名成功，寄寄寄")


def sign(uri, data=None, a1="", web_session=""):
    # 填写自己的 flask 签名服务端口地址
    res = requests.post(f"{XHS_SERVER}/sign",
                        json={"uri": uri, "data": data, "a1": a1, "web_session": web_session})
    signs = res.json()
    return {
        "x-s": signs["x-s"],
        "x-t": signs["x-t"]
    }


def beauty_print(data: dict):
    print(json.dumps(data, ensure_ascii=False, indent=2))
