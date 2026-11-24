"""Exercise real multi-select controls and parity with the read-only query layer."""
import argparse
import csv
import io
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from journaldb.query import connect, search, selection


def run(url):
    checks, errors = [], []
    con = connect()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle", timeout=60000)
        expect(page.locator("#rows .journal-btn")).to_have_count(50, timeout=60000)
        page.wait_for_function("document.querySelector('#broad_area').options.length > 1")
        page.evaluate("""() => {
          const original=fetch; window.filterCalls=0;
          window.fetch=(...args)=>{if(String(args[0]).includes('/api/journals?'))window.filterCalls++;return original(...args)};
          // The row must work even when implicit label activation is absent.
          window.blockLabelForwarding=true;
          document.addEventListener('click', event=>{
            if(window.blockLabelForwarding && event.target.closest('.multi-select-option') && event.target.tagName!=='INPUT') event.preventDefault();
          }, true);
        }""")

        def panel(key):
            trigger = page.locator(f"#{key}-trigger")
            if trigger.get_attribute("aria-expanded") != "true":
                trigger.click()
            return page.locator("#" + trigger.get_attribute("aria-controls"))

        def toggle(key, value, checked=True):
            before = page.evaluate("filterCalls")
            option = panel(key).locator(f'input[type="checkbox"][value="{value}"]')
            row = option.locator("..")
            row.scroll_into_view_if_needed()
            rect = row.bounding_box()
            assert rect["height"] >= 44
            # Click the empty right edge, away from both checkbox and text.
            row.click(position={"x": rect["width"] - 5, "y": rect["height"] / 2}, delay=150)
            expect(option).to_be_checked(checked=checked)
            page.wait_for_function("filterCalls === " + str(before + 1))
            expect(page.locator("#export-link")).to_have_attribute("aria-disabled", "false")

        def close():
            page.keyboard.press("Escape")

        def api(params):
            return page.evaluate("""async params => {
              const query=new URLSearchParams();
              Object.entries(params).forEach(([key,value])=>(Array.isArray(value)?value:[value]).forEach(v=>query.append(key,v)));
              const response=await fetch('/api/journals?'+query);
              return {status:response.status,body:await response.json()};
            }""", params)

        def parity(params):
            remote = api(params)
            assert remote["status"] == 200, remote
            local = search(con, **params)
            assert remote["body"]["total"] == local["total"]
            where, values, order = selection(params)
            all_ids = {r[0] for r in con.execute("SELECT c.journal_id FROM catalogue c" + where + order, values)}
            assert {r["journal_id"] for r in remote["body"]["results"]} <= all_ids
            return remote["body"]

        toggle("abdc", "A*")
        toggle("abdc", "A")
        expect(page.locator("#abdc")).to_have_values(["A*", "A"])
        page.evaluate("window.blockLabelForwarding=false")
        popup = panel("abdc")
        assert abs(popup.bounding_box()["width"] - page.locator("#abdc-trigger").bounding_box()["width"]) <= 1
        expect(popup.locator(".multi-select-tools")).to_be_hidden()
        expect(popup.locator(".multi-select-count")).to_have_count(0)
        # Text and the checkbox itself must each toggle once as well.
        popup.locator('.multi-select-option[data-value="B"] span').click()
        expect(page.locator("#abdc")).to_have_values(["A*", "A", "B"])
        popup.locator('input[value="B"]').click()
        expect(page.locator("#abdc")).to_have_values(["A*", "A"])
        expect(page.locator("#export-link")).to_have_attribute("aria-disabled", "false")
        before = page.evaluate("filterCalls")
        popup.locator('input[value="B"]').focus()
        page.keyboard.press("Space")
        expect(page.locator("#abdc")).to_have_values(["A*", "A", "B"])
        page.keyboard.press("Space")
        expect(page.locator("#abdc")).to_have_values(["A*", "A"])
        assert page.evaluate("filterCalls") == before + 2
        expect(page.locator("#export-link")).to_have_attribute("aria-disabled", "false")
        close()
        expect(page.locator("#abdc-trigger")).to_be_focused()
        values = parse_qs(urlsplit(page.locator("#export-link").get_attribute("href")).query)
        assert values["abdc"] == ["A*", "A"]
        result = parity({"abdc": ["A*", "A"], "limit": 500})
        assert result["total"] == search(con, abdc="A*")["total"] + search(con, abdc="A")["total"]
        checks.append("explicit row clicks work without label forwarding; square/Space toggle once; one request per change")

        toggle("jcr_quartile", "Q1")
        toggle("jcr_quartile", "Q2")
        close()
        result = parity({"abdc": ["A*", "A"], "jcr_quartile": ["Q1", "Q2"], "limit": 500})
        assert all(r["abdc"] in ("A*", "A") and r["jcr_quartile"] in ("Q1", "Q2") for r in result["results"])
        for key, vals in (("wos_index", ["SCIE", "SSCI"]), ("source_type", ["journal", "book series"]),
                          ("ajg", ["4*", "4"]), ("cas", ["1", "2"]), ("sjr_quartile", ["Q1", "Q2"])):
            parity({key: vals, "limit": 500})
        checks.append("cross-field intersection and all nine API fields agree with SQLite")

        page.locator('thead [data-sort="impact_factor"]').click()
        page.locator("#next").click()
        expect(page.locator("#page-label")).to_contain_text("Page 2")
        before = page.evaluate("filterCalls")
        page.locator("#language").select_option("zh")
        expect(page.locator("#abdc")).to_have_values(["A*", "A"])
        expect(page.locator("#jcr_quartile")).to_have_values(["Q1", "Q2"])
        expect(page.locator("#page-label")).to_contain_text("第 2 页")
        assert page.evaluate("filterCalls") == before
        href = page.locator("#export-link").get_attribute("href")
        values = parse_qs(urlsplit(href).query)
        assert values["abdc"] == ["A*", "A"] and values["jcr_quartile"] == ["Q1", "Q2"]
        assert values["sort"] == ["impact_factor"]
        page.evaluate("""() => {
          const original=URL.createObjectURL; URL.createObjectURL=blob=>{window.multiCSV=blob;return original(blob)};
          const click=HTMLAnchorElement.prototype.click;
          HTMLAnchorElement.prototype.click=function(){if(!this.download)return click.call(this)};
        }""")
        if page.evaluate("!!window.JOURNAL_STATIC"):
            page.locator("#export-link").click()
            page.wait_for_function("window.multiCSV")
            data = page.evaluate("async()=>multiCSV.text()")
        else:
            data = page.evaluate("async href=>(await fetch(href)).text()", href)
        exported = list(csv.DictReader(io.StringIO(data.lstrip("\ufeff"))))
        expected = search(con, abdc=["A*", "A"], jcr_quartile=["Q1", "Q2"], sort="impact_factor", limit=500)
        assert len(exported) == expected["total"]
        where, values, order = selection(dict(abdc=["A*", "A"], jcr_quartile=["Q1", "Q2"], sort="impact_factor"))
        all_ids = {r[0] for r in con.execute("SELECT c.journal_id FROM catalogue c" + where + order, values)}
        assert {r["journal_id"] for r in exported} == all_ids
        impacts = [float(r["impact_factor"]) for r in exported]
        assert impacts == sorted(impacts)
        assert len({r["journal_id"] for r in exported}) == len(exported)
        assert all(r["abdc"] in ("A*", "A") and r["jcr_quartile"] in ("Q1", "Q2") for r in exported)
        checks.append("locale, sort, paging and complete CSV retain multiple choices")

        page.locator("#clear").click()
        expect(page.locator("#abdc")).to_have_values([])
        expect(page.locator("#jcr_quartile")).to_have_values([])
        toggle("broad_area", "area-1400")
        close()
        toggle("subcategory", "asjc-1406")
        close()
        toggle("broad_area", "area-2700")
        close()
        expect(page.locator("#subcategory")).to_have_values(["asjc-1406"])
        toggle("subcategory", "asjc-2705")
        close()
        expect(page.locator("#subcategory")).to_have_values(["asjc-1406", "asjc-2705"])
        parity({"broad_area": ["area-1400", "area-2700"], "subcategory": ["asjc-1406", "asjc-2705"], "limit": 500})
        toggle("broad_area", "area-1400", False)
        close()
        expect(page.locator("#subcategory")).to_have_values(["asjc-2705"])
        toggle("broad_area", "area-2700", False)
        close()
        expect(page.locator("#subcategory")).to_have_values([])
        expect(page.locator("#subcategory-trigger")).to_be_disabled()
        assert api({"broad_area": ["area-1400"], "subcategory": ["asjc-1406", "asjc-2705"]})["status"] == 400
        assert api({"abdc": ["A*", "INVALID"]})["status"] == 400
        checks.append("taxonomy union preserves selected leaves and prunes only orphaned leaves")

        page.locator("#clear").click()
        page.locator("#language").select_option("en")
        for grade in ("A*", "A", "B", "C"):
            toggle("abdc", grade)
        close()
        assert page.locator("#abdc-trigger").inner_text().strip() != "All"
        assert parity({"abdc": ["A*", "A", "B", "C"]})["total"] < search(con)["total"]
        page.locator("#clear").click()
        expect(page.locator("#abdc-trigger")).to_contain_text("All")
        checks.append("no choices means unrestricted; all known grades excludes missing")

        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            if page.locator("#filter-panel").get_attribute("open") is None:
                page.locator("#filter-panel > summary").click()
            popup = panel("broad_area")
            searchbox = popup.locator('input[type="search"]')
            expect(searchbox).to_be_visible()
            searchbox.fill("Business")
            expect(popup.locator('input[type="checkbox"][value="area-1400"]')).to_be_visible()
            expect(popup.locator('input[type="checkbox"][value="area-2700"]')).to_be_hidden()
            searchbox.fill("no-such-discipline-xyz")
            expect(popup.locator(".multi-select-option:visible")).to_have_count(0)
            expect(popup).to_contain_text("No options found")
            searchbox.fill("Business")
            rect = popup.bounding_box()
            assert rect["x"] >= 0 and rect["x"] + rect["width"] <= width + 1
            assert rect["y"] >= 0 and rect["y"] + rect["height"] <= 845, rect
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            close()
        assert not errors, errors
        checks.append("searchable popup, Escape focus and 320/390px viewport fit")
        browser.close()
    con.close()
    return {"url": url, "checks": checks, "page_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18766/")
    print(json.dumps(run(parser.parse_args().url), ensure_ascii=False))
