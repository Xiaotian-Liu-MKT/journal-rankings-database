"""Exercise sortable table headers, grade order, missing values and export order."""
import argparse
import csv
import io
import json
import re

from playwright.sync_api import expect, sync_playwright


def run(url):
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle", timeout=60000)
        expect(page.locator("#rows .journal-btn")).to_have_count(50, timeout=60000)
        page.wait_for_function("document.querySelector('#broad_area').options.length > 1")
        expect(page.locator("thead [data-sort]")).to_have_count(10)
        assert page.locator(".table-wrap").evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        page.locator("#broad_area").select_option("area-1400")
        page.locator("#subcategory").select_option("asjc-1406")
        expect(page.locator("#export-link")).to_have_attribute("href", re.compile("subcategory=asjc-1406"))
        metadata = page.evaluate("async()=> (await (await fetch('/api/meta')).json())")
        labels = {node["id"]: node["label_en"] for node in metadata["taxonomy"]["nodes"]}

        def api(params):
            return page.evaluate("""async params => {
              const r = await fetch('/api/journals?' + new URLSearchParams(params));
              return {status:r.status,body:await r.json()};
            }""", params)

        ranks = {"abdc": {"A*": 1, "A": 2, "B": 3, "C": 4},
                 "ajg": {"4*": 1, "4": 2, "3": 3, "2": 4, "1": 5},
                 "jcr_quartile": {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}}

        def value(row, key):
            if key in ranks:
                return ranks[key].get(row[key])
            if key == "lists":
                return int(row["ft50"]) + int(row["utd24"])
            if key == "wos_indexes":
                return "\x1f".join(sorted(row["wos_indexes"], key=str.casefold)).casefold() or None
            if key == "subcategory":
                names = {labels[path["subcategory_id"]] for path in row["taxonomy_paths"] if path["subcategory_id"]}
                return "\x1f".join(sorted(names, key=str.casefold)).casefold() or None
            return row[key]

        keys = ["abdc", "ajg", "jcr_quartile", "cas_zone", "impact_factor", "sjr", "wos_indexes", "lists", "subcategory", "title"]
        for key in keys:
            header = page.locator(f'thead [data-sort="{key}"]')
            for order in ("asc", "desc"):
                header.click()
                expect(header.locator("xpath=..")).to_have_attribute("aria-sort", "ascending" if order == "asc" else "descending")
                expect(page.locator("#sort")).to_have_value(key)
                expect(page.locator("#export-link")).to_have_attribute("href", re.compile("order=" + order))
                result = api({"broad_area": "area-1400", "subcategory": "asjc-1406", "sort": key, "order": order, "limit": "500"})
                assert result["status"] == 200, (key, order, result)
                assert result["body"]["total"] <= 500
                rows = result["body"]["results"]
                if key != "title":  # Title uses host-language collation; grades/numbers/composites are explicit.
                    values = [value(row, key) for row in rows]
                    present = [item for item in values if item is not None]
                    assert present == sorted(present, reverse=order == "desc"), (key, order)
                    assert values == present + [None] * (len(values) - len(present)), (key, order, "missing placement")
                expect(page.locator("#rows .journal-btn").first).to_have_text(page.evaluate("title => JournalTitle.format(title)", rows[0]["title"]))
        checks.append("all ten headers toggle directions; ratings, numeric values and composite labels sort correctly")
        checks.append("missing values remain last in both directions; zero list matches remain valid")

        page.locator('thead [data-sort="abdc"]').click()
        page.locator('thead [data-sort="abdc"]').click()
        expect(page.locator('thead [data-sort="abdc"]').locator("xpath=..")).to_have_attribute("aria-sort", "descending")
        first = api({"broad_area": "area-1400", "subcategory": "asjc-1406", "sort": "abdc", "order": "desc", "limit": "50"})["body"]["results"]
        page.locator("#next").click()
        expect(page.locator("#page-label")).to_contain_text("Page 2")
        second = api({"broad_area": "area-1400", "subcategory": "asjc-1406", "sort": "abdc", "order": "desc", "limit": "50", "offset": "50"})["body"]["results"]
        assert not ({row["journal_id"] for row in first} & {row["journal_id"] for row in second})
        page.locator("#language").select_option("zh")
        expect(page.locator("#page-label")).to_contain_text("第 2 页")
        expect(page.locator("#broad_area")).to_have_value("area-1400")
        expect(page.locator("#subcategory")).to_have_value("asjc-1406")
        expect(page.locator('thead [data-sort="abdc"]').locator("xpath=..")).to_have_attribute("aria-sort", "descending")
        checks.append("sort, filters and stable pagination survive language changes")

        page.evaluate("""() => {
          const original=URL.createObjectURL; URL.createObjectURL=blob=>{window.sortedCSV=blob;return original(blob)};
          const click=HTMLAnchorElement.prototype.click;
          HTMLAnchorElement.prototype.click=function(){if(!this.download)return click.call(this)};
        }""")
        href = page.locator("#export-link").get_attribute("href")
        if page.evaluate("!!window.JOURNAL_STATIC"):
            page.locator("#export-link").click()
            page.wait_for_function("window.sortedCSV")
            text = page.evaluate("async()=> sortedCSV.text()")
        else:
            text = page.evaluate("async href=>(await fetch(href)).text()", href)
        exported = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
        expected = api({"broad_area": "area-1400", "subcategory": "asjc-1406", "sort": "abdc", "order": "desc", "limit": "500"})["body"]["results"]
        assert [row["journal_id"] for row in exported] == [row["journal_id"] for row in expected]
        assert api({"sort": "unknown-column"})["status"] == 400
        assert api({"sort": "abdc", "order": "sideways"})["status"] == 400
        checks.append("CSV preserves full filtered sort order and invalid parameters are rejected")
        assert not errors, errors
        browser.close()
    return {"url": url, "checks": checks, "page_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18766/")
    print(json.dumps(run(parser.parse_args().url), ensure_ascii=False))
