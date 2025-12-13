"""
Main entrypoint for SMART APPLY BOT.
This file adapts to the existing src/* implementations and uses safe fallbacks.
"""
import sys
import time
import random
from typing import List, Dict, Optional

# Try to import config values if present (use safe defaults)
try:
    from src.config import (
        DRY_RUN,
        HEADLESS_MODE,
        MAX_APPLICATIONS_PER_DAY,
        SEARCH_QUERIES,
        PREFERRED_LOCATIONS,
    )
except Exception:
    DRY_RUN = False
    HEADLESS_MODE = True
    MAX_APPLICATIONS_PER_DAY = 20
    SEARCH_QUERIES = [ "Full Stack Intern,Frontend Intern,Web Developer Intern,React Developer Intern,Node.js Intern"]
    PREFERRED_LOCATIONS = ["India"]

# Flexible imports for bot / user config / components
try:
    # prefer JobBot if available
    from src.bot import JobBot as _BotClass
except Exception:
    try:
        from src.bot import SmartApplyBot as _BotClass
    except Exception:
        _BotClass = None

# user config variations
try:
    from src.user_config import PERSONAL_INFO, validate_user_config
except Exception:
    try:
        from src.user_config import PROFILE as PERSONAL_INFO  # fallback shape may differ
        validate_user_config = lambda: True
    except Exception:
        PERSONAL_INFO = {"phone": ""}
        validate_user_config = lambda: True

# other components
from src.resume_manager import ResumeManager
from src.llm_engine import LLMEngine
from src.logger import JobLogger
from src.utils import human_sleep


def choose_resume(llm: Optional[LLMEngine], resumes: ResumeManager, description: str, title: str):
    """Return selected_resume_name, match_score, confidence"""
    # If only one resume is available, always use it (simple & deterministic)
    try:
        available = resumes.list_available_resumes()
        if available and len(available) == 1:
            return available[0], 0, 1.0
    except Exception:
        pass
    try:
        if llm and hasattr(llm, "select_best_resume"):
            all_res = resumes.get_all_resumes() if hasattr(resumes, "get_all_resumes") else resumes.list_available_resumes()
            match = llm.select_best_resume(job_description=description or title, resumes=all_res, job_title=title)
            return match.get("selected_resume") or match.get("selected_resume_name"), match.get("match_score", 0), match.get("confidence", 0.0)
    except Exception:
        pass

    # fallback: pick first available resume
    try:
        list_res = resumes.list_available_resumes()
    except Exception:
        list_res = []
    if not list_res:
        try:
            all_res = resumes.get_all_resumes()
            list_res = [r for r in all_res]
        except Exception:
            list_res = []
    selected = list_res[0] if list_res else None
    return selected, 0, 0.0


def apply_with_bot(bot, url: str, resume_path: str):
    """
    Try common apply API names on bot: apply_to_job, apply_to_linkedin_job, apply.
    If none exist, open page and try a minimal 'click Easy Apply' flow using page.
    Returns result string or boolean.
    """
    try:
        if hasattr(bot, "apply_to_job"):
            return bot.apply_to_job(url, resume_path)
        if hasattr(bot, "apply_to_linkedin_job"):
            # expects job_data sometimes; create minimal job dict
            job = {"url": url, "description": ""}
            return bot.apply_to_linkedin_job(job, resume_path)
        if hasattr(bot, "apply"):
            return bot.apply(url, resume_path)
    except Exception as e:
        print("⚠️ Bot apply method raised:", e)

    # Last resort: open URL and attempt to click Easy Apply using page API
    try:
        page = getattr(bot, "page", None)
        if page is None:
            return False
        page.goto(url, timeout=60000)
        human_sleep(1, 2)
        # try a few selectors
        easy_selectors = [
            'button.jobs-apply-button',
            'button[aria-label*="Easy Apply"]',
            'button:has-text("Easy Apply")'
        ]
        for sel in easy_selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click()
                    human_sleep(0.3, 0.6)
                    # attempt upload if file input present and bot has upload helper
                    if hasattr(bot, "upload_file"):
                        try:
                            file_in = page.locator('input[type="file"]')
                            if file_in.count() > 0:
                                bot.upload_file('input[type="file"]', resume_path)
                                human_sleep(0.5, 1)
                        except Exception:
                            pass
                    # try to submit
                    submit_sel = ['button:has-text("Submit")', 'button[aria-label="Submit application"]']
                    for s in submit_sel:
                        try:
                            s_loc = page.locator(s)
                            if s_loc.count() > 0:
                                s_loc.first.click()
                                human_sleep(0.5, 1)
                                return True
                        except Exception:
                            continue
                    return True
            except Exception:
                continue
    except Exception as e:
        print("⚠️ Fallback apply flow failed:", e)
    return False


