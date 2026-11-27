/* Special Issues (Call for Papers) view — isolated from Journal Search */
(() => {
  'use strict';

  const $ = selector => document.querySelector(selector);
  const tr = (en, zh) => window.JournalI18n?.locale === 'zh' ? zh : en;
  const node = (tag, text, attrs = {}) => {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = String(text);
    for (const [k, v] of Object.entries(attrs)) {
      if (v !== undefined && v !== null) el.setAttribute(k, String(v));
    }
    return el;
  };

  const DOMAIN_LABELS = {
    all: ['All domains', '全部学科'],
    marketing: ['Marketing', '市场营销 (Marketing)'],
    is: ['Information Systems', '信息系统 (IS)'],
    tourism: ['Tourism & Hospitality', '旅游与酒店 (Tourism)']
  };

  const DEADLINE_TYPE_LABELS = {
    fixed: ['', ''],
    extended: ['Extended', '已延期'],
    abstract_first: ['Abstract / proposal first', '先交摘要/提案'],
    rolling: ['Rolling', '滚动征稿'],
    unknown: ['TBA', '日期待定']
  };

  const state = {
    view: 'journals',
    data: null,
    status: 'idle', // idle | loading | ready | error
    error: '',
    domain: 'all',
    journalId: '',
    query: '',
    openOnly: true,
    sort: 'deadline',
    coverageOpen: false,
    built: false
  };

  function parseLocalDate(str) {
    if (!str || typeof str !== 'string') return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(str.trim());
    if (!m) return null;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function localToday() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }

  function deadlineInfo(issue, today) {
    const d = parseLocalDate(issue.deadline_date);
    if (!d) {
      return {
        date: null,
        diffDays: null,
        expired: false,
        group: 1 // rolling / unknown
      };
    }
    const diffDays = Math.round((d.getTime() - today.getTime()) / 86400000);
    const expired = diffDays < 0;
    return {
      date: d,
      diffDays,
      expired,
      group: expired ? 2 : 0
    };
  }

  function isIssueOpen(issue, today) {
    return !deadlineInfo(issue, today).expired;
  }

  function computeLiveCounts(data) {
    const today = localToday();
    const byDomain = { all: 0, marketing: 0, is: 0, tourism: 0 };
    const byJournal = new Map();
    for (const j of data.journals || []) byJournal.set(j.journal_id, 0);
    for (const issue of data.issues || []) {
      if (isIssueOpen(issue, today)) {
        byDomain.all += 1;
        if (issue.domain in byDomain) byDomain[issue.domain] += 1;
        byJournal.set(issue.journal_id, (byJournal.get(issue.journal_id) || 0) + 1);
      }
    }
    return { byDomain, byJournal };
  }

  function updateTabBadge() {
    const badge = $('#si-tab-badge');
    if (!badge || !state.data) return;
    const { byDomain } = computeLiveCounts(state.data);
    badge.textContent = String(byDomain.all);
    badge.hidden = false;
  }

  function setView(next, updateHash = true) {
    const target = next === 'special-issues' ? 'special-issues' : 'journals';
    state.view = target;
    const journalsView = $('#view-journals');
    const siView = $('#view-special-issues');
    const tabJournals = $('#tab-journals');
    const tabSi = $('#tab-special-issues');
    if (journalsView) journalsView.hidden = target !== 'journals';
    if (siView) siView.hidden = target !== 'special-issues';
    if (tabJournals) tabJournals.setAttribute('aria-pressed', String(target === 'journals'));
    if (tabSi) tabSi.setAttribute('aria-pressed', String(target === 'special-issues'));
    if (updateHash) {
      const desiredHash = target === 'special-issues' ? '#special-issues' : '';
      if (window.location.hash !== desiredHash) {
        const nextUrl = window.location.pathname + window.location.search + desiredHash;
        history.replaceState(null, '', nextUrl);
      }
    }
    if (target === 'special-issues') {
      ensureBuilt();
      if (state.status === 'idle') loadData();
      else renderView();
    }
  }

  function ensureBuilt() {
    const root = $('#view-special-issues');
    if (!root || state.built) return;
    state.built = true;

    const header = node('div', undefined, { class: 'si-header' });
    header.append(
      node('p', '', { class: 'si-intro', id: 'si-intro' }),
      node('div', '', { class: 'si-statline', id: 'si-statline' })
    );

    const controls = node('div', undefined, { class: 'si-controls' });
    const pills = node('div', undefined, { class: 'si-domain-pills', id: 'si-domain', role: 'group' });
    for (const key of ['all', 'marketing', 'is', 'tourism']) {
      const btn = node('button', undefined, {
        type: 'button',
        class: 'si-pill',
        'data-si-domain': key,
        'aria-pressed': String(state.domain === key)
      });
      btn.append(
        node('span', '', { class: 'si-pill-label' }),
        node('span', '0', { class: 'si-pill-count' })
      );
      btn.addEventListener('click', () => {
        state.domain = key;
        if (state.journalId && state.data) {
          const j = state.data.journals.find(item => item.journal_id === state.journalId);
          if (j && key !== 'all' && j.domain !== key) state.journalId = '';
        }
        renderView();
      });
      pills.append(btn);
    }

    const bar = node('div', undefined, { class: 'si-bar' });
    const searchInput = node('input', undefined, {
      id: 'si-q',
      class: 'si-input',
      type: 'search',
      autocomplete: 'off'
    });
    searchInput.addEventListener('input', event => {
      state.query = event.target.value;
      renderResults();
    });

    const journalSelect = node('select', undefined, { id: 'si-journal', class: 'si-select' });
    journalSelect.addEventListener('change', event => {
      state.journalId = event.target.value;
      renderResults();
    });

    const sortSelect = node('select', undefined, { id: 'si-sort', class: 'si-select' });
    sortSelect.addEventListener('change', event => {
      state.sort = event.target.value;
      renderResults();
    });

    const openLabel = node('label', undefined, { class: 'si-toggle', for: 'si-open-only' });
    const openCheckbox = node('input', undefined, { id: 'si-open-only', type: 'checkbox' });
    openCheckbox.checked = state.openOnly;
    openCheckbox.addEventListener('change', event => {
      state.openOnly = event.target.checked;
      renderResults();
    });
    openLabel.append(openCheckbox, node('span', '', { id: 'si-open-only-label' }));

    bar.append(searchInput, journalSelect, sortSelect, openLabel);
    controls.append(pills, bar);

    const resultsHead = node('div', undefined, { class: 'si-results-head' });
    resultsHead.append(
      node('h2', '', { id: 'si-results-heading' }),
      node('span', '', { class: 'si-results-count', id: 'si-results-count' })
    );

    const tableWrap = node('div', undefined, { class: 'si-table-wrap', id: 'si-results-wrap' });
    const coverage = node('details', undefined, { class: 'si-coverage', id: 'si-coverage' });
    coverage.open = state.coverageOpen;
    coverage.addEventListener('toggle', () => { state.coverageOpen = coverage.open; });
    coverage.append(
      node('summary', '', { id: 'si-coverage-summary' }),
      node('div', undefined, { class: 'si-coverage-body', id: 'si-coverage-body' })
    );

    root.append(header, controls, resultsHead, tableWrap, coverage);
  }

  function domainLabel(domain) {
    const pair = DOMAIN_LABELS[domain];
    return pair ? tr(pair[0], pair[1]) : domain;
  }

  function renderControlsText() {
    $('#si-intro').textContent = tr(
      'Open Special Issues (Calls for Papers) across 29 ABDC 2025 A* journals in Marketing, Information Systems, and Tourism & Hospitality. Click a journal name to inspect its full rankings.',
      '覆盖 Marketing、信息系统（IS）、旅游与酒店管理领域共 29 本 ABDC 2025 A* 期刊的开放特刊征稿。点击期刊名可查看完整评级与指标。'
    );
    const pills = $('#si-domain');
    if (pills) {
      pills.setAttribute('aria-label', tr('Filter by domain', '按学科筛选'));
      const counts = state.data ? computeLiveCounts(state.data).byDomain : { all: 0, marketing: 0, is: 0, tourism: 0 };
      pills.querySelectorAll('.si-pill').forEach(btn => {
        const key = btn.dataset.siDomain;
        btn.setAttribute('aria-pressed', String(state.domain === key));
        btn.querySelector('.si-pill-label').textContent = domainLabel(key);
        btn.querySelector('.si-pill-count').textContent = String(counts[key] ?? 0);
      });
    }
    const q = $('#si-q');
    if (q) {
      const ph = tr('Search topic, Chinese summary, journal, or guest editor…', '搜索英文标题、中文概括、期刊名或客座编辑…');
      q.placeholder = ph;
      q.setAttribute('aria-label', ph);
      if (q.value !== state.query) q.value = state.query;
    }
    const journalSelect = $('#si-journal');
    if (journalSelect) {
      journalSelect.setAttribute('aria-label', tr('Filter by journal', '按期刊筛选'));
      const journals = (state.data?.journals || [])
        .filter(j => state.domain === 'all' || j.domain === state.domain)
        .slice()
        .sort((a, b) => a.title.localeCompare(b.title, 'en'));
      journalSelect.replaceChildren(
        node('option', tr(`All journals (${journals.length})`, `全部期刊（${journals.length} 本）`), { value: '' }),
        ...journals.map(j => node('option', j.title, { value: j.journal_id }))
      );
      journalSelect.value = state.journalId;
    }
    const sortSelect = $('#si-sort');
    if (sortSelect) {
      sortSelect.setAttribute('aria-label', tr('Sort special issues', '排序方式'));
      sortSelect.replaceChildren(
        node('option', tr('Soonest deadline first', '截稿日最近优先'), { value: 'deadline' }),
        node('option', tr('Journal A–Z', '按期刊名 A–Z'), { value: 'journal' }),
        node('option', tr('Most recently checked', '按最近核查时间'), { value: 'checked' })
      );
      sortSelect.value = state.sort;
    }
    $('#si-open-only-label').textContent = tr('Open only', '仅看未截止');
    $('#si-results-heading').textContent = tr('Special issue calls', '特刊征稿列表');
  }

  function compareByDeadline(a, b, today) {
    const ia = deadlineInfo(a, today);
    const ib = deadlineInfo(b, today);
    if (ia.group !== ib.group) return ia.group - ib.group;
    if (ia.group === 0) {
      if (ia.diffDays !== ib.diffDays) return ia.diffDays - ib.diffDays;
    } else if (ia.group === 2) {
      if (ia.diffDays !== ib.diffDays) return ib.diffDays - ia.diffDays;
    }
    return a.journal_title.localeCompare(b.journal_title, 'en')
      || a.title.localeCompare(b.title, 'en');
  }

  function deadlineCell(issue, today) {
    const td = node('td', undefined, { class: 'si-col-deadline' });
    const info = deadlineInfo(issue, today);

    let mainText = issue.deadline_date || tr('Not specified', '未注明日期');
    if (!issue.deadline_date && issue.deadline_type === 'rolling') {
      mainText = tr('Rolling', '滚动征稿');
    }
    td.append(node('div', mainText, { class: 'si-deadline-main' }));

    const badges = node('div', undefined, { class: 'si-deadline-badges' });
    if (info.date) {
      if (info.expired) {
        badges.append(node('span', tr('Closed', '已截止'), { class: 'si-deadline-badge si-deadline-expired' }));
      } else if (info.diffDays === 0) {
        badges.append(node('span', tr('Due today', '今日截止'), { class: 'si-deadline-badge si-deadline-urgent' }));
      } else if (info.diffDays <= 14) {
        badges.append(node('span', tr(`${info.diffDays}d left`, `剩 ${info.diffDays} 天`), { class: 'si-deadline-badge si-deadline-urgent' }));
      } else {
        badges.append(node('span', tr(`${info.diffDays} days left`, `剩 ${info.diffDays} 天`), { class: 'si-deadline-badge si-deadline-open' }));
      }
    } else if (issue.deadline_type === 'rolling') {
      badges.append(node('span', tr('Rolling', '滚动征稿'), { class: 'si-deadline-badge si-deadline-rolling' }));
    } else {
      badges.append(node('span', tr('Date TBA', '日期待定'), { class: 'si-deadline-badge si-deadline-rolling' }));
    }

    const typePair = DEADLINE_TYPE_LABELS[issue.deadline_type];
    if (typePair && typePair[0] && issue.deadline_type !== 'rolling' && issue.deadline_type !== 'unknown') {
      badges.append(node('span', tr(typePair[0], typePair[1]), { class: 'si-type-tag' }));
    }
    td.append(badges);

    if (issue.deadline_raw && issue.deadline_raw !== issue.deadline_date) {
      td.append(node('div', issue.deadline_raw, { class: 'si-deadline-raw' }));
    }
    return td;
  }

  function renderResults() {
    const wrap = $('#si-results-wrap');
    const countEl = $('#si-results-count');
    if (!wrap) return;

    if (state.status === 'loading') {
      wrap.replaceChildren(node('div', tr('Loading special issues…', '正在加载特刊征稿…'), { class: 'si-empty' }));
      if (countEl) countEl.textContent = '';
      return;
    }
    if (state.status === 'error') {
      wrap.replaceChildren(node('div', tr('Could not load special issues: ', '无法加载特刊数据：') + state.error, { class: 'si-empty' }));
      if (countEl) countEl.textContent = '';
      return;
    }
    if (!state.data) return;

    const today = localToday();
    const tokens = state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);

    const filtered = (state.data.issues || []).filter(issue => {
      if (state.domain !== 'all' && issue.domain !== state.domain) return false;
      if (state.journalId && issue.journal_id !== state.journalId) return false;
      if (state.openOnly && !isIssueOpen(issue, today)) return false;
      if (tokens.length) {
        const hay = [
          issue.title,
          issue.summary_zh,
          issue.journal_title,
          ...(issue.guest_editors || [])
        ].join(' ').toLowerCase();
        if (!tokens.every(tok => hay.includes(tok))) return false;
      }
      return true;
    });

    filtered.sort((a, b) => {
      if (state.sort === 'journal') {
        return a.journal_title.localeCompare(b.journal_title, 'en')
          || compareByDeadline(a, b, today);
      }
      if (state.sort === 'checked') {
        return String(b.checked_at || '').localeCompare(String(a.checked_at || ''))
          || compareByDeadline(a, b, today);
      }
      return compareByDeadline(a, b, today);
    });

    if (countEl) {
      countEl.textContent = tr(
        `Showing ${filtered.length} of ${(state.data.issues || []).length} calls`,
        `显示 ${filtered.length} 条（共 ${(state.data.issues || []).length} 条）`
      );
    }

    if (!filtered.length) {
      wrap.replaceChildren(node('div', tr(
        'No special issues match the current filters.',
        '当前筛选条件下暂无符合的特刊征稿。'
      ), { class: 'si-empty' }));
      return;
    }

    const table = node('table', undefined, { class: 'si-table' });
    const thead = node('thead');
    const headRow = node('tr');
    [
      tr('Journal', '期刊'),
      tr('Special issue & Chinese summary', '特刊主题与中文概括'),
      tr('Deadline', '截稿日期'),
      tr('Checked', '核查日期')
    ].forEach(label => headRow.append(node('th', label, { scope: 'col' })));
    thead.append(headRow);

    const tbody = node('tbody');
    for (const issue of filtered) {
      const trEl = node('tr');

      const jTd = node('td', undefined, { class: 'si-col-journal' });
      const jBtn = node('button', issue.journal_title, { type: 'button', class: 'si-journal-btn' });
      jBtn.addEventListener('click', () => window.JournalApp?.openDetail(issue.journal_id));
      jTd.append(jBtn, node('div'), node('span', domainLabel(issue.domain), { class: 'si-domain-tag' }));

      const topicTd = node('td', undefined, { class: 'si-col-topic' });
      topicTd.append(
        node('a', issue.title, {
          class: 'si-issue-title',
          href: issue.cfp_url,
          target: '_blank',
          rel: 'noopener noreferrer'
        }),
        node('p', issue.summary_zh, { class: 'si-summary-zh' })
      );
      if (issue.guest_editors?.length) {
        topicTd.append(node('p', tr('Guest editors: ', '客座编辑：') + issue.guest_editors.join(', '), { class: 'si-editors' }));
      }

      const checkedTd = node('td', issue.checked_at || '—', { class: 'si-col-checked' });
      trEl.append(jTd, topicTd, deadlineCell(issue, today), checkedTd);
      tbody.append(trEl);
    }

    table.append(thead, tbody);
    wrap.replaceChildren(table);
  }

  function renderCoverage() {
    const summaryEl = $('#si-coverage-summary');
    const bodyEl = $('#si-coverage-body');
    if (!summaryEl || !bodyEl || !state.data) return;

    const journals = state.data.journals || [];
    const { byJournal } = computeLiveCounts(state.data);
    const openJournals = journals.filter(j => (byJournal.get(j.journal_id) || 0) > 0).length;
    const blockedCount = journals.filter(j => j.status === 'blocked_manual').length;

    summaryEl.textContent = tr(
      `Journal coverage & verification status (${journals.length} journals · ${openJournals} with open calls${blockedCount ? ` · ${blockedCount} manual check` : ''})`,
      `29 本覆盖期刊核查状态（共 ${journals.length} 本 · ${openJournals} 本有开放征稿${blockedCount ? ` · ${blockedCount} 本需人工直达` : ''}）`
    );

    const wrap = node('div', undefined, { class: 'si-coverage-wrap' });
    const table = node('table', undefined, { class: 'si-cov-table' });
    const thead = node('thead');
    const headRow = node('tr');
    [
      tr('Journal', '期刊'),
      tr('Domain', '学科'),
      tr('Publisher', '出版商'),
      tr('Status', '核查状态'),
      tr('Official CFP', '官方入口'),
      tr('Checked', '核查日期'),
      tr('Note', '备注')
    ].forEach(label => headRow.append(node('th', label, { scope: 'col' })));
    thead.append(headRow);

    const tbody = node('tbody');
    const domainOrder = { marketing: 0, is: 1, tourism: 2 };
    const sorted = journals.slice().sort((a, b) =>
      (domainOrder[a.domain] ?? 9) - (domainOrder[b.domain] ?? 9)
      || a.title.localeCompare(b.title, 'en')
    );

    for (const j of sorted) {
      const liveOpen = byJournal.get(j.journal_id) || 0;
      const row = node('tr');

      const jTd = node('td');
      const jBtn = node('button', j.title, { type: 'button', class: 'si-journal-btn' });
      jBtn.addEventListener('click', () => window.JournalApp?.openDetail(j.journal_id));
      jTd.append(jBtn);

      let statusText, statusClass;
      if (liveOpen > 0) {
        statusText = tr(`${liveOpen} open`, `${liveOpen} 个开放`);
        statusClass = 'si-status si-status-open';
      } else if (j.status === 'blocked_manual') {
        statusText = tr('Manual check', '受限需直达');
        statusClass = 'si-status si-status-blocked';
      } else {
        statusText = tr('No open calls', '当前无征稿');
        statusClass = 'si-status si-status-none';
      }
      const statusTd = node('td');
      statusTd.append(node('span', statusText, { class: statusClass }));

      const linkTd = node('td');
      linkTd.append(node('a', tr('CFP page ↗', '官网 CFP ↗'), {
        class: 'si-cfp-link',
        href: j.cfp_url,
        target: '_blank',
        rel: 'noopener noreferrer'
      }));

      row.append(
        jTd,
        node('td', domainLabel(j.domain)),
        node('td', j.publisher),
        statusTd,
        linkTd,
        node('td', j.checked_at || '—', { class: 'num' }),
        node('td', j.note || '—', { class: 'si-cov-note' })
      );
      tbody.append(row);
    }

    table.append(thead, tbody);
    wrap.replaceChildren(table);
    bodyEl.replaceChildren(wrap);
  }

  function renderStatline() {
    const el = $('#si-statline');
    if (!el) return;
    if (!state.data) {
      el.textContent = tr('Loading…', '加载中…');
      return;
    }
    const { byDomain } = computeLiveCounts(state.data);
    const totalJournals = (state.data.journals || []).length;
    el.textContent = tr(
      `${byDomain.all} open calls · ${totalJournals} journals · Updated ${state.data.updated_at || '—'}`,
      `${byDomain.all} 个开放征稿 · ${totalJournals} 本期刊 · 更新于 ${state.data.updated_at || '—'}`
    );
  }

  function renderView() {
    if (!state.built) return;
    renderStatline();
    renderControlsText();
    renderResults();
    renderCoverage();
  }

  async function loadData() {
    if (state.status === 'loading') return;
    state.status = 'loading';
    if (state.view === 'special-issues') renderView();
    try {
      const response = await fetch('/api/special-issues');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      state.data = data;
      state.status = 'ready';
      updateTabBadge();
      if (state.view === 'special-issues') renderView();
    } catch (err) {
      state.status = 'error';
      state.error = err.message || 'Unknown error';
      if (state.view === 'special-issues') renderView();
    }
  }

  function syncFromHash() {
    if (window.location.hash === '#special-issues') setView('special-issues', false);
    else setView('journals', false);
  }

  document.addEventListener('DOMContentLoaded', () => {
    $('#tab-journals')?.addEventListener('click', () => setView('journals', true));
    $('#tab-special-issues')?.addEventListener('click', () => setView('special-issues', true));
    window.addEventListener('hashchange', syncFromHash);
    window.addEventListener('journal-locale-change', () => {
      if (state.view === 'special-issues') renderView();
    });
    syncFromHash();
    loadData();
  });
})();
