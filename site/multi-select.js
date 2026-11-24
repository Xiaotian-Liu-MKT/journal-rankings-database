(() => {
  'use strict';
  const widgets = new WeakMap();
  const registry = new Set();
  const text = (en, zh) => window.JournalI18n?.locale === 'zh' ? zh : en;
  const realOptions = select => [...select.options].filter(option => option.value);
  const values = select => realOptions(select).filter(option => option.selected).map(option => option.value);
  const label = option => option.textContent.trim();
  function refresh(widget) {
    const {select, trigger, panel, list, search, clear} = widget;
    const options = realOptions(select);
    // A placeholder cannot be a meaningful multiselect choice.
    [...select.options].filter(option => !option.value).forEach(option => { option.selected = false; });
    const byValue = new Map([...list.querySelectorAll('[data-value]')].map(row => [row.dataset.value, row]));
    for (const option of options) {
      let row = byValue.get(option.value);
      if (!row) {
        row = document.createElement('label'); row.className = 'multi-select-option'; row.dataset.value = option.value;
        const input = document.createElement('input'); input.type = 'checkbox'; input.value = option.value;
        const content = document.createElement('span'); row.append(input, content); list.append(row);
        input.addEventListener('change', () => {
          const target = [...select.options].find(item => item.value === input.value);
          if (target) target.selected = input.checked;
          refresh(widget); select.dispatchEvent(new Event('change', {bubbles: true}));
        });
      }
      row.querySelector('input').checked = option.selected;
      row.querySelector('span').textContent = label(option);
      byValue.delete(option.value);
    }
    byValue.forEach(row => row.remove());
    select.disabled ? trigger.setAttribute('disabled', '') : trigger.removeAttribute('disabled');
    const selectedLabels = options.filter(option => option.selected).map(label);
    trigger.querySelector('.multi-select-value').textContent = selectedLabels.length ? `${selectedLabels.slice(0, 2).join(', ')}${selectedLabels.length > 2 ? ` +${selectedLabels.length - 2}` : ''}` : text('All', '全部');
    trigger.title = selectedLabels.join(', ') || text('All', '全部');
    trigger.setAttribute('aria-label', `${widget.label.textContent.trim()}: ${trigger.title}`);
    const many = options.length > 8;
    search.hidden = !many; if (many) search.placeholder = text('Search options', '搜索选项');
    search.setAttribute('aria-label', text('Search options', '搜索选项'));
    panel.setAttribute('aria-label', widget.label.textContent.trim());
    search.parentElement.hidden = !many;
    clear.textContent = text('Clear selection', '清除选择');
    clear.setAttribute('aria-label', clear.textContent);
    filter(widget);
    if (widget.open) place(widget);
  }
  function filter(widget) {
    const query = widget.search.value.trim().toLocaleLowerCase(); let shown = 0;
    widget.list.querySelectorAll('[data-value]').forEach(row => { const visible = !query || row.textContent.toLocaleLowerCase().includes(query); row.hidden = !visible; if (visible) shown++; });
    let empty = widget.list.querySelector('.multi-select-empty');
    if (!shown && widget.search.hidden === false) { if (!empty) { empty = document.createElement('div'); empty.className = 'multi-select-empty'; widget.list.append(empty); } empty.textContent = text('No options found', '没有匹配项'); }
    else empty?.remove();
    if (widget.open) place(widget);
  }
  function place(widget) {
    const rect = widget.trigger.getBoundingClientRect(), panel = widget.panel;
    panel.style.width = `${Math.min(rect.width, window.innerWidth - 16)}px`;
    const spaceBelow = Math.max(0, window.innerHeight - rect.bottom - 8);
    const spaceAbove = Math.max(0, rect.top - 8);
    panel.style.maxHeight = '390px';
    const naturalHeight = panel.offsetHeight;
    const below = naturalHeight <= spaceBelow || spaceBelow >= spaceAbove;
    const available = below ? spaceBelow : spaceAbove;
    panel.style.maxHeight = `${Math.max(1, Math.min(390, available))}px`;
    const height = Math.min(panel.offsetHeight, available);
    panel.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - panel.offsetWidth - 8))}px`;
    panel.style.top = `${Math.max(8, Math.min(below ? rect.bottom + 4 : rect.top - height - 4, window.innerHeight - height - 8))}px`;
  }
  function close(widget, focus = false) { if (!widget.open) return; widget.open = false; widget.panel.hidden = true; widget.trigger.setAttribute('aria-expanded', 'false'); if (focus) widget.trigger.focus(); }
  function open(widget) { if (widget.select.disabled) return; registry.forEach(item => { if (item !== widget) close(item); }); widget.open = true; widget.panel.hidden = false; widget.trigger.setAttribute('aria-expanded', 'true'); place(widget); if (!widget.search.hidden) widget.search.focus(); else widget.list.querySelector('input')?.focus(); }
  function initialise(select) {
    if (!select || widgets.has(select)) return widgets.get(select);
    select.multiple = true; select.classList.add('multi-select-native'); select.setAttribute('aria-hidden', 'true'); select.tabIndex = -1;
    const labelElement = document.querySelector(`label[for="${CSS.escape(select.id)}"]`) || select.closest('.filter-group')?.querySelector('label') || select;
    const host = document.createElement('div'); host.className = 'multi-select'; select.after(host); host.append(select);
    const trigger = document.createElement('button'); trigger.type = 'button'; trigger.id = `${select.id}-trigger`; trigger.className = 'multi-select-trigger'; trigger.dataset.multiTrigger = select.id; trigger.setAttribute('aria-haspopup', 'dialog'); trigger.setAttribute('aria-expanded', 'false');
    const value = document.createElement('span'); value.className = 'multi-select-value'; const chevron = document.createElement('span'); chevron.className = 'multi-select-chevron'; chevron.textContent = '⌄'; trigger.append(value, chevron); host.append(trigger);
    const panel = document.createElement('div'); panel.className = 'multi-select-popover'; panel.id = `${select.id}-options`; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', labelElement.textContent.trim()); panel.hidden = true;
    const tools = document.createElement('div'); tools.className = 'multi-select-tools'; const search = document.createElement('input'); search.className = 'multi-select-search'; search.type = 'search'; search.autocomplete = 'off'; search.setAttribute('aria-label', text('Search options', '搜索选项')); const clear = document.createElement('button'); clear.type = 'button'; clear.className = 'multi-select-clear'; tools.append(search); const list = document.createElement('div'); list.className = 'multi-select-options'; panel.append(tools, list, clear); host.append(panel);
    trigger.setAttribute('aria-controls', panel.id); const widget = {select, label: labelElement, trigger, panel, list, search, clear, open: false}; widgets.set(select, widget); registry.add(widget);
    trigger.addEventListener('click', () => widget.open ? close(widget) : open(widget));
    trigger.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); close(widget); } });
    labelElement.addEventListener('click', event => { if (event.target === labelElement) { event.preventDefault(); trigger.focus(); } });
    clear.addEventListener('click', () => { realOptions(select).forEach(option => { option.selected = false; }); refresh(widget); select.dispatchEvent(new Event('change', {bubbles: true})); });
    select.addEventListener('change', () => refresh(widget));
    search.addEventListener('input', () => filter(widget));
    panel.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); close(widget, true); } });
    host.addEventListener('focusout', () => setTimeout(() => { if (widget.open && !host.contains(document.activeElement)) close(widget); }, 0));
    new MutationObserver(() => refresh(widget)).observe(select, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['disabled', 'selected']});
    refresh(widget); return widget;
  }
  document.addEventListener('click', event => { document.querySelectorAll('.multi-select-trigger[aria-expanded=true]').forEach(trigger => { const select = document.getElementById(trigger.dataset.multiTrigger), widget = select && widgets.get(select); if (widget && !widget.panel.contains(event.target) && !widget.trigger.contains(event.target)) close(widget); }); });
  const relocate = () => registry.forEach(widget => { if (widget.open) place(widget); });
  window.addEventListener('resize', relocate); window.addEventListener('scroll', relocate, true);
  window.addEventListener('journal-locale-change', () => document.querySelectorAll('select[data-multi]').forEach(select => { const widget = widgets.get(select); if (widget) refresh(widget); }));
  window.JournalMultiSelect = {init(root = document) { root.querySelectorAll?.('select[data-multi]').forEach(initialise); }, values, refresh(target) { if (target) { const widget = widgets.get(target); if (widget) refresh(widget); } else document.querySelectorAll('select[data-multi]').forEach(select => refresh(widgets.get(select))); }, clear(select) { realOptions(select).forEach(option => { option.selected = false; }); refresh(widgets.get(select)); }};
  document.addEventListener('DOMContentLoaded', () => window.JournalMultiSelect.init());
})();
