/* Shared UI for the local API and the static GitHub Pages catalogue. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const tr = (en, zh) => window.JournalI18n?.locale === 'zh' ? zh : en;
  const display = value => value === null || value === undefined || value === '' ? '—' : String(value);
  const node = (tag, text, attrs = {}) => {
    const result = document.createElement(tag);
    if (text !== undefined && text !== null) result.textContent = String(text);
    for (const [key, value] of Object.entries(attrs)) result.setAttribute(key, value);
    return result;
  };
  const state = {
    offset: 0, limit: 50, sort: 'title', order: 'asc', total: 0,
    request: 0, controller: null, status: 'loading', lastData: null,
    applied: {}, metadata: null, error: '', errorLocale: '',
    detailId: null, detailData: null, detailRequest: 0, details: new Map()
  };
  const params = () => {
    const values = {limit: state.limit, offset: state.offset, sort: state.sort, order: state.order};
    document.querySelectorAll('[data-param]').forEach(control => {
      const value = control.type === 'checkbox' ? (control.checked ? '1' : '') : control.value.trim();
      if (value) values[control.dataset.param] = value;
    });
    return values;
  };
  const badge = value => node('span', display(value), {class: value == null || value === '' ? 'na' : 'badge'});
  const explain = (element, type, value, edition) => {
    if (value == null || value === '' || value === '—') return element;
    element.dataset.metric = type;
    element.dataset.metricValue = String(value);
    if (edition) element.dataset.metricEdition = edition;
    element.tabIndex = 0;
    element.setAttribute('role', 'button');
    element.setAttribute('aria-haspopup', 'dialog');
    element.setAttribute('aria-expanded', 'false');
    const title = window.JournalMetricInfo?.get(type, value, edition)?.title || type;
    element.setAttribute('aria-label', tr('Explain ', '说明：') + title + ' · ' + value);
    return element;
  };
  const cell = content => {
    const td = node('td');
    td.append(content instanceof Node ? content : document.createTextNode(display(content)));
    return td;
  };
  const taxonomy = () => state.metadata?.taxonomy || {nodes: [], sources: []};
  const taxonomyNodes = () => new Map((taxonomy().nodes || []).map(item => [item.id, item]));
  const taxonomyLabel = id => {
    const item = taxonomyNodes().get(id);
    if (!item) return display(id);
    return window.JournalI18n?.locale === 'zh' ? item.label_zh || item.label_en : item.label_en || item.label_zh;
  };
  const taxonomyPathText = path => path.subcategory_id
    ? `${taxonomyLabel(path.broad_id)} › ${taxonomyLabel(path.subcategory_id)}`
    : taxonomyLabel(path.broad_id);
  const taxonomyPathNodes = paths => {
    const wrap = node('div');
    if (!paths?.length) return node('span', tr('No classification supplied', '本地来源未提供分类'), {class: 'na'});
    paths.forEach(path => wrap.append(node('span', taxonomyPathText(path), {class: 'taxonomy-path'})));
    return wrap;
  };
  function populateTaxonomyControls() {
    const broad = $('#broad_area'), leaf = $('#subcategory');
    if (!broad || !leaf || !state.metadata?.taxonomy) return;
    const currentBroad = broad.value, currentLeaf = leaf.value;
    const nodes = taxonomy().nodes || [];
    const roots = nodes.filter(item => !item.parent_id);
    broad.replaceChildren(node('option', tr('All broad areas', '全部大类'), {value: ''}), ...roots.map(item => node('option', taxonomyLabel(item.id), {value: item.id})));
    broad.value = roots.some(item => item.id === currentBroad) ? currentBroad : '';
    const children = nodes.filter(item => item.parent_id === broad.value);
    leaf.replaceChildren(node('option', tr('All subcategories', '全部子类'), {value: ''}), ...children.map(item => node('option', taxonomyLabel(item.id), {value: item.id})));
    leaf.disabled = !broad.value || !children.length;
    leaf.value = children.some(item => item.id === currentLeaf) ? currentLeaf : '';
    $('#classification-heading').textContent = tr('Unified classification', '统一分类');
  }
  function sortIndicators() {
    document.querySelectorAll('th [data-sort]').forEach(button => {
      const active = button.dataset.sort === state.sort;
      button.closest('th').setAttribute('aria-sort', active ? (state.order === 'asc' ? 'ascending' : 'descending') : 'none');
    });
  }
  function controls(available) {
    $('#prev').disabled = !available || state.offset === 0;
    $('#next').disabled = !available || state.offset + state.limit >= state.total;
    const link = $('#export-link');
    link.setAttribute('aria-disabled', String(!available));
    if (available) link.href = '/api/export.csv?' + new URLSearchParams(state.applied);
    else link.removeAttribute('href');
  }
  function messageRow(message) {
    const row = node('tr');
    row.append(node('td', message, {colspan: '10', class: 'empty'}));
    $('#rows').replaceChildren(row);
  }
  function render(data) {
    state.total = data.total;
    const body = $('#rows');
    body.replaceChildren();
    for (const record of data.results) {
      const row = node('tr');
      const button = node('button', record.title, {class: 'journal-btn', type: 'button'});
      button.addEventListener('click', () => openDetail(record.journal_id));
      const title = cell(button);
      if (record.issns?.length) title.append(node('span', record.issns.join(' · '), {class: 'issn'}));
      const lists = node('div', undefined, {class: 'badges'});
      if (record.ft50) lists.append(explain(badge('FT50'), 'ft50', 'FT50'));
      if (record.utd24) lists.append(explain(badge('UTD24'), 'utd24', 'UTD24'));
      if (!lists.childNodes.length) lists.append(node('span', '—', {class: 'na'}));
      const indexes = node('div', undefined, {class: 'badges'});
      (record.wos_indexes || []).forEach(index => indexes.append(explain(badge(index), index, index)));
      if (!indexes.childNodes.length) indexes.append(node('span', '—', {class: 'na'}));
      const zone = record.cas_zone == null ? '—' : `Q${record.cas_zone}` + (record.cas_top ? ' · Top' : '');
      const sjr = display(record.sjr) + (record.sjr_quartile ? ' · ' + record.sjr_quartile : '');
      row.append(title, cell(explain(badge(record.abdc), 'abdc', record.abdc)), cell(explain(badge(record.ajg), 'ajg', record.ajg)), cell(lists), cell(indexes),
        cell(explain(node('span', display(record.impact_factor), {class: 'num'}), 'jif', record.impact_factor)), cell(explain(badge(record.jcr_quartile), 'jcr', record.jcr_quartile)),
        cell(explain(node('span', sjr, {class: 'num'}), 'sjr', sjr)),
        cell(explain(node('span', zone), 'cas', record.cas_zone == null ? null : `Q${record.cas_zone}`)), cell(taxonomyPathNodes(record.taxonomy_paths)));
      body.append(row);
    }
    if (!data.results.length) messageRow(tr('No records match these filters.', '没有符合条件的记录。'));
    const start = state.total ? data.offset + 1 : 0;
    const end = Math.min(data.offset + data.limit, state.total);
    $('#result-summary').textContent = tr(`Showing ${start}–${end} of ${state.total.toLocaleString()}`, `显示 ${start}–${end} 条，共 ${state.total.toLocaleString()} 条`);
    $('#page-label').textContent = state.total ? tr(`Page ${Math.floor(data.offset / data.limit) + 1} of ${Math.ceil(state.total / data.limit)}`, `第 ${Math.floor(data.offset / data.limit) + 1} 页 / 共 ${Math.ceil(state.total / data.limit)} 页`) : '—';
    sortIndicators();
    controls(true);
  }
  function renderError() {
    const sameLanguage = state.errorLocale === window.JournalI18n?.locale;
    messageRow(sameLanguage ? state.error : tr('Unable to show results. Check your filters and try again.', '无法显示结果，请检查筛选条件后重试。'));
    $('#result-summary').textContent = tr('Query failed', '查询失败');
    $('#page-label').textContent = '—';
    controls(false);
  }
  async function load(reset = false) {
    clearTimeout(state.debounce);
    if (reset) state.offset = 0;
    state.controller?.abort();
    state.controller = new AbortController();
    const request = ++state.request;
    const applied = params();
    state.status = 'loading';
    messageRow(tr('Loading results…', '正在加载结果…'));
    controls(false);
    try {
      const response = await fetch('/api/journals?' + new URLSearchParams(applied), {signal: state.controller.signal});
      const data = await response.json();
      if (request !== state.request) return;
      if (!response.ok) throw new Error(data.error || tr(`Request failed (${response.status}).`, `请求失败（${response.status}）。`));
      state.applied = applied;
      state.lastData = data;
      state.status = 'ready';
      render(data);
    } catch (error) {
      if (error.name === 'AbortError' || request !== state.request) return;
      state.status = 'error';
      state.error = error.message || tr('Could not load results.', '无法加载结果。');
      state.errorLocale = window.JournalI18n?.locale;
      renderError();
    }
  }
  const metricNames = {
    impact_factor: ['JIF', '影响因子'], rating: ['Rating', '评级'], field: ['Field', '领域'],
    publisher: ['Publisher', '出版商'], country: ['Country / region', '国家 / 地区'],
    categories: ['Categories', '学科'], category: ['Category', '学科'], quartile: ['Quartile', '分区'], rank: ['Rank', '排名'],
    zone: ['Zone', '分区'], top: ['Top', 'Top'], open_access: ['Open access', '开放获取'],
    index: ['WoS index', 'WoS 索引'], languages: ['Languages', '出版语言'], publisher_address: ['Publisher address', '出版商地址'],
    h_index: ['H-index', 'H 指数'], source_type: ['Publication type', '出版物类型'], areas: ['Areas', '领域'],
    sourceid: ['SJR source ID', 'SJR 来源 ID'], start_year: ['Start year', '创刊年'],
    member: ['List inclusion', '名单收录'], web_of_science: ['Web of Science index', 'Web of Science 索引'],
    sjr: ['SJR', 'SJR'], sjr_quartile: ['SJR best quartile', 'SJR 最佳分区']
  };
  const metricName = key => metricNames[key] ? tr(...metricNames[key]) : key;
  const metricValue = value => {
    if (typeof value === 'boolean') return value ? tr('Yes', '是') : tr('No', '否');
    if (Array.isArray(value)) return value.map(metricValue).join(tr('; ', '；'));
    if (value && typeof value === 'object') return Object.entries(value).filter(([, item]) => item != null && item !== '').map(([key, item]) => `${metricName(key)}: ${metricValue(item)}`).join(tr('; ', '；'));
    return display(value);
  };
  function renderDetail(data) {
    const journal = data.journal;
    $('#detail-title').textContent = journal.title;
    const body = $('#detail-body');
    const profile = node('div', undefined, {class: 'profile'});
    const fields = [
      ['ISSN', journal.issns.join(' · ') || '—'],
      [tr('Publisher', '出版商'), journal.publisher], [tr('Country / region', '国家 / 地区'), journal.country],
      ['ABDC 2025', journal.abdc, 'abdc'], ['AJG 2024', journal.ajg, 'ajg'], ['JIF', journal.impact_factor, 'jif'],
      [tr('WoS indexes', 'WoS 索引'), journal.wos_indexes?.join(' · ') || null, 'wos'],
      [tr('Languages', '出版语言'), journal.languages?.join(' · ') || null],
      [tr('JCR best quartile', 'JCR 最佳分区'), journal.jcr_quartile, 'jcr'], ['SJR', journal.sjr, 'sjr'],
      [tr('CAS', '中科院分区'), journal.cas_zone == null ? null : `Q${journal.cas_zone}`, 'cas']
    ];
    for (const [label, value, metric] of fields) {
      const item = node('div');
      const content = node('span', display(value));
      item.append(node('b', label), metric ? explain(content, metric, value) : content);
      profile.append(item);
    }
    body.replaceChildren(profile);
    const classification = node('section', undefined, {class: 'taxonomy-evidence', id: 'classification-evidence'});
    classification.append(node('h3', tr('Unified classification', '统一分类')),
      node('p', tr('Unified from source classifications; finer compatible categories are retained.', '由来源分类归并；可兼容的细分类会保留。')));
    if (journal.taxonomy_paths?.length) {
      const sources = new Map((taxonomy().sources || []).map(source => [source.name, source.url]));
      for (const path of journal.taxonomy_paths) {
        const item = node('p');
        item.append(node('strong', taxonomyPathText(path)));
        const evidence = (path.evidence || []).map(entry => {
          const relation = entry.relation === 'broader' ? tr('broader category', '上级分类依据') : tr('direct category', '直接分类依据');
          const source = sources.get(entry.system);
          const text = `${entry.system} ${entry.edition || ''}: ${entry.value || entry.field || ''} (${relation})`.trim();
          return source ? node('a', text, {href: source, target: '_blank', rel: 'noreferrer'}) : node('code', text);
        });
        if (evidence.length) item.append(document.createTextNode(' · '), ...evidence.flatMap((entry, index) => index ? [document.createTextNode(' · '), entry] : [entry]));
        classification.append(item);
      }
    } else classification.append(node('p', tr('No classification supplied by the local sources.', '本地来源未提供分类。')));
    const method = node('details', undefined, {class: 'taxonomy-method'});
    method.append(node('summary', tr('Classification method and references', '归并方法与参考依据')),
      node('p', tr('Project-maintained crosswalk using ASJC as the backbone, with compatible finer source categories. Broader evidence does not imply a finer classification. This is not an official crosswalk between rating systems.', '本项目以 ASJC 为层级骨架，融合来源中相容的细分类。上级分类依据不代表来源也给出了细分类；这不是评级机构发布的官方跨体系对照表。')));
    const references = node('ul');
    (taxonomy().sources || []).forEach(source => {
      const item = node('li');
      item.append(node('a', source.name, {href: source.url, target: '_blank', rel: 'noreferrer'}));
      references.append(item);
    });
    method.append(references);
    classification.append(method);
    body.append(classification);
    const legacy = [...new Map((journal.subjects || []).map(value => [String(value).toLocaleLowerCase(), value])).values()];
    if (legacy.length) {
      const auxiliary = node('details', undefined, {class: 'taxonomy-legacy', id: 'legacy-subjects'});
      auxiliary.append(node('summary', tr('Legacy mixed source labels', '旧版混合来源标签（辅助）')), node('p', legacy.join(tr('; ', '；'))));
      body.append(auxiliary);
    }
    if (data.aliases.length) body.append(node('p', tr('Source titles: ', '来源刊名：') + data.aliases.join(tr('; ', '；')), {class: 'source-note'}));
    const history = node('section', undefined, {class: 'history'});
    history.append(node('h3', tr('Sources and history', '来源与历史版本')));
    for (const observation of data.observations) {
      const item = node('article', undefined, {class: 'observation'});
      const top = node('div', undefined, {class: 'obs-top'});
      const location = [observation.source_file, observation.source_sheet,
        tr(`Row ${observation.source_row}`, `第 ${observation.source_row} 行`)].filter(Boolean).join(' / ');
      const edition = observation.edition === 'undated' ? tr('Undated snapshot', '未标年份快照') : observation.edition;
      top.append(node('b', `${observation.system} · ${edition}`), node('small', location));
      item.append(top, node('div', tr('Source title: ', '原刊名：') + observation.title + tr(' · Matched by: ', ' · 匹配方式：') + observation.match_method));
      const chips = node('div', undefined, {class: 'metric-list'});
      const metricChip = (key, value) => {
        const shown = observation.system === 'CAS' && key === 'zone' ? `Q${value}` : metricValue(value);
        const chip = node('span', `${metricName(key)}: ${shown}`);
        let kind = null, helpValue = value;
        if (key === 'rating' && observation.system === 'ABDC') kind = 'abdc';
        if (key === 'rating' && observation.system === 'AJG') kind = 'ajg';
        if (observation.system === 'JCR' && key === 'impact_factor') kind = 'jif';
        if (observation.system === 'JCR' && key === 'categories' && value?.quartile) { kind = 'jcr'; helpValue = value.quartile; }
        if (observation.system === 'SJR' && ['sjr', 'sjr_quartile'].includes(key)) kind = 'sjr';
        if (observation.system === 'CAS' && key === 'zone') { kind = 'cas'; helpValue = shown; }
        if (['SCIE', 'SSCI', 'AHCI', 'ESCI'].includes(observation.system) && key === 'index') kind = observation.system;
        if (['FT50', 'UTD24'].includes(observation.system) && key === 'member') { kind = observation.system.toLowerCase(); helpValue = observation.system; }
        return kind ? explain(chip, kind, helpValue, observation.edition) : chip;
      };
      for (const [key, value] of Object.entries(observation.metrics)) {
        if (value == null || value === '') continue;
        if (Array.isArray(value)) value.forEach(entry => chips.append(metricChip(key, entry)));
        else chips.append(metricChip(key, value));
      }
      item.append(chips);
      if (observation.quality_flags.length) item.append(node('p', tr('Data flags: ', '数据标记：') + observation.quality_flags.join('; '), {class: 'source-note'}));
      const raw = node('details', undefined, {class: 'raw'});
      raw.append(node('summary', tr('View original fields', '查看原始字段')), node('pre', JSON.stringify(observation.raw, null, 2)));
      item.append(raw);
      history.append(item);
    }
    body.append(history);
  }
  async function openDetail(id) {
    const request = ++state.detailRequest;
    state.detailId = id;
    state.detailData = state.details.get(id) || null;
    if (!$('#detail').open) $('#detail').showModal();
    if (state.detailData) { renderDetail(state.detailData); return; }
    $('#detail-title').textContent = tr('Journal details', '期刊详情');
    $('#detail-body').replaceChildren(node('p', tr('Loading sources and history…', '正在加载来源与历史…'), {class: 'loading'}));
    try {
      const response = await fetch('/api/journals/' + encodeURIComponent(id));
      const data = await response.json();
      if (request !== state.detailRequest || !$('#detail').open) return;
      if (!response.ok) throw new Error(data.error || tr('Could not load details.', '无法加载详情。'));
      state.details.set(id, data);
      state.detailData = data;
      renderDetail(data);
    } catch (error) {
      if (request === state.detailRequest) $('#detail-body').replaceChildren(node('p', tr('Could not load details: ', '无法加载详情：') + error.message, {class: 'empty'}));
    }
  }
  function renderMetadata() {
    const data = state.metadata;
    if (!data) return;
    const stats = data.stats;
    $('#statline').textContent = tr(`${stats.journals.toLocaleString()} publications · ${stats.records.toLocaleString()} source records`, `${stats.journals.toLocaleString()} 个刊物 · ${stats.records.toLocaleString()} 条来源记录`);
    const notes = tr(window.JournalI18n.notesEn, data.notes);
    const items = node('ul');
    notes.forEach(note => items.append(node('li', note)));
    $('#notes').replaceChildren(items);
    $('#source-list').replaceChildren(...data.sources.filter(source => !source.duplicate_of).map(source =>
      node('li', `${source.system} ${source.edition} · ${source.filename} · ` + tr(`${source.row_count.toLocaleString()} records`, `${source.row_count.toLocaleString()} 条`))));
    populateTaxonomyControls();
    if (state.status === 'ready' && state.lastData) render(state.lastData);
  }
  async function metadata() {
    try {
      const response = await fetch('/api/meta');
      if (!response.ok) throw new Error();
      state.metadata = await response.json();
      renderMetadata();
    } catch (_) { $('#statline').textContent = tr('Journal catalogue', '期刊数据库'); }
  }
  // Put the primary action before optional filters in both visual and keyboard order.
  $('.workbench').prepend($('#searchform'));
  $('#searchform').addEventListener('submit', event => { event.preventDefault(); load(true); });
  document.querySelectorAll('[data-param]:not(#sort):not(#broad_area):not(#subcategory)').forEach(control => {
    if (control.matches('select,input[type="checkbox"]')) {
      control.addEventListener('change', () => load(true));
    } else {
      control.addEventListener('input', event => {
        clearTimeout(state.debounce);
        if (!event.isComposing) state.debounce = setTimeout(() => load(true), 250);
      });
      control.addEventListener('compositionend', () => {
        clearTimeout(state.debounce);
        state.debounce = setTimeout(() => load(true), 250);
      });
    }
  });
  $('#broad_area').addEventListener('change', () => {
    $('#subcategory').value = '';
    populateTaxonomyControls();
    load(true);
  });
  $('#subcategory').addEventListener('change', () => load(true));
  $('#clear').addEventListener('click', () => {
    document.querySelectorAll('[data-param]').forEach(control => {
      if (control.type === 'checkbox') control.checked = false;
      else control.value = control.id === 'sort' ? 'title' : '';
    });
    populateTaxonomyControls();
    state.sort = 'title'; state.order = 'asc'; load(true);
  });
  document.querySelectorAll('th [data-sort]').forEach(button => button.addEventListener('click', () => {
    state.order = state.sort === button.dataset.sort && state.order === 'asc' ? 'desc' : 'asc';
    state.sort = button.dataset.sort; $('#sort').value = state.sort; load(true);
  }));
  $('#sort').addEventListener('change', event => { state.sort = event.target.value; state.order = 'asc'; load(true); });
  $('#prev').addEventListener('click', () => { state.offset = Math.max(0, state.offset - state.limit); load(); });
  $('#next').addEventListener('click', () => { state.offset += state.limit; load(); });
  $('#close-detail').addEventListener('click', () => $('#detail').close());
  $('#detail').addEventListener('click', event => { if (event.target === $('#detail')) $('#detail').close(); });
  $('#detail').addEventListener('close', () => { state.detailId = null; state.detailData = null; ++state.detailRequest; });
  window.addEventListener('journal-static-progress', event => {
    if (state.status === 'loading') $('#result-summary').textContent = event.detail.message;
  });
  window.addEventListener('journal-locale-change', () => {
    if (state.status === 'ready' && state.lastData) render(state.lastData);
    else if (state.status === 'error') renderError();
    else messageRow(tr('Loading results…', '正在加载结果…'));
    renderMetadata();
    populateTaxonomyControls();
    if ($('#detail').open && state.detailData) renderDetail(state.detailData);
  });
  metadata();
  load();
})();
