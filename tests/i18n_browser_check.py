"""Verify default language, user switching, persistence and responsive UI."""
import argparse
import json
import re

from playwright.sync_api import sync_playwright, expect
from detail_helpers import detail_tab, source_record


def run(url):
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle", timeout=60000)
        expect(page.locator("#rows .journal-btn")).to_have_count(50, timeout=60000)
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#language")).to_have_value("en")
        assert not re.search(r"[\u4e00-\u9fff]", page.locator("#searchform").inner_text())
        assert page.locator("#q").bounding_box()["y"] < 250
        assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(255, 255, 255)"
        checks.append("first visit defaults to English; search is prominent")

        response = page.evaluate("""async()=>{
            const r=await fetch('/api/journals?min_if=NaN');
            return {status:r.status,body:await r.json()};
        }""")
        assert response["status"] == 400
        assert not re.search(r"[\u4e00-\u9fff]", response["body"]["error"])
        checks.append("English validation messages")
        expect(page.locator("#apply")).to_have_count(0)
        page.locator("#q").fill("00935301")
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        expect(page.locator("#rows .journal-btn").first).to_have_text("Journal of Consumer Research")
        page.locator("#q").fill("")
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#min_if").fill("600")
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        expect(page.locator("#rows .journal-btn").first).to_have_text("CA-A Cancer Journal for Clinicians")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        checks.append("search and numeric filters update without Apply or Enter")

        def aligned(target):
            return target.evaluate("""() => ['ft50','utd24'].every(id => {
              const input=document.getElementById(id),label=input.closest('label');
              const text=[...label.childNodes].find(n=>n.nodeType===3 && n.textContent.trim());
              const range=document.createRange();range.selectNode(text);
              const a=input.getBoundingClientRect(),b=range.getBoundingClientRect();
              return Math.abs((a.top+a.height/2)-(b.top+b.height/2))<2;
            })""")
        assert aligned(page)
        checks.append("list checkboxes align with their labels")

        page.locator("#q").fill("Journal of Consumer Research")
        page.locator("#searchform button[type=submit]").click()
        expect(page.locator("#rows .journal-btn").first).to_have_text("Journal of Consumer Research")
        page.locator("#abdc").select_option("A*")
        expect(page.locator("#rows .journal-btn").first).to_have_text("Journal of Consumer Research")
        count = page.locator("#rows .journal-btn").count()
        page.locator("#language").select_option("zh")
        expect(page.locator("html")).to_have_attribute("lang", "zh-CN")
        expect(page.locator("#searchform button[type=submit]")).to_have_text(re.compile("检索|搜索"))
        expect(page.locator("#q")).to_have_value("Journal of Consumer Research")
        expect(page.locator("#abdc")).to_have_value("A*")
        expect(page.locator("#rows .journal-btn")).to_have_count(count)
        checks.append("visible language switch preserves query, filters and results")

        page.locator("#rows .journal-btn").first.click()
        expect(page.locator("#detail")).to_be_visible()
        source_record(page, "ABDC")
        expect(page.locator("#detail-body")).to_contain_text("2010 JQL", timeout=30000)
        expect(page.locator("#detail-body")).to_contain_text("查看原始字段")
        page.evaluate("window.JournalI18n.setLocale('en')")
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#detail-body .raw summary").first).not_to_have_text("查看原始字段")
        expect(page.locator("#detail-body")).to_contain_text("2010 JQL")
        expect(page.locator("#detail-title")).to_have_text("Journal of Consumer Research")
        page.keyboard.press("Escape")
        checks.append("open details change language; original titles and sources remain")

        page.locator("#language").select_option("zh")
        page.reload(wait_until="networkidle")
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        expect(page.locator("html")).to_have_attribute("lang", "zh-CN")
        expect(page.locator("#language")).to_have_value("zh")
        checks.append("selected language persists after reload")
        page.locator("#next").click()
        expect(page.locator("#page-label")).to_contain_text("第 2 页")
        first_title = page.locator("#rows .journal-btn").first.inner_text()
        page.locator("#language").select_option("en")
        expect(page.locator("#page-label")).to_contain_text("Page 2")
        expect(page.locator("#rows .journal-btn").first).to_have_text(first_title)
        checks.append("language switch preserves the current results page")

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(url, wait_until="networkidle", timeout=60000)
        expect(mobile.locator("#rows .journal-btn")).to_have_count(50, timeout=60000)
        expect(mobile.locator("html")).to_have_attribute("lang", "en")
        assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert mobile.locator("#q").is_visible()
        assert mobile.locator("#q").bounding_box()["y"] < 300
        expect(mobile.locator("#filter-panel")).not_to_have_attribute("open", "")
        mobile.locator("#filter-panel > summary").click()
        expect(mobile.locator("#abdc")).to_be_visible()
        assert aligned(mobile)
        mobile.locator("#language").select_option("zh")
        expect(mobile.locator("html")).to_have_attribute("lang", "zh-CN")
        assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
        checks.append("mobile search, collapsible filters and language switch")
        assert not errors, errors
        browser.close()
    return {"url": url, "checks": checks, "page_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766/")
    args = parser.parse_args()
    print(json.dumps(run(args.url), ensure_ascii=False))
