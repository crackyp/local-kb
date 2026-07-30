"""Take screenshots of every tab in the Local KB UI using headless Playwright."""
import time, os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("KB_BASE_URL", "http://127.0.0.1:3737")
OUT = "screenshots"

def main():
    os.makedirs(OUT, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Collect console/errors for debugging
        errors = []
        page.on("console", lambda msg: print(f"  CONSOLE: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(str(err)))

        # ── 1. Explorer (default, wiki tab) ──
        print("[1/8] Explorer (Wiki tab)...")
        page.goto(f"{BASE}", wait_until="commit", timeout=10000)
        # Wait for React to hydrate
        page.wait_for_timeout(4000)
        if errors:
            print(f"  PAGE ERRORS: {errors[:3]}")
        page.screenshot(path=f"{OUT}/01-explorer.png", full_page=False)

        # ── 2. Explorer with a file selected ──
        print("[2/8] Explorer (file selected)...")
        first_row = page.locator('[role="listbox"] [role="option"]').first
        if first_row.count() > 0:
            first_row.click()
            page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT}/02-explorer-file-selected.png", full_page=False)

        # ── 3. Chat ──
        print("[3/8] Chat tab...")
        nav = page.locator("nav button")
        nav.nth(1).click()  # Chat is 2nd nav item
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT}/03-chat.png", full_page=False)

        # ── 4. Ingest ──
        print("[4/8] Ingest tab...")
        nav.nth(2).click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT}/04-ingest.png", full_page=False)

        # ── 5. Compile ──
        print("[5/8] Compile tab...")
        nav.nth(3).click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT}/05-compile.png", full_page=False)

        # ── 6. Quality ──
        print("[6/8] Quality tab...")
        nav.nth(4).click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT}/06-quality.png", full_page=False)

        # ── 7. Sidebar collapsed ──
        print("[7/8] Sidebar collapsed...")
        # Expand sidebar first if collapsed
        expand_btn = page.locator("button[title='Expand sidebar']")
        if expand_btn.count() > 0:
            expand_btn.click()
            page.wait_for_timeout(500)
        # Now collapse it
        collapse_btn = page.locator("button[title='Collapse sidebar']")
        if collapse_btn.count() > 0:
            collapse_btn.click()
        else:
            # Fallback: click any button in the aside header
            page.locator("aside > div:first-child button").first.click()
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{OUT}/07-sidebar-collapsed.png", full_page=False)

        # ── 8. Explorer with Raw tab ──
        print("[8/8] Explorer (Raw tab)...")
        nav.nth(0).click()  # Explorer
        page.wait_for_timeout(1000)
        # Click the "Raw" sub-tab inside explorer
        raw_tab = page.locator("button:has-text('Raw')")
        if raw_tab.count() > 0:
            raw_tab.first.click()
            page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUT}/08-explorer-raw.png", full_page=False)

        print(f"\nDone! All screenshots in {os.path.abspath(OUT)}/")
        browser.close()

if __name__ == "__main__":
    main()
