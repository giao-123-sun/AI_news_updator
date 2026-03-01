from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    out_dir = Path("report/qa_ai_digest_clone")
    out_dir.mkdir(parents=True, exist_ok=True)

    index_uri = Path("report/ai_digest_clone/index.html").resolve().as_uri()
    archive_uri = Path("report/ai_digest_clone/archive.html").resolve().as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        desktop = browser.new_page(viewport={"width": 1440, "height": 2000})
        desktop.goto(index_uri, wait_until="networkidle")
        desktop.wait_for_timeout(500)
        desktop.screenshot(path=str(out_dir / "index_desktop.png"), full_page=True)

        desktop.goto(archive_uri, wait_until="networkidle")
        desktop.wait_for_timeout(500)
        desktop.screenshot(path=str(out_dir / "archive_desktop.png"), full_page=False)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(index_uri, wait_until="networkidle")
        mobile.wait_for_timeout(500)
        mobile.screenshot(path=str(out_dir / "index_mobile.png"), full_page=False)

        # Open first digest card if present
        first = mobile.query_selector(".article-card a.card-link")
        if first:
            first.click()
            mobile.wait_for_timeout(500)
            mobile.screenshot(path=str(out_dir / "digest_mobile.png"), full_page=False)

        browser.close()

    print((out_dir / "index_desktop.png").as_posix())
    print((out_dir / "archive_desktop.png").as_posix())
    print((out_dir / "index_mobile.png").as_posix())
    print((out_dir / "digest_mobile.png").as_posix())


if __name__ == "__main__":
    main()
