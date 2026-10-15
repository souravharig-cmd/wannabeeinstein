import os
import time
from playwright.sync_api import sync_playwright

def run_cuj(page):
    page.goto("http://localhost:5173")
    page.wait_for_timeout(1000)

    # Click Load Main Scenario Goal
    page.get_by_text("Load Main Scenario Goal").click()
    page.wait_for_timeout(500)

    # Click Initialize Task
    page.get_by_text("Initialize Task").click()
    page.wait_for_timeout(1500)

    # Click Run Workflow continuously until all steps are done or awaiting approval
    for _ in range(5):
        page.get_by_text("Run Workflow").click()
        page.wait_for_timeout(2000)
        
        # Approve if step 5 requires approval
        approve_btn = page.get_by_text("Approve & Execute")
        if approve_btn.is_visible():
            approve_btn.click()
            page.wait_for_timeout(2000)

    # Run verification checks
    page.get_by_text("Run Verification Checks").click()
    page.wait_for_timeout(1500)

    # Take final screenshot
    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos"
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()
            browser.close()
