"""Browser acceptance checks. Prints results; screenshots stay in memory only."""
import argparse
import base64
import csv
import io
import json
from urllib.request import urlopen
from urllib.error import HTTPError

from playwright.sync_api import sync_playwright, expect


def run(url="http://127.0.0.1:8765", include_image=False):
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle")
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        total = page.evaluate("async()=> (await (await fetch('/api/meta')).json()).stats.journals")
        expect(page.locator("#result-summary")).to_contain_text(f"{total:,}")
        page.locator("#language").select_option("zh")
        expect(page.locator("html")).to_have_attribute("lang", "zh-CN")
        checks.append("initial list and metadata")
        first_title = page.locator("#rows .journal-btn").first.inner_text()
        page.locator("#next").click()
        expect(page.locator("#page-label")).to_contain_text("第 2 页")
        assert page.locator("#rows .journal-btn").first.inner_text() != first_title
        checks.append("pagination")
        page.locator("#q").fill("Journal of Consumer Research")
        page.locator("#searchform button[type=submit]").click()
        expect(page.locator("#rows .journal-btn").first).to_have_text("Journal of Consumer Research")
        page.locator("#rows .journal-btn").first.click()
        expect(page.locator("#detail")).to_be_visible()
        expect(page.locator("#detail-title")).to_have_text("Journal of Consumer Research")
        expect(page.locator("#detail-body")).to_contain_text("2025 JQL")
        expect(page.locator("#detail-body")).to_contain_text("2010 JQL")
        expect(page.locator("#detail-body")).to_contain_text("Q1")
        page.locator("#detail-body .raw summary").first.click()
        assert page.locator("#detail-body .raw pre").first.is_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#detail")).not_to_be_visible()
        checks.append("detail, history, category quartile and raw fields")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#abdc").select_option("A*")
        page.locator("#ft50").check()
        page.locator("#utd24").check()
        expect(page.locator("#result-summary")).to_contain_text("共 23 条")
        export_url = url + page.locator("#export-link").get_attribute("href")
        with urlopen(export_url) as response:
            records = list(csv.DictReader(io.StringIO(response.read().decode("utf-8-sig"))))
        assert len(records) == 23
        assert all(row["abdc"] == "A*" for row in records)
        checks.append("combined filters and full CSV export")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#q").fill("00935301")
        page.locator("#searchform button[type=submit]").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        checks.append("unhyphenated ISSN search")
        page.locator("#q").fill("zzzz-no-such-journal-908173")
        page.locator("#searchform button[type=submit]").click()
        expect(page.locator("#rows")).to_contain_text("没有符合条件")
        expect(page.locator("#next")).to_be_disabled()
        checks.append("no results state")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#source_type").select_option("book series")
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        with urlopen(url + "/api/journals?source_type=book%20series&limit=1") as response:
            assert json.load(response)["results"][0]["source_type"] == "book series"
        checks.append("source type filter")
        try:
            urlopen(url + "/api/journals?min_if=NaN")
            raise AssertionError("invalid numeric value accepted")
        except HTTPError as exc:
            assert exc.code == 400
        checks.append("API validation")
        # Delay an earlier search to ensure it cannot overwrite a newer query.
        def delayed(route):
            import time
            time.sleep(0.25)
            route.continue_()
        page.route("**/api/journals?q=slow*", delayed)
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#q").fill("slow")
        page.locator("#searchform button[type=submit]").click()
        page.locator("#q").fill("00935301")
        page.locator("#searchform button[type=submit]").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        expect(page.locator("#rows .journal-btn").first).to_have_text("Journal of Consumer Research")
        checks.append("latest request wins")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.locator("#q").fill("00935301")
        page.locator("#searchform button[type=submit]").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        page.locator("#rows .journal-btn").click()
        expect(page.locator("#detail")).to_be_visible()
        page.keyboard.press("Escape")
        checks.append("mobile width and detail")
        page.set_viewport_size({"width": 1440, "height": 1050})
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#ft50").check()
        expect(page.locator("#result-summary")).to_contain_text("共 50 条")
        assert not errors, errors
        result = {"checks": checks, "page_errors": errors}
        if include_image:
            result["image"] = base64.b64encode(page.screenshot(type="png", full_page=False)).decode()
        browser.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--image", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.url, args.image), ensure_ascii=False))
