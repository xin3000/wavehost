import os
import time
from playwright.sync_api import sync_playwright, Cookie, TimeoutError as PlaywrightTimeoutError
# 【【【 核心修正：使用与 v1.0.0+ 匹配的正确导入路径 】】】
from playwright_stealth.sync_api import stealth_sync 

# --- URL 和选择器定义 ---
BASE_URL = "https://game.wavehost.eu/"
LOGIN_URL = "https://game.wavehost.eu/auth/login"
SERVER_URL = "https://game.wavehost.eu/server/667f11a7/"
MANAGE_LINK_SELECTOR = f'a[href="/server/667f11a7/"]' 
ADD_BUTTON_SELECTOR = 'button:has-text("DODAJ 6 GODZIN")'

def add_server_time():
    """
    使用 playwright-stealth (已修正为最终正确的 import)
    """
    # 从环境变量获取登录凭据
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    pterodactyl_email = os.environ.get('PTERODACTYL_EMAIL')
    pterodactyl_password = os.environ.get('PTERODACTYL_PASSWORD')

    if not (remember_web_cookie or (pterodactyl_email and pterodactyl_password)):
        print("错误: 缺少登录凭据。")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        context = browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        print("正在对浏览器页面应用 'stealth' (隐身) 补丁...")
        # 【【【 核心修正：使用正确的函数名 】】】
        stealth_sync(page) 
        
        page.set_default_timeout(90000)
        logged_in = False
        wait_time = 10 

        try:
            # --- 方案一：优先尝试使用 Cookie 会话登录 ---
            if remember_web_cookie:
                print("检测到 REMEMBER_WEB_COOKIE，尝试使用 Cookie 登录...")
                session_cookie = {
                    'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    'value': remember_web_cookie,
                    'domain': 'game.wavehost.eu',
                    'path': '/',
                    'expires': int(time.time()) + 3600 * 24 * 365,
                    'httpOnly': True,
                    'secure': True,
                    'sameSite': 'Lax'
                }
                page.context.add_cookies([session_cookie])
                
                print(f"已设置 Cookie。正在访问【主页】: {BASE_URL}")
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90000)
                
                print(f"页面已导航，等待 {wait_time} 秒 (等待 stealth 生效)...")
                time.sleep(wait_time)

                try:
                    print(f"检查 Cookie 登录是否成功（查找管理链接: {MANAGE_LINK_SELECTOR}）...")
                    page.wait_for_selector(MANAGE_LINK_SELECTOR, state='visible', timeout=15000)
                    print("Cookie 登录成功，已加载主页。")
                    logged_in = True
                except PlaywrightTimeoutError:
                    print("Cookie 登录失败（未找到管理链接）或被 Cloudflare 拦截。")
                    page.screenshot(path="cookie_fail_or_cf.png")
                    page.context.clear_cookies()
                    remember_web_cookie = None 

            # --- 方案二：如果 Cookie 方案失败或未提供，则使用邮箱密码登录 ---
            if not logged_in:
                if not (pterodactyl_email and pterodactyl_password):
                    print("错误: Cookie 无效，且未提供 PTERODACTYL_EMAIL 或 PTERODACTYL_PASSWORD。无法登录。")
                    browser.close()
                    return False

                print(f"正在访问【登录页面】: {LOGIN_URL}")
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                
                print(f"已导航到登录页，等待 {wait_time} 秒...")
                time.sleep(wait_time)

                email_selector = 'input[name="username"]'
                password_selector = 'input[name="password"]'
                login_button_selector = 'button:has-text("Logowanie")'

                print("等待登录表单元素加载...")
                page.wait_for_selector(email_selector)
                page.wait_for_selector(password_selector)
                page.wait_for_selector(login_button_selector)

                print("正在填写邮箱和密码...")
                page.fill(email_selector, pterodactyl_email)
                page.fill(password_selector, pterodactyl_password)

                print("正在点击 'Logowanie' 登录按钮...")
                with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
                    page.click(login_button_selector)
                
                print(f"登录后导航完成，等待 {wait_time} 秒...")
                time.sleep(wait_time)

                if "login" in page.url or "auth" in page.url:
                    error_text = page.locator('.alert.alert-danger').inner_text().strip() if page.locator('.alert.alert-danger').count() > 0 else "未知错误"
                    print(f"邮箱密码登录失败: {error_text}")
                    page.screenshot(path="login_fail_error.png")
                    browser.close()
                    return False
                else:
                    print("邮箱密码登录成功。（当前应位于主页）")
                    logged_in = True
            
            # --- 导航步骤：从主页点击链接到服务器页面 ---
            
            print(f"确保当前在主页 ({BASE_URL}) ...")
            if BASE_URL not in page.url:
                print(f"警告：当前不在主页 (在 {page.url})，尝试强制导航到主页...")
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90000)
                print(f"强制导航到主页，等待 {wait_time} 秒...")
                time.sleep(wait_time) 

            print(f"正在查找服务器管理链接: {MANAGE_LINK_SELECTOR} ...")
            manage_link = page.locator(MANAGE_LINK_SELECTOR)
            manage_link.wait_for(state='visible', timeout=30000)
            
            print("找到链接，正在点击以导航到服务器页面...")
            with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
                manage_link.click()
            
            print(f"导航到服务器页面完成，等待 {wait_time} 秒...")
            time.sleep(wait_time)

            if page.url != SERVER_URL:
                print(f"错误: 点击链接后，意外地到达了 {page.url}")
                print(f"期望的 URL 是: {SERVER_URL}")
                page.screenshot(path="server_nav_fail.png")
                browser.close()
                return False

            print("成功导航到目标服务器页面。")

            # --- 核心操作：查找并点击 "DODAJ 6 GODZIN" 按钮 ---
            print(f"正在查找并等待 '{ADD_BUTTON_SELECTOR}' 按钮...")
            try:
                add_button = page.locator(ADD_BUTTON_SELECTOR)
                add_button.wait_for(state='visible', timeout=30000)
                add_button.click()
                print("成功点击 'DODAJ 6 GODZIN' 按钮。")
                time.sleep(5) 
                print("任务完成。")
                browser.close()
                return True
            except PlaywrightTimeoutError:
                print(f"错误: 在30秒内未找到或 'DODAJ 6 GODZIN' 按钮不可见/不可点击。")
                page.screenshot(path="add_button_not_found.png")
                browser.close()
                return False

        except Exception as e:
            print(f"执行过程中发生未知错误: {e}")
            page.screenshot(path="general_error.png")
            browser.close()
            return False

if __name__ == "__main__":
    print("开始执行添加服务器时间任务 (Stealth 模式 - 最终修正版)...")
    success = add_server_time()
    if success:
        print("任务执行成功。")
        exit(0)
    else:
        print("任务执行失败。")
        exit(1)
