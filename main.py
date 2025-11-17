import os
import time
import random
from playwright.sync_api import sync_playwright, Cookie, TimeoutError as PlaywrightTimeoutError

def add_server_time(server_url="https://game.wavehost.eu/server/667f11a7/"):
    """
    尝试登录 game.wavehost.eu 并点击 "DODAJ 6 GODZIN" 按钮。
    优先使用 REMEMBER_WEB_COOKIE 进行会话登录，如果不存在则回退到邮箱密码登录。
    增加了反 Cloudflare 机器人检测的尝试。
    """
    # 从环境变量获取登录凭据
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    pterodactyl_email = os.environ.get('PTERODACTYL_EMAIL')
    pterodactyl_password = os.environ.get('PTERODACTYL_PASSWORD')

    # 检查是否提供了任何登录凭据
    if not (remember_web_cookie or (pterodactyl_email and pterodactyl_password)):
        print("错误: 缺少登录凭据。")
        return False

    with sync_playwright() as p:
        # 尝试使用 Firefox，它在 headless 模式下有时比 Chromium 更不容易被检测
        browser = p.firefox.launch(headless=True)
        
        # 创建一个带有伪装的浏览器上下文
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        context = browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        page.set_default_timeout(90000)

        # 定义核心按钮选择器
        add_button_selector = 'button:has-text("DODAJ 6 GODZIN")'

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
                print(f"已设置 Cookie。正在访问目标服务器页面: {server_url}")
                page.goto(server_url, wait_until="domcontentloaded", timeout=90000)
                
                print("页面已导航，等待 10 秒，以便 Cloudflare (如果存在) 进行验证...")
                time.sleep(10)

                # 优化检查逻辑：不再检查 URL，而是直接看能不能找到目标按钮
                try:
                    print("检查 Cookie 登录是否成功（查找目标按钮）...")
                    page.wait_for_selector(add_button_selector, state='visible', timeout=15000)
                    print("Cookie 登录成功，已进入服务器页面。")
                except PlaywrightTimeoutError:
                    print("Cookie 登录失败、会话过期或被 Cloudflare 拦截。")
                    page.screenshot(path="cookie_login_fail_or_cf.png") # 截图以便调试
                    if "login" in page.url or "auth" in page.url:
                        print("已重定向到登录页，将回退到邮箱密码登录。")
                    else:
                        print("未重定向到登录页（可能是 Cloudflare），但仍将尝试邮箱密码登录。")
                    page.context.clear_cookies()
                    remember_web_cookie = None # 标记 Cookie 登录失败

            # --- 方案二：如果 Cookie 方案失败或未提供，则使用邮箱密码登录 ---
            if not remember_web_cookie:
                if not (pterodactyl_email and pterodactyl_password):
                    print("错误: Cookie 无效，且未提供 PTERODACTYL_EMAIL 或 PTERODACTYL_PASSWORD。无法登录。")
                    browser.close()
                    return False

                login_url = "https://game.wavehost.eu/auth/login"
                print(f"正在访问登录页面: {login_url}")
                page.goto(login_url, wait_until="domcontentloaded", timeout=90000)
                
                print("已导航到登录页，等待 10 秒，以便 Cloudflare (如果存在) 进行验证...")
                time.sleep(10)

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
                
                print("登录后导航完成，等待 10 秒...")
                time.sleep(10)

                if "login" in page.url or "auth" in page.url:
                    error_text = page.locator('.alert.alert-danger').inner_text().strip() if page.locator('.alert.alert-danger').count() > 0 else "未知错误，URL仍在登录页。"
                    print(f"邮箱密码登录失败: {error_text}")
                    page.screenshot(path="login_fail_error.png")
                    browser.close()
                    return False
                else:
                    print("邮箱密码登录成功。")

            # --- 确保当前位于正确的服务器页面 ---
            if page.url != server_url:
                print(f"当前不在目标服务器页面，正在导航至: {server_url}")
                page.goto(server_url, wait_until="domcontentloaded", timeout=90000)
                print("导航到服务器页面，等待 10 秒...")
                time.sleep(10)
                
                if "login" in page.url:
                    print("导航失败，会话可能已失效，需要重新登录。")
                    page.screenshot(path="server_page_nav_fail.png")
                    browser.close()
                    return False

            # --- 核心操作：查找并点击 "DODAJ 6 GODZIN" 按钮 ---
            print(f"正在查找并等待 '{add_button_selector}' 按钮...")
            try:
                add_button = page.locator(add_button_selector)
                add_button.wait_for(state='visible', timeout=30000)
                add_button.click()
                print("成功点击 'DODAJ 6 GODZIN' 按钮。")
                time.sleep(5)
                print("任务完成。")
                browser.close()
                return True
            except PlaywrightTimeoutError:
                print(f"错误: 在30秒内未找到或 'DODAJ 6 GODZIN' 按钮不可见/不可点击。")
                page.screenshot(path="add_button_not_found.png") # 最终找不到按钮时截图
                browser.close()
                return False

        except Exception as e:
            print(f"执行过程中发生未知错误: {e}")
            page.screenshot(path="general_error.png")
            browser.close()
            return False

if __name__ == "__main__":
    print("开始执行添加服务器时间任务...")
    success = add_server_time()
    if success:
        print("任务执行成功。")
        exit(0)
    else:
        print("任务执行失败。")
        exit(1)