def scrape_job_urls_with_bot(bot, keyword: str = "Python Developer", max_urls: int = 50) -> List[str]:
    """Lightweight job URL scraper using bot.page. Returns unique URLs.

    This version navigates directly to the LinkedIn search URL (more reliable),
    collects links using several common selectors, and saves an HTML snapshot
    for diagnostics when no jobs are found.
    """
    from urllib.parse import quote_plus

    page = getattr(bot, "page", None)
    if page is None:
        return []

    try:
        # Build a direct search URL with Easy Apply filter enabled
        q = quote_plus(keyword)
        loc = quote_plus(keyword if not PREFERRED_LOCATIONS else PREFERRED_LOCATIONS[0])
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}&f_AL=true"
        page.goto(search_url, wait_until="domcontentloaded")
        human_sleep(1, 2)

        # Scroll to load more results
        for _ in range(4):
            try:
                page.evaluate("window.scrollBy(0, window.innerHeight);")
            except Exception:
                pass
            human_sleep(0.5, 1)

        # Try several link selectors to be robust against DOM changes
        candidate_selectors = [
            "a.job-card-container__link",
            "a.base-card__full-link",
            "a.result-card__full-card-link",
            "a[href*='/jobs/view/']",
        ]

        urls = []
        for sel in candidate_selectors:
            try:
                elems = page.locator(sel).all()
            except Exception:
                elems = []
            for el in elems:
                try:
                    href = el.get_attribute("href")
                    if not href:
                        continue
                    clean = href.split("?")[0]
                    if not clean.startswith("http"):
                        clean = f"https://www.linkedin.com{clean}"
                    urls.append(clean)
                    if len(urls) >= max_urls:
                        break
                except Exception:
                    continue
            if len(urls) >= max_urls:
                break

        # Unique preserve order
        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
            if len(unique) >= max_urls:
                break

        if not unique:
            # Save diagnostic HTML snapshot for inspection
            try:
                ts = int(time.time())
                html_path = f"data/logs/no_jobs_{ts}.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"📄 Saved page HTML for inspection: {html_path}")
            except Exception:
                pass

        return unique
    except Exception:
        return []


