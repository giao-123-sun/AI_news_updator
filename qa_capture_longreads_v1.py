import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def to_uri(path_str):
    path = Path(path_str)
    if not path.is_absolute() and not path.exists():
        alt = Path("report") / path
        if alt.exists():
            path = alt
    return path.resolve().as_uri()


def pick_article():
    manifest = Path("report/longreads/manifest.json")
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            articles = data.get("articles", [])
            if articles:
                return articles[0]
        except Exception:
            pass
    files = sorted(Path("report/longreads/articles").glob("*.html"))
    if files:
        return files[-1].as_posix()
    return None


def main():
    out = Path("report/qa_longreads")
    out.mkdir(parents=True, exist_ok=True)

    index_uri = to_uri("report/longreads/index.html")
    facts_uri = to_uri("report/longreads/facts_all_events.html")
    history_uri = to_uri("report/longreads/brief_history.html")
    article_path = pick_article()
    article_uri = to_uri(article_path) if article_path else None

    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        desktop = browser.new_page(viewport={"width": 1440, "height": 1200})
        desktop.goto(index_uri, wait_until="networkidle")
        desktop.wait_for_timeout(600)
        path = out / "longreads_index_desktop.png"
        desktop.screenshot(path=str(path), full_page=True)
        shots.append(path)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(index_uri, wait_until="networkidle")
        mobile.wait_for_timeout(600)
        path = out / "longreads_index_mobile.png"
        mobile.screenshot(path=str(path), full_page=False)
        shots.append(path)

        facts = browser.new_page(viewport={"width": 1440, "height": 900})
        facts.goto(facts_uri, wait_until="networkidle")
        facts.wait_for_timeout(600)
        path = out / "facts_events_desktop.png"
        facts.screenshot(path=str(path), full_page=False)
        shots.append(path)

        history = browser.new_page(viewport={"width": 1440, "height": 900})
        history.goto(history_uri, wait_until="networkidle")
        history.wait_for_timeout(600)
        path = out / "history_desktop.png"
        history.screenshot(path=str(path), full_page=False)
        shots.append(path)

        if article_uri:
            art_d = browser.new_page(viewport={"width": 1440, "height": 1600})
            art_d.goto(article_uri, wait_until="networkidle")
            art_d.wait_for_timeout(600)
            path = out / "article_desktop.png"
            art_d.screenshot(path=str(path), full_page=False)
            shots.append(path)

            art_m = browser.new_page(viewport={"width": 390, "height": 844})
            art_m.goto(article_uri, wait_until="networkidle")
            art_m.wait_for_timeout(600)
            path = out / "article_mobile.png"
            art_m.screenshot(path=str(path), full_page=False)
            shots.append(path)

        browser.close()

    for p in shots:
        print(p.as_posix())


if __name__ == "__main__":
    main()
