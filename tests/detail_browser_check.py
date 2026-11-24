"""Check readable detail sections, traceability, disclosure state and keyboard use."""
import argparse
import json

from playwright.sync_api import expect, sync_playwright
from detail_helpers import detail_tab, source_record


def run(url):
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.locator("#q").fill("00935301")
        expect(page.locator("#rows .journal-btn")).to_have_count(1, timeout=60000)
        page.locator("#rows .journal-btn").click()
        expect(page.locator("#detail")).to_be_visible()
        expect(page.locator("#detail-title")).to_have_text("Journal of Consumer Research")
        expect(page.locator('[data-detail-tab="overview"]')).to_have_attribute("aria-selected", "true")
        expect(page.locator("#detail-overview")).to_be_visible()
        expect(page.locator("#detail-classification")).not_to_be_visible()
        expect(page.locator("#detail-sources")).not_to_be_visible()
        expect(page.locator("#detail-overview .rating-card")).to_have_count(6)
        assert not page.locator("#detail-overview .raw:visible").count()
        data = page.evaluate("""async()=> {
          const r=await (await fetch('/api/journals?q=00935301')).json();
          return (await fetch('/api/journals/'+r.results[0].journal_id)).json();
        }""")
        assert page.locator(".observation").count() == len(data["observations"])
        assert page.locator(".source-group").count() == len({o["system"] for o in data["observations"]})
        checks.append("overview prioritises six indicators; separate tabs retain all source observations")

        page.locator('[data-detail-tab="overview"]').focus()
        page.keyboard.press("ArrowRight")
        expect(page.locator('[data-detail-tab="classification"]')).to_be_focused()
        expect(page.locator("#detail-classification")).to_be_visible()
        expect(page.locator(".classification-proof").first).not_to_have_attribute("open", "")
        page.locator(".classification-proof > summary").first.click()
        expect(page.locator(".taxonomy-evidence-table").first).to_be_visible()
        assert page.locator("#detail-body").evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        checks.append("keyboard tabs and collapsed classification evidence create a readable hierarchy")

        record = source_record(page, "ABDC", "2010")
        expect(record).to_have_attribute("open", "")
        assert record.locator(".detail-metrics").evaluate("node => [...node.children].every((item,index)=>item.tagName === (index % 2 ? 'DD' : 'DT'))")
        record.locator(".raw > summary").click()
        expect(record.locator(".raw pre")).to_be_visible()
        expected = next(o["raw"] for o in data["observations"] if o["system"] == "ABDC" and o["edition"].startswith("2010"))
        assert json.loads(record.locator(".raw pre").inner_text()) == expected
        checks.append("source/version disclosures preserve correctly structured metrics and exact original fields")

        page.evaluate("JournalI18n.setLocale('zh')")
        expect(page.locator('[data-detail-tab="sources"]')).to_have_attribute("aria-selected", "true")
        record = page.locator('.source-group[data-system="ABDC"] .observation[data-edition^="2010"]')
        expect(record.locator(".raw pre")).to_be_visible()
        assert record.evaluate("node => node.open")
        assert record.locator(".raw").evaluate("node => node.open")
        page.keyboard.press("Escape")
        expect(page.locator("#detail")).not_to_be_visible()
        checks.append("language changes preserve the current section, version and expanded original fields")

        page.locator("#rows .taxonomy-summary").click()
        expect(page.locator("#detail-classification")).to_be_visible()
        expect(page.locator('[data-detail-tab="classification"]')).to_have_attribute("aria-selected", "true")
        assert page.locator("#classification-evidence > h3").bounding_box()["y"] >= page.locator(".detail-tabs").bounding_box()["y"] + page.locator(".detail-tabs").bounding_box()["height"] - 1
        page.keyboard.press("Escape")
        page.locator("#rows .journal-btn").click()
        expect(page.locator("#detail-overview")).to_be_visible()
        page.locator('[data-detail-tab="overview"]').focus()
        page.keyboard.press("End")
        expect(page.locator('[data-detail-tab="sources"]')).to_be_focused()
        page.keyboard.press("Home")
        expect(page.locator('[data-detail-tab="overview"]')).to_be_focused()
        page.keyboard.press("Escape")
        checks.append("cached classification links open the right section; normal reopen resets to overview")

        for width in (390, 320):
            mobile = browser.new_page(viewport={"width": width, "height": 844})
            mobile.on("pageerror", lambda error: errors.append(str(error)))
            mobile.goto(url, wait_until="networkidle", timeout=60000)
            mobile.locator("#q").fill("03090566")
            expect(mobile.locator("#rows .journal-btn")).to_have_count(1, timeout=60000)
            mobile.locator("#rows .journal-btn").click()
            expect(mobile.locator("#detail-overview")).to_be_visible()
            rect = mobile.locator("#detail").bounding_box()
            assert rect["x"] >= 0 and rect["x"] + rect["width"] <= width + 1
            detail_tab(mobile, "classification")
            mobile.locator(".classification-proof > summary").first.click()
            assert mobile.locator("#detail-body").evaluate("node => node.scrollWidth <= node.clientWidth + 1")
            mobile.locator("#close-detail").click()
            expect(mobile.locator("#detail")).not_to_be_visible()
            mobile.close()
        checks.append("expanded evidence remains within 390px and 320px phone drawers")
        assert not errors, errors
        browser.close()
    return {"url": url, "checks": checks, "page_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18766/")
    print(json.dumps(run(parser.parse_args().url), ensure_ascii=False))
