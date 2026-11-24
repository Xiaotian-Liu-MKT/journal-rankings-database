"""Navigate the public detail tabs and disclosures in browser acceptance checks."""


def detail_tab(page, name):
    page.locator(f'[data-detail-tab="{name}"]').click()


def source_record(page, system, edition=None):
    detail_tab(page, "sources")
    group = page.locator(f'.source-group[data-system="{system}"]')
    if not group.evaluate("node => node.open"):
        group.locator(":scope > summary").click()
    record = group.locator(".observation")
    if edition:
        record = group.locator(f'.observation[data-edition^="{edition}"]')
    record = record.first
    if not record.evaluate("node => node.open"):
        record.locator(":scope > summary").click()
    return record