def main(max_jobs: int = 10):
    print("\n" + "=" * 60)
    print("🤖 SMART APPLY - MAIN")
    print("=" * 60)

    # quick validations
    if not validate_user_config():
        print("❌ user_config validation failed.")
        sys.exit(1)

    if _BotClass is None:
        print("❌ No usable bot class found in src.bot. Inspect src/bot.py")
        sys.exit(1)

    # initialize components
    resumes = ResumeManager()
    try:
        llm = LLMEngine()
    except Exception as e:
        print("⚠️ LLMEngine init failed:", e)
        llm = None
    logger = JobLogger()

    bot = None
    try:
        bot = _BotClass(headless=HEADLESS_MODE)
        # try common launch names
        if hasattr(bot, "start_browser"):
            bot.start_browser()
        elif hasattr(bot, "launch"):
            bot.launch()
        elif hasattr(bot, "open"):
            bot.open()
        # small pause for browser readiness
            human_sleep(0.5, 1)
    except Exception as e:
        print("❌ Failed to start bot:", e)
        if bot:
            try:
                bot.close()
            except Exception:
                pass
        sys.exit(1)

    try:
        # choose search query & location
        keyword = SEARCH_QUERIES[0] if SEARCH_QUERIES else "Python Developer"
        location = PREFERRED_LOCATIONS[0] if PREFERRED_LOCATIONS else "India"

        print(f"\n🔍 Scraping jobs for: {keyword} in {location}")
        job_urls = scrape_job_urls_with_bot(bot, keyword=keyword, max_urls=max_jobs)
        # If no job URLs found, allow a manual retry when running headful so you can login/inspect
        if not job_urls:
            print("❌ No job URLs found.")
            if not HEADLESS_MODE:
                # Save a screenshot for debugging (best-effort)
                try:
                    page = getattr(bot, "page", None)
                    if page:
                        ts = int(time.time())
                        path = f"data/logs/no_jobs_{ts}.png"
                        try:
                            page.screenshot(path=path, full_page=True)
                            print(f"📸 Saved screenshot for inspection: {path}")
                        except Exception:
                            pass
                except Exception:
                    pass

                # Interactive retry loop: let user log in manually then press 'r' to retry or Enter to exit
                try:
                    resp = input("No jobs found — log in if needed. Type 'r' then Enter to retry scraping, or just press Enter to exit: ")
                    if resp.strip().lower() == 'r':
                        print("🔁 Retrying scrape after manual action...")
                        job_urls = scrape_job_urls_with_bot(bot, keyword=keyword, max_urls=max_jobs)
                        if not job_urls:
                            print("❌ Still no job URLs found after retry. Exiting.")
                            return
                    else:
                        print("Exiting.")
                        return
                except KeyboardInterrupt:
                    print("\nInterrupted. Exiting.")
                    return
            else:
                print("Exiting (headless mode).")
                return

        print(f"📋 Found {len(job_urls)} jobs (processing up to {max_jobs})")

        applied_count = 0
        for idx, url in enumerate(job_urls[:max_jobs], start=1):
            print("\n" + "-" * 60)
            print(f"📍 Job {idx}/{min(len(job_urls), max_jobs)}")
            print(url)
            # load job page & try to extract useful info
            page = getattr(bot, "page", None)
            title = "Unknown"
            company = "Unknown"
            description = ""
            if page is not None:
                try:
                    page.goto(url, timeout=60000)
                    human_sleep(1, 2)
                    
                    # Try multiple selectors for title/company/description to avoid 'Unknown'
                    t_selectors = [
                        ".job-details-jobs-unified-top-card__job-title h1 a",  # Specific: h1 > a inside job title div
                        "h1.t-24.t-bold a",  # Class-based match for h1 > a
                        ".job-details-jobs-unified-top-card__job-title h1",  # Fallback: just the h1
                        "h1",  # Any h1 tag (usually job title)
                        ".topcard__title",
                        "h1.top-card-layout__title",
                    ]
                    c_selectors = [
                        ".job-details-jobs-unified-top-card__company-name a",  # Specific: a inside company name div
                        "div.job-details-jobs-unified-top-card__company-name a",  # More specific version
                        ".topcard__org-name-link",
                        "a[data-tracking-control-name='public_jobs_topcard-org-name']",
                        "a[href*='/company/']",  # Any company link
                    ]
                    d_selectors = [
                        ".jobs-description__content",
                        ".jobs-description-content__text",
                        "div.jobs-description",
                        "article.jobs-description",
                        ".description__text",
                        ".description",
                    ]

                    for sel in t_selectors:
                        try:
                            loc = page.locator(sel)
                            if loc.count() > 0:
                                text = loc.first.inner_text().strip()
                                if text:  # Only accept non-empty text
                                    title = text
                                    print(f"✓ Title found with selector: {sel[:50]}")
                                    break
                        except Exception:
                            continue
                    
                    if title == "Unknown":
                        print("⚠️ Could not extract job title - will try all selectors on next run")

                    for sel in c_selectors:
                        try:
                            loc = page.locator(sel)
                            if loc.count() > 0:
                                text = loc.first.inner_text().strip()
                                if text:  # Only accept non-empty text
                                    company = text
                                    print(f"✓ Company found with selector: {sel[:50]}")
                                    break
                        except Exception:
                            continue

                    for sel in d_selectors:
                        try:
                            loc = page.locator(sel)
                            if loc.count() > 0:
                                description = loc.first.inner_text().strip()
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print("⚠️ Could not load/extract page:", e)

            selected_resume, score, confidence = choose_resume(llm, resumes, description, title)
            if not selected_resume:
                print("❌ No resume available. Skipping job.")
                continue

            resume_path = resumes.get_resume_path(selected_resume)
            if not resume_path:
                print(f"❌ Resume path missing for {selected_resume}. Skipping.")
                continue

            if DRY_RUN:
                print("🧪 DRY RUN - not actually applying. Logging only.")
                result = "DRY_RUN"
                success = True
            else:
                print("📝 Applying...")
                result = apply_with_bot(bot, url, resume_path)
                # Check if actually succeeded (not just returned a string)
                success = result == "Success" if isinstance(result, str) else bool(result)

            # Determine status from result
            if success:
                status = "Success"
            elif result == "Skipped" or "Skipped" in str(result):
                status = "Skipped"
            else:
                status = "Failed"
                
            logger.log_application(
                job_title=title,
                company=company,
                platform="LinkedIn",
                resume_used=selected_resume,
                match_score=score,
                confidence=confidence,
                status=status,
                location=location,
                application_url=url,
                notes=str(result)[:1000] if result else ""
            )

            if success:
                applied_count += 1

            # polite pause & stop if reached daily cap
                human_sleep(0.3, 0.6)
            try:
                today_count = logger.get_today_count()
                if today_count >= MAX_APPLICATIONS_PER_DAY:
                    print(f"\n🛑 Reached daily cap ({today_count}/{MAX_APPLICATIONS_PER_DAY}). Stopping.")
                    break
            except Exception:
                pass

        print("\n" + "=" * 60)
        print(f"Session applied count: {applied_count}")
        stats = logger.get_statistics()
        print("Logger stats:", stats)

    except KeyboardInterrupt:
        print("⚠️ Interrupted by user.")
    except Exception as e:
        print("❌ Fatal error in main loop:", e)
    finally:
        try:
            if bot:
                if hasattr(bot, "close"):
                    bot.close()
                elif hasattr(bot, "stop_browser"):
                    bot.stop_browser()
        except Exception:
            pass
        try:
            logger.close()
        except Exception:
            pass

    print("✅ Done. Check data/job_tracker.xlsx or logs for details.")


if __name__ == "__main__":
    main(max_jobs=10)