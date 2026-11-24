"""Acceptance checks against a static HTTP host, including GitHub Pages."""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from detail_helpers import detail_tab, source_record

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(url):
    checks, errors, requests = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(request.url))
        page.goto(url, wait_until="networkidle", timeout=60000)
        expect(page.locator("#rows .journal-btn")).to_have_count(50, timeout=60000)
        total = page.evaluate("async()=> (await (await fetch('/api/meta')).json()).stats.journals")
        expect(page.locator("#statline")).to_contain_text(f"{total:,}")
        checks.append("static snapshot initial load")
        page.locator("#language").select_option("zh")
        expect(page.locator("html")).to_have_attribute("lang", "zh-CN")

        def api(params):
            return page.evaluate("""async params => {
              const response = await fetch('/api/journals?' + new URLSearchParams(params));
              return {status:response.status,body:await response.json()};
            }""", params)

        from journaldb.query import connect, search
        con = connect()
        try:
            for query, title in (("ejm", "EUROPEAN JOURNAL OF MARKETING"),
                                 ("EJM", "EUROPEAN JOURNAL OF MARKETING"),
                                 ("E.J.M.", "EUROPEAN JOURNAL OF MARKETING"),
                                 ("e j m", "EUROPEAN JOURNAL OF MARKETING"),
                                 ("jcr", "JOURNAL OF CONSUMER RESEARCH"),
                                 ("jmr", "JOURNAL OF MARKETING RESEARCH")):
                params = {"q": query, "limit": "500"}
                result = api(params)["body"]
                local = search(con, **params)
                assert title in {row["title"] for row in result["results"]}, query
                assert {row["journal_id"] for row in result["results"]} == {row["journal_id"] for row in local["results"]}, query
                assert result["total"] == local["total"], query
            filtered = api({"q": "ejm", "abdc": "A*"})["body"]
            assert "EUROPEAN JOURNAL OF MARKETING" in {row["title"] for row in filtered["results"]}
            assert all(row["abdc"] == "A*" for row in filtered["results"])
            page.locator("#q").fill("ejm")
            expect(page.locator("#rows .journal-btn").filter(has_text="EUROPEAN JOURNAL OF MARKETING")).to_be_visible()
            assert api({"q": "ejm"})["body"]["total"] > 1
            checks.append("acronym search, live EJM input, ambiguity, filters and CLI parity")
        finally:
            con.close()

        page.locator("#q").fill("Journal of Consumer Research")
        page.locator("#searchform button[type=submit]").click()
        expect(page.locator("#rows .journal-btn").first).to_have_text("Journal of Consumer Research")
        page.locator("#rows .journal-btn").first.click()
        expect(page.locator("#detail")).to_be_visible()
        source_record(page, "ABDC")
        expect(page.locator("#detail-body")).to_contain_text("2010 JQL", timeout=30000)
        expect(page.locator("#detail-body")).to_contain_text("Q1")
        expect(page.locator("#detail-body")).to_contain_text("查看原始字段")
        page.keyboard.press("Escape")
        checks.append("exact title, lazy detail, history and category quartiles")
        result = api({"q": "00935301"})
        assert result["status"] == 200 and result["body"]["total"] == 1
        assert result["body"]["results"][0]["title"] == "JOURNAL OF CONSUMER RESEARCH"
        checks.append("ISSN lookup")
        result = api({"q": "The Accounting Review"})
        assert result["body"]["results"][0]["title"] == "ACCOUNTING REVIEW"
        checks.append("normalized title lookup")
        result = api({"abdc": "A*", "ft50": "1", "utd24": "1"})
        assert result["body"]["total"] == 23
        assert all(r["ft50"] and r["utd24"] for r in result["body"]["results"])
        assert all(not r["ft50"] for r in api({"ft50": "0"})["body"]["results"])
        checks.append("combined and negative membership filters")
        wos = api({"wos_index": "SSCI", "limit": "500"})
        assert wos["status"] == 200 and wos["body"]["total"] > 3000
        assert all("SSCI" in record["wos_indexes"] for record in wos["body"]["results"])
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#wos_index").select_option("SSCI", force=True)
        expect(page.locator("#result-summary")).to_contain_text(f"共 {wos['body']['total']:,} 条")
        assert all("SSCI" in text for text in page.locator("#rows tr td:nth-child(5)").all_inner_texts())
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        checks.append("WoS index membership, real-time filter and visible index column")
        expect(page.locator('#cas option[value="1"]')).to_have_text("Q1")
        page.locator("#cas").select_option("1", force=True)
        cas = api({"cas": "1"})["body"]
        expect(page.locator("#result-summary")).to_contain_text(f"共 {cas['total']:,} 条")
        assert all(text.startswith("Q1") for text in page.locator("#rows tr td:nth-child(9)").all_inner_texts())
        page.locator("#rows .journal-btn").first.click()
        expect(page.locator("#detail-body .profile")).to_contain_text("Q1")
        page.keyboard.press("Escape")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        checks.append("CAS Q1–Q4 display maps to original numeric filter")
        assert api({"min_if": "NaN"})["status"] == 400
        assert api({"abdc": "D"})["status"] == 400
        assert api({"ft50": "2"})["status"] == 400
        checks.append("invalid parameter rejection")
        first = api({"sort": "impact_factor", "order": "desc", "limit": "5"})["body"]["results"]
        second = api({"sort": "impact_factor", "order": "desc", "limit": "5", "offset": "5"})["body"]["results"]
        assert first[0]["impact_factor"] == 685.2
        assert not ({r["journal_id"] for r in first} & {r["journal_id"] for r in second})
        checks.append("numeric ordering and pagination")
        # Capture the generated CSV in memory rather than saving a test artifact.
        page.evaluate("""() => {
          const native = URL.createObjectURL;
          URL.createObjectURL = blob => {window.exportedBlob=blob; return native(blob)};
          const click=HTMLAnchorElement.prototype.click;
          HTMLAnchorElement.prototype.click=function(){if(!this.download)return click.call(this)};
        }""")
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        page.locator("#ft50").check()
        expect(page.locator("#result-summary")).to_contain_text("共 50 条")
        page.locator("#export-link").click()
        page.wait_for_function("window.exportedBlob")
        csv_data = page.evaluate("async()=>await window.exportedBlob.text()")
        import csv, io
        reader = csv.DictReader(io.StringIO(csv_data.lstrip("\ufeff")))
        assert len(list(reader)) == 50
        assert {"journal_id", "abdc_year", "jcr_year", "quality_flags"} <= set(reader.fieldnames)
        assert "search_acronyms" not in reader.fieldnames
        checks.append("full filtered CSV with provenance fields")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
        checks.append("mobile width")
        assert not any("/api/" in request for request in requests), requests
        assert not errors, errors
        checks.append("no server API requests or JavaScript errors")
        browser.close()
    return {"url": url, "checks": checks, "page_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766/")
    args = parser.parse_args()
    print(json.dumps(run(args.url), ensure_ascii=False))
