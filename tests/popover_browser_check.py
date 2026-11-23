"""Exercise metric explanations with mouse, keyboard, touch and native dialogs."""
import argparse
import json

from playwright.sync_api import sync_playwright, expect


def run(url):
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.locator("#q").fill("00935301")
        expect(page.locator("#rows .journal-btn")).to_have_count(1, timeout=60000)
        rating = page.locator('#rows [data-metric="abdc"]').first
        popup = page.locator("#metric-popover")
        rating.hover()
        page.wait_for_timeout(200)
        assert not popup.is_visible()
        page.mouse.move(15, 15)
        page.wait_for_timeout(400)
        assert not popup.is_visible()
        checks.append("brief hover does not open a popup")

        rating.hover()
        expect(popup).to_be_visible(timeout=2000)
        expect(popup).to_contain_text("ABDC")
        expect(popup).to_contain_text("highest category")
        expect(rating).to_have_attribute("aria-expanded", "true")
        assert popup.locator("a").get_attribute("href").startswith("https://abdc.edu.au/")
        popup.hover()
        page.wait_for_timeout(250)
        expect(popup).to_be_visible()
        page.keyboard.press("Escape")
        expect(popup).not_to_be_visible()
        checks.append("delayed bilingual content, source link, hoverable popup and Escape")

        rating.focus()
        expect(popup).to_be_visible()
        page.keyboard.press("ArrowDown")
        assert popup.evaluate("node=>node.contains(document.activeElement)")
        page.mouse.move(15, 15)
        page.wait_for_timeout(250)
        expect(popup).to_be_visible()
        page.keyboard.press("Escape")
        expect(popup).not_to_be_visible()
        expect(rating).to_be_focused()
        page.locator("#q").focus()
        rating.focus()
        expect(popup).to_be_visible()
        page.locator("#q").focus()
        expect(popup).not_to_be_visible()
        checks.append("keyboard focus opens and unrelated focus closes")

        cas = page.locator('#rows [data-metric="cas"]').first
        cas.hover()
        expect(popup).to_be_visible()
        expect(popup).to_contain_text("not a JCR quartile")
        expect(popup).to_contain_text("source zone 2 as Q2")
        page.mouse.move(15, 15)
        expect(popup).not_to_be_visible()
        checks.append("CAS display mapping is explained without claiming JCR equivalence")

        rating.hover()
        expect(popup).to_be_visible()
        page.locator("#clear").click()
        expect(page.locator("#rows .journal-btn")).to_have_count(50)
        expect(popup).not_to_be_visible()
        checks.append("rerender removes orphan popups")

        page.locator("#q").fill("00935301")
        expect(page.locator("#rows .journal-btn")).to_have_count(1)
        page.locator("#language").select_option("zh")
        rating.hover()
        expect(popup).to_be_visible()
        expect(popup).to_contain_text("最高类别")
        expect(popup.locator("a")).to_contain_text("官方来源")
        page.keyboard.press("Escape")
        page.locator("#rows .journal-btn").click()
        expect(page.locator("#detail")).to_be_visible()
        modal_rating = page.locator('#detail-body [data-metric="abdc"]').first
        modal_rating.hover()
        expect(popup).to_be_visible()
        assert popup.evaluate("node=>!!node.closest('dialog[open]')")
        page.keyboard.press("Escape")
        expect(popup).not_to_be_visible()
        expect(page.locator("#detail")).to_be_visible()
        page.locator("#detail-title").hover()
        modal_rating.hover()
        expect(popup).to_be_visible()
        popup.locator(".metric-popover__close").click()
        expect(popup).not_to_be_visible()
        expect(page.locator("#detail")).to_be_visible()
        page.keyboard.press("Escape")
        checks.append("Chinese content and interactive popup inside journal details")

        page.locator("#rows .journal-btn").click()
        old_rating = page.locator("#detail-body .observation").filter(has_text="ABDC · 2010").locator('[data-metric="abdc"]').first
        old_rating.hover()
        expect(popup).to_be_visible()
        expect(popup.locator(".metric-popover__title")).to_have_text("ABDC · 2010")
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        checks.append("historical ratings retain their own edition in explanations")

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(url, wait_until="networkidle", timeout=60000)
        mobile.locator("#q").fill("00935301")
        expect(mobile.locator("#rows .journal-btn")).to_have_count(1, timeout=60000)
        tag = mobile.locator('#rows [data-metric="SSCI"]').first
        tag.tap()
        mp = mobile.locator("#metric-popover")
        expect(mp).to_be_visible()
        expect(mp).to_contain_text("Social Sciences Citation Index")
        bounds = mp.bounding_box()
        assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= 390
        assert 0 <= bounds["y"] and bounds["y"] + bounds["height"] <= 844
        mp.locator(".metric-popover__close").tap()
        expect(mp).not_to_be_visible()
        checks.append("first touch opens, close works and the popup fits a phone")

        fallback = browser.new_page(viewport={"width": 1280, "height": 900})
        fallback.add_init_script("Object.defineProperty(HTMLElement.prototype,'showPopover',{value:undefined,configurable:true})")
        fallback.on("pageerror", lambda error: errors.append(str(error)))
        fallback.goto(url, wait_until="networkidle", timeout=60000)
        fallback.locator("#q").fill("00935301")
        expect(fallback.locator("#rows .journal-btn")).to_have_count(1, timeout=60000)
        fallback.locator('#rows [data-metric="abdc"]').hover()
        expect(fallback.locator("#metric-popover")).to_be_visible()
        checks.append("popup fallback works without the native Popover API")
        assert not errors, errors
        browser.close()
    return {"url": url, "checks": checks, "page_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766/")
    args = parser.parse_args()
    print(json.dumps(run(args.url), ensure_ascii=False))
