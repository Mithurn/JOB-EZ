"""
🔵 LINKEDIN LOGIN SETUP
Run this once to save your session. 
"""

import time
from playwright.sync_api import sync_playwright
from pathlib import Path

# ---------------------------------------------------------
# ⚙️ CONFIGURATION
# ---------------------------------------------------------
PROFILE_DIR = "data/chrome_profile"  # Where cookies/session are saved

# REAL CHROME USER AGENT (Crucial to avoid "Headless" detection)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
# ---------------------------------------------------------

def run_login_setup():
    print("=" * 60)
    print("🔵 LINKEDIN SESSION SETUP")
    print("=" * 60)

    # 1. Create data directory if it doesn't exist
    data_path = Path(PROFILE_DIR)
    data_path.mkdir(parents=True, exist_ok=True)

    print(f"📂 Session storage: {data_path.absolute()}")
    print("🚀 Launching browser... (Please wait)")

    with sync_playwright() as p:
        # 2. Launch Persistent Context
        # This is the magic part: it loads/saves cookies to the PROFILE_DIR
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,  # Must be False to see the login screen
            viewport={'width': 1920, 'height': 1080},
            user_agent=USER_AGENT,  # <--- The Critical Fix
            args=['--disable-blink-features=AutomationControlled']
        )

        page = browser.pages[0] if browser.pages else browser.new_page()

        # 3. Go to LinkedIn Login
        print("\n🔗 Navigating to LinkedIn...")
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        print("\n" + "-" * 40)
        print("📝 ACTION REQUIRED:")
        print("   1. Enter your Email & Password in the browser window.")
        print("   2. Complete 2FA / Captcha if asked.")
        print("   3. Wait until you see your FEED (Home page).")
        print("-" * 40)
        print("⏳ Waiting for you to login successfully...")

        try:
            # 4. Wait for the URL to change to the feed
            # Timeout set to 5 minutes (300,000 ms) to give you plenty of time
            page.wait_for_url("**/feed/**", timeout=300000)
            
            print("\n✅ URL detected: linkedin.com/feed/")
            print("🎉 Login Detected! Saving session...")
            
            # Small wait to ensure cookies settle
            time.sleep(3) 
            
            # 5. Verification Check
            if page.locator(".global-nav__me-photo").count() > 0 or page.locator("nav").count() > 0:
                print("✅ Session Verified: Profile icon found.")
            
        except Exception as e:
            print(f"\n❌ Error or Timeout: {e}")
            print("Try running the script again.")

        finally:
            # 6. Close browser to flush cookies to disk
            print("💾 Closing browser and writing to disk...")
            browser.close()
            print("✨ DONE. You can now run your bot without logging in again.")

if __name__ == "__main__":
    run_login_setup()