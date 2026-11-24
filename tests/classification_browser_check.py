"""Verify the unified hierarchy end to end; print findings without artifacts."""
import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from detail_helpers import detail_tab, source_record

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from journaldb.query import connect, search


def run(url):
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle", timeout=60000)
        expect(page.locator("#rows .journal-btn")).to_have_count(50, timeout=60000)
        page.wait_for_function("document.querySelector('#broad_area').options.length > 1")
        expect(page.locator("#classification_system")).to_have_count(0)
        expect(page.locator("#subcategory")).to_be_disabled()
        page.evaluate("""() => {
          const native = window.fetch;
          window.taxQueries = 0;
          window.fetch = (...args) => {
            if (String(args[0]).includes('/api/journals?')) window.taxQueries++;
            return native(...args);
          };
        }""")

        def api(params):
            return page.evaluate("""async params => {
              const r = await fetch('/api/journals?' + new URLSearchParams(params));
              return {status:r.status, body:await r.json()};
            }""", params)

        before = page.evaluate("taxQueries")
        page.locator("#broad_area").select_option("area-1400", force=True)
        expect(page.locator("#subcategory")).to_be_enabled()
        page.wait_for_function("taxQueries > " + str(before))
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        assert page.evaluate("taxQueries") == before + 1
        assert page.locator('#subcategory option[value="asjc-1406"]').count() == 1
        assert not page.locator('#subcategory option[value="asjc-2705"]').count()
        checks.append("single taxonomy; dependent broad/leaf controls and one live request")

        page.locator("#subcategory").select_option("asjc-1406", force=True)
        expect(page.locator("#export-link")).to_have_attribute("href", re.compile("subcategory=asjc-1406"))
        result = api({"broad_area": "area-1400", "subcategory": "asjc-1406", "limit": "500"})
        assert result["status"] == 200
        con = connect()
        try:
            local = search(con, broad_area="area-1400", subcategory="asjc-1406", limit=500)
            assert local["total"] == result["body"]["total"]
            assert {r["journal_id"] for r in local["results"]} == {r["journal_id"] for r in result["body"]["results"]}
        finally:
            con.close()
        assert all(any(path["broad_id"] == "area-1400" and path["subcategory_id"] == "asjc-1406" for path in row["taxonomy_paths"]) for row in result["body"]["results"])
        assert api({"broad_area": "area-1400", "subcategory": "asjc-2705"})["status"] == 400
        assert api({"subcategory": "unknown-category"})["status"] == 400
        checks.append("exact leaf filter, API/CLI parity, invalid IDs and mismatched branches")

        tops = page.evaluate("""() => ['#broad_area-trigger','#subcategory-trigger','#source_type-trigger','#min_if','.checkgrid','#clear'].map(selector => document.querySelector(selector).getBoundingClientRect().top)""")
        assert max(tops) - min(tops) <= 1, tops
        first_row = page.locator("#rows tr").first
        expect(first_row.locator(".taxonomy-name")).to_have_text("Marketing")
        expect(page.locator("#rows .taxonomy-context")).to_have_count(0)
        assert "Business" not in first_row.locator(".taxonomy-summary").inner_text()
        assert "›" not in first_row.locator(".taxonomy-summary").get_attribute("title")
        assert "Business, Management and Accounting" not in first_row.locator(".taxonomy-summary").get_attribute("title")
        assert first_row.bounding_box()["height"] <= 95
        assert first_row.locator(".taxonomy-summary").get_attribute("title").count("\n") >= 1
        first_row.locator(".taxonomy-summary").click()
        expect(page.locator("#classification-evidence")).to_contain_text("Marketing", timeout=30000)
        expect(page.locator("#classification-evidence")).to_contain_text("Strategy and Management")
        page.keyboard.press("Escape")
        checks.append("aligned filter controls; compact matched category opens every classification")

        page.locator("#q").fill("ejm")
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        expect(page.locator("#rows .journal-btn")).to_have_text("European Journal of Marketing")
        classification = page.locator("#rows tr td:last-child")
        expect(classification).to_contain_text("Marketing")
        assert "MKT" not in classification.inner_text()
        assert "BUSINESS; Business" not in classification.inner_text()
        row = api({"q": "0309-0566"})["body"]["results"][0]
        assert len([path for path in row["taxonomy_paths"] if path["broad_id"] == "area-1400"]) == 1
        path = next(path for path in row["taxonomy_paths"] if path["subcategory_id"] == "asjc-1406")
        assert {e["system"] for e in path["evidence"] if e["relation"] == "direct"} >= {"AJG", "SJR", "ABDC"}
        assert any(e["system"] == "JCR" and e["relation"] == "broader" for e in path["evidence"])
        checks.append("EJM merges Business/MKT/Marketing into one precise path with evidence")

        requests = page.evaluate("taxQueries")
        page.locator("#language").select_option("zh")
        expect(classification).to_contain_text("市场营销")
        expect(page.locator("#broad_area")).to_have_values(["area-1400"])
        expect(page.locator("#subcategory")).to_have_values(["asjc-1406"])
        assert page.evaluate("taxQueries") == requests
        page.locator("#rows .journal-btn").click()
        detail_tab(page, "classification")
        page.locator(".classification-proof > summary").first.click()
        expect(page.locator("#classification-evidence")).to_contain_text("MKT", timeout=30000)
        expect(page.locator("#classification-evidence")).to_contain_text("上级")
        expect(page.locator("#classification-evidence .taxonomy-method a")).to_have_count(4)
        expect(page.locator("#legacy-subjects")).not_to_have_attribute("open", "")
        page.keyboard.press("Escape")
        checks.append("locale preserves state without query; direct/broader evidence and auxiliary raw labels")

        page.evaluate("""() => {
          const native = URL.createObjectURL;
          URL.createObjectURL = blob => {window.exportedBlob=blob; return native(blob)};
          const click = HTMLAnchorElement.prototype.click;
          HTMLAnchorElement.prototype.click = function() {if (!this.download) return click.call(this)};
        }""")
        href = page.locator("#export-link").get_attribute("href")
        if page.evaluate("!!window.JOURNAL_STATIC"):
            page.locator("#export-link").click()
            page.wait_for_function("window.exportedBlob")
            text = page.evaluate("async()=>await window.exportedBlob.text()")
        else:
            text = page.evaluate("async href => (await fetch(href)).text()", href)
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        rows = list(reader)
        assert len(rows) == 1 and "Marketing" in rows[0]["classification"]
        assert "taxonomy_paths" not in reader.fieldnames
        checks.append("CSV exports the same filtered journal with readable unified classification")

        page.locator("#broad_area").select_option("area-2700", force=True)
        expect(page.locator("#subcategory")).to_have_values([])
        page.locator("#clear").click()
        expect(page.locator("#broad_area")).to_have_values([])
        expect(page.locator("#subcategory")).to_be_disabled()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#q").fill("00280836")
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        expect(page.locator("#rows .journal-btn")).to_have_text("Nature")
        expect(page.locator("#rows tr td:last-child")).to_have_text("—")
        page.locator("#rows .journal-btn").click()
        detail_tab(page, "classification")
        expect(page.locator("#classification-evidence")).to_contain_text(re.compile("Multidisciplinary|综合学科"), timeout=30000)
        page.keyboard.press("Escape")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        checks.append("broad-only classifications stay in details and never fill the subcategory column")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        checks.append("parent changes clear leaf; reset and mobile layout remain sound")
        browser.close()
    return {"url": url, "checks": checks, "page_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766/")
    print(json.dumps(run(parser.parse_args().url), ensure_ascii=False))
