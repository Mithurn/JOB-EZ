"""
🕹️ BOT CONTROLLER
Handles all browser automation using Playwright.
Combines High-Stealth settings with Smart Form Filling logic.
"""

from playwright.sync_api import sync_playwright, BrowserContext, Page
from pathlib import Path
from typing import Optional, Dict
import time

# Import your configuration and utils
from src.config import CHROME_USER_DATA, DRY_RUN
from src.user_config import PROFILE, ANSWERS
from src.utils import (
    human_sleep, 
    human_type, 
    human_scroll, 
    human_click,
    human_mouse_move,
    simulate_reading_pattern
)

class JobBot:
    def __init__(self, headless: bool = False):
        """
        Initialize the bot with browser settings.
        """
        self.headless = headless
        self.profile_dir = Path(CHROME_USER_DATA)
        self.playwright = None
        self.browser: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        # Create profile dir if missing
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        print(f"🤖 Bot initialized (Headless: {headless})")

    def start_browser(self):
        """
        Launch the browser with MAXIMUM anti-detection settings.
        """
        print("🚀 Launching Stealth Browser...")
        self.playwright = sync_playwright().start()
        
        # 1. Launch with specific arguments to hide automation
        self.browser = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="chrome",       # Uses your real Chrome
            headless=self.headless,
            viewport={'width': 1920, 'height': 1080},
            args=[
                '--disable-blink-features=AutomationControlled', # CRITICAL: Hides "controlled by automated software"
                '--start-maximized',
                '--disable-infobars',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # 2. Get the page
        self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()

        # 3. Inject JavaScript to fake "navigator" properties (The Cloak)
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {} };
            human_sleep(0.7, 1.5)
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        
        print("✅ Stealth Browser Ready")

    def apply_to_job(self, job_url, resume_path):
        """
        The main logic loop to apply for a single job.
        """
        if not self.page:
            self.start_browser()

        print(f"\n🔗 Navigating to: {job_url}")
        try:
            self.page.goto(job_url, timeout=60000)
            human_sleep(3, 5) # Let page load

            # 1. Simulate Reading (Important for stealth)
            simulate_reading_pattern(self.page, "h1")
            # We look for multiple variations of the button
            apply_locators = [
                # Buttons
                "button.jobs-apply-button",
                "button[aria-label*='Easy Apply']",
                "button:has-text('Easy Apply')",
                # Links (new LinkedIn layout)
                "a[aria-label*='Easy Apply']",
                "a:has-text('Easy Apply')",
                "a[data-view-name='job-apply-button']",
                # Fallback: any element with Easy Apply text
                "*[aria-label*='Easy Apply']",
                "*:has-text('Easy Apply')"
            ]
            
            clicked = False
            for selector in apply_locators:
                try:
                    loc = self.page.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible():
                        print("👇 Clicking Easy Apply...")
                        human_click(self.page, selector)
                        clicked = True
                        break
                except Exception:
                    human_sleep(0.7, 1.5)

            if not clicked:
                print("⚠️ No 'Easy Apply' button found (Might be external or already applied). Skipping.")
                return "Skipped"

            human_sleep(2, 3)

            # 3. The Form Loop (Handle Popups)
            # We loop up to 10 times to handle multi-page forms (Contact -> Resume -> Review -> Submit)
            max_steps = 10
            for step in range(max_steps):
                print(f"   ➡️ Form Step {step + 1}")
                
                # A. Auto-Fill inputs
                self._fill_smart_fields()

                # B. Upload Resume if asked
                self._handle_upload(resume_path)

                # C. Check for SUBMIT
                submit_btn = self.page.locator("button[aria-label='Submit application']")
                if submit_btn.is_visible():
                    print("✅ Found Submit button!")
                    if not DRY_RUN:
                        try:
                            human_click(self.page, "button[aria-label='Submit application']")
                            human_sleep(3, 5) # Wait for submission
                            print("   ✅ Submit clicked")
                        except Exception as e:
                            print("   ❌ Submit click failed:", e)
                            return f"Failed (Submit error: {e})"
                    else:
                        print("   (DRY RUN: Submit skipped)")
                    return "Success"

                # D. Check for NEXT or REVIEW
                next_btn = self.page.locator("button[aria-label='Next']")
                review_btn = self.page.locator("button[aria-label='Review']")

                if next_btn.is_visible():
                    human_click(self.page, "button[aria-label='Next']")
                elif review_btn.is_visible():
                    human_click(self.page, "button[aria-label='Review']")
                else:
                    # Check for errors
                    if self.page.locator(".artdeco-inline-feedback__message").is_visible():
                        print("❌ Form Error: Missing required field.")
                        return "Failed (Form Error)"
                    
                    print("⚠️ Stuck: No Next/Submit button.")
                    return "Failed (Stuck)"
                
                human_sleep(2, 3)

                return "Failed (Too many steps)"
        except Exception as e:
            print(f"❌ Error applying: {e}")
            return f"Failed: {str(e)}"

    def _fill_smart_fields(self):
        """
        Scans the page for inputs and fills them using USER_CONFIG.
        """
        try:
            # 1. Text Inputs
            inputs = self.page.locator("input[type='text'], input[type='email'], input[type='tel']")
            count = inputs.count()
            
            for i in range(count):
                field = inputs.nth(i)
                if field.is_visible() and not field.get_attribute("value"):
                    label = self._get_label(field).lower()
                    
                    # Match logic
                    for key, value in PROFILE.items():
                        if key in label:
                            print(f"      ✍️ Filling {key}...")
                            field.fill(value)
                            human_sleep(0.5, 1)
                            break

            # 2. Radio Buttons (Yes/No)
            fieldsets = self.page.locator("fieldset")
            for i in range(fieldsets.count()):
                group = fieldsets.nth(i)
                text = group.text_content().lower()
                
                for question, answer in ANSWERS.items():
                    if question in text:
                        # Try to click the specific radio (label containing 'Yes' or 'No')
                        option = group.locator(f"label:has-text('{answer}')")
                        if option.is_visible():
                            option.click()
                            human_sleep(0.5, 1)

        except Exception:
            pass 

    def _get_label(self, element):
        """Helper to get label text for an input."""
        try:
            id_val = element.get_attribute("id")
            if id_val:
                return self.page.locator(f"label[for='{id_val}']").inner_text()
        except:
            return ""
        return ""

    def _handle_upload(self, resume_path):
        """Finds file inputs and uploads resume."""
        try:
            file_input = self.page.locator("input[type='file']")
            if file_input.is_visible():
                # Only upload if empty
                if not file_input.get_attribute("value"): 
                    print(f"      📎 Uploading resume...")
                    file_input.set_input_files(resume_path)
                    human_sleep(2, 4)
        except:
            pass

    def close(self):
        try:
            # close persistent context / browser
            if getattr(self, 'browser', None):
                try:
                    self.browser.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if getattr(self, 'playwright', None):
                try:
                    self.playwright.stop()
                except Exception:
                    pass
        except Exception:
            pass

# TEST
if __name__ == "__main__":
    bot = JobBot(headless=False)
    bot.start_browser()
    # bot.apply_to_job("https://linkedin.com/jobs/view/...", "data/resumes/frontend.pdf")