from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    html_uri = Path("report/hub_v1.html").resolve().as_uri()
    out_dir = Path("report/qa")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Desktop: daily / compare / posts
        desktop = browser.new_page(viewport={"width": 1440, "height": 1200})
        desktop.goto(html_uri, wait_until="networkidle")
        desktop.wait_for_timeout(600)
        desktop.screenshot(path=str(out_dir / "hub_v1_daily_desktop.png"), full_page=True)

        desktop.click('button[data-view="compare"]')
        desktop.wait_for_timeout(300)
        desktop.screenshot(path=str(out_dir / "hub_v1_compare_desktop.png"), full_page=True)

        desktop.click('button[data-view="posts"]')
        desktop.wait_for_timeout(300)
        desktop.screenshot(path=str(out_dir / "hub_v1_posts_desktop.png"), full_page=True)

        desktop.click('button[data-view="longreads"]')
        desktop.wait_for_timeout(300)
        desktop.screenshot(path=str(out_dir / "hub_v1_longreads_desktop.png"), full_page=True)

        # Mobile: full-page may show chromium artifact on very long pages, keep viewport capture.
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(html_uri, wait_until="networkidle")
        mobile.wait_for_timeout(600)
        mobile.screenshot(path=str(out_dir / "hub_v1_daily_mobile.png"), full_page=False)

        mobile.click('button[data-view="posts"]')
        mobile.wait_for_timeout(500)
        mobile.screenshot(path=str(out_dir / "hub_v1_posts_mobile.png"), full_page=False)

        mobile.click('button[data-view="compare"]')
        mobile.wait_for_timeout(300)
        mobile.screenshot(path=str(out_dir / "hub_v1_compare_mobile.png"), full_page=False)

        mobile.click('button[data-view="longreads"]')
        mobile.wait_for_timeout(300)
        mobile.screenshot(path=str(out_dir / "hub_v1_longreads_mobile.png"), full_page=False)

        browser.close()

    print((out_dir / "hub_v1_daily_desktop.png").as_posix())
    print((out_dir / "hub_v1_compare_desktop.png").as_posix())
    print((out_dir / "hub_v1_posts_desktop.png").as_posix())
    print((out_dir / "hub_v1_longreads_desktop.png").as_posix())
    print((out_dir / "hub_v1_daily_mobile.png").as_posix())
    print((out_dir / "hub_v1_posts_mobile.png").as_posix())
    print((out_dir / "hub_v1_compare_mobile.png").as_posix())
    print((out_dir / "hub_v1_longreads_mobile.png").as_posix())


if __name__ == "__main__":
    main()
