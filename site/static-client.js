/* Static data adapter for the GitHub Pages build. It deliberately does nothing
   unless the generated site declares window.JOURNAL_STATIC before this file. */
(() => {
  'use strict';
  if (!window.JOURNAL_STATIC) return;

  const assetsURL = new URL('./assets/', window.location.href);
  const nativeFetch = window.fetch.bind(window);
  const cache = { manifest: null, catalogue: null, details: new Map() };
  const msg = (en, zh) => window.JournalI18n?.locale === 'zh' ? zh : en;
  const progress = message => window.dispatchEvent(new CustomEvent('journal-static-progress', { detail: { message } }));
  const abortError = () => new DOMException(msg('Request cancelled.', '请求已取消'), 'AbortError');
  const ensureNotAborted = signal => { if (signal?.aborted) throw abortError(); };
  const jsonResponse = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json; charset=utf-8' } });
  const errorResponse = (message, status = 400) => jsonResponse({ error: message }, status);

  async function gzipJSON(url) {
    if (!('DecompressionStream' in window)) throw new Error(msg('Your browser cannot decompress the data. Please use an up-to-date Chrome, Edge, Firefox or Safari.', '当前浏览器不支持 gzip 数据解压。请使用新版 Chrome、Edge、Firefox 或 Safari。'));
    const response = await nativeFetch(url);
    if (!response.ok) throw new Error(msg(`Could not load the data (${response.status}).`, `无法读取静态数据（${response.status}）`));
    const bytes = await response.arrayBuffer(); const view = new Uint8Array(bytes);
    const text = view[0] === 0x1f && view[1] === 0x8b
      ? await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text()
      : new TextDecoder().decode(bytes);
    return JSON.parse(text);
  }
  function manifest() {
    if (!cache.manifest) {
      progress(msg('Reading data manifest…', '正在读取静态数据目录…'));
      cache.manifest = nativeFetch(new URL('manifest.json', assetsURL)).then(async r => {
        if (!r.ok) throw new Error(msg(`Could not load the data manifest (${r.status}).`, `无法读取数据目录（${r.status}）`));
        return r.json();
      });
    }
    return cache.manifest;
  }
  async function catalogue() {
    if (!cache.catalogue) {
      cache.catalogue = (async () => {
        const m = await manifest(); progress(msg('Loading journals…', '正在加载期刊目录…'));
        const rows = await gzipJSON(new URL(m.catalogue, assetsURL));
        if (!Array.isArray(m.columns) || !Array.isArray(rows)) throw new Error(msg('Invalid data format.', '静态目录格式无效。'));
        const records = rows.map(row => Object.fromEntries(m.columns.map((column, i) => [column, row[i] ?? null])));
        progress(msg(`Loaded ${records.length.toLocaleString()} records.`, `已载入 ${records.length.toLocaleString()} 条本地记录`));
        return records;
      })();
    }
    return cache.catalogue;
  }
  async function journalDetail(id) {
    const shard = String(id).slice(2, 4).toLowerCase();
    if (!/^[0-9a-f]{2}$/.test(shard)) return null;
    if (!cache.details.has(shard)) {
      cache.details.set(shard, (async () => {
        const m = await manifest(); progress(msg('Loading sources and history…', '正在读取来源与历史记录…'));
        return gzipJSON(new URL(`${m.detail_base}${shard}.json.gz`, assetsURL));
      })());
    }
    return (await cache.details.get(shard))[id] || null;
  }
  const asText = value => String(value ?? '').toLocaleLowerCase();
  const normalize = value => asText(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/&/g, ' and ').replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/^the\s+/, '');
  const queryTokens = value => normalize(value).split(/\s+/).filter(Boolean);
  const normalizedISSN = value => String(value ?? '').replace(/[^0-9x]/gi, '').toUpperCase();
  const nullableNumber = (value, name) => {
    if (value === null || value === '') return null;
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) throw new Error(msg(`${name} must be a finite number greater than or equal to 0.`, `${name} 必须是大于或等于 0 的数字。`));
    return number;
  };
  function compare(a, b, key, order, exactTitle) {
    if (key === 'title' && exactTitle) {
      const exactA = normalize(a.title) === exactTitle, exactB = normalize(b.title) === exactTitle;
      if (exactA !== exactB) return exactA ? -1 : 1;
    }
    const av = a[key], bv = b[key]; const missingA = av === null || av === undefined || av === '';
    const missingB = bv === null || bv === undefined || bv === '';
    if (missingA || missingB) return missingA === missingB ? 0 : (missingA ? 1 : -1);
    let result;
    if (key === 'title') {
      const aa = normalize(a.title);
      const bb = normalize(b.title);
      result = aa.localeCompare(bb, 'en');
    } else result = Number(av) - Number(bv);
    return order === 'desc' ? -result : result;
  }
  function booleanParameter(search, name) {
    const value = search.get(name);
    if (value === null || value === '') return null;
    if (value !== '0' && value !== '1') throw new Error(msg(`${name} must be 1 or 0.`, `${name} 只能是 1 或 0。`));
    return value === '1';
  }
  function filterAndSort(records, search) {
    const q = queryTokens(search.get('q'));
    const exact = [['abdc', 'abdc', new Set(['A*', 'A', 'B', 'C'])], ['ajg', 'ajg', new Set(['4*', '4', '3', '2', '1'])], ['cas', 'cas_zone', new Set(['1', '2', '3', '4'])], ['jcr_quartile', 'jcr_quartile', new Set(['Q1', 'Q2', 'Q3', 'Q4'])], ['sjr_quartile', 'sjr_quartile', new Set(['Q1', 'Q2', 'Q3', 'Q4'])], ['source_type', 'source_type', new Set(['journal', 'book series', 'conference and proceedings', 'trade journal'])]];
    const minIF = nullableNumber(search.get('min_if'), msg('Minimum JIF', '最低 JIF'));
    const sort = search.get('sort') || 'title'; const order = search.get('order') || 'asc';
    const ft50 = booleanParameter(search, 'ft50'), utd24 = booleanParameter(search, 'utd24');
    const wosIndex = search.get('wos_index');
    if (wosIndex && !['SCIE', 'SSCI', 'AHCI', 'ESCI'].includes(wosIndex)) throw new Error(msg('Invalid WoS index.', 'WoS 索引参数无效。'));
    if (!['title', 'impact_factor', 'sjr'].includes(sort)) throw new Error(msg('Unsupported sort field.', '不支持的排序字段。'));
    if (!['asc', 'desc'].includes(order)) throw new Error(msg('Sort order must be asc or desc.', '排序方向必须为 asc 或 desc。'));
    exact.forEach(([parameter, , allowed]) => { if (search.get(parameter) && !allowed.has(search.get(parameter))) throw new Error(msg(`Invalid ${parameter} parameter.`, `${parameter} 参数无效。`)); });
    const exactTitle = normalize(search.get('q'));
    let matched = records.filter(record => {
      const text = normalize([record.title, ...(record.normalized_aliases || []), ...(record.issns || []), ...(record.subjects || []), record.search_text || ''].join(' '));
      if (q.length && !q.every(token => /^[0-9X]{8}$/.test(token.toUpperCase()) ? (record.issns || []).some(issn => normalizedISSN(issn) === token.toUpperCase()) : text.includes(token))) return false;
      if (exact.some(([parameter, field]) => search.get(parameter) && String(record[field] ?? '') !== search.get(parameter))) return false;
      if (ft50 !== null && record.ft50 !== ft50) return false;
      if (utd24 !== null && record.utd24 !== utd24) return false;
      if (wosIndex && !(record.wos_indexes || []).includes(wosIndex)) return false;
      if (search.get('subject') && !normalize(record.subjects?.join(' ')).includes(normalize(search.get('subject')))) return false;
      return minIF === null || (record.impact_factor !== null && record.impact_factor !== undefined && Number(record.impact_factor) >= minIF);
    });
    matched = matched.slice().sort((a, b) => compare(a, b, sort, order, exactTitle) || normalize(a.title).localeCompare(normalize(b.title), 'en'));
    return matched;
  }
  async function api(url, signal) {
    ensureNotAborted(signal);
    const path = url.pathname.replace(/\/+$/, '');
    if (path.endsWith('/api/meta')) {
      const m = await manifest();
      return jsonResponse({ stats: m.stats || {}, sources: m.sources || [], notes: m.notes || [] });
    }
    const detail = path.match(/\/api\/journals\/([^/]+)$/);
    if (detail) {
      const found = await journalDetail(decodeURIComponent(detail[1])); ensureNotAborted(signal);
      return found ? jsonResponse(found) : errorResponse(msg('Publication not found.', '未找到该刊物。'), 404);
    }
    if (path.endsWith('/api/journals')) {
      try {
        const records = await catalogue(); ensureNotAborted(signal);
        const all = filterAndSort(records, url.searchParams); const limit = Number(url.searchParams.get('limit') || 50); const offset = Number(url.searchParams.get('offset') || 0);
        if (!Number.isInteger(limit) || limit < 1 || limit > 500 || !Number.isInteger(offset) || offset < 0) throw new Error(msg('Invalid pagination parameters.', '分页参数无效。'));
        return jsonResponse({ results: all.slice(offset, offset + limit), total: all.length, limit, offset });
      } catch (error) { return errorResponse(error.message); }
    }
    return null;
  }
  window.fetch = async (input, init = {}) => {
    const request = input instanceof Request ? input : null;
    const url = new URL(request ? request.url : input, window.location.href);
    const signal = init.signal || request?.signal;
    if (!/\/api\/(?:meta|journals)(?:\/|$)/.test(url.pathname)) return nativeFetch(input, init);
    try { return await api(url, signal); }
    catch (error) {
      if (error.name === 'AbortError') throw error;
      return errorResponse(error.message || msg('Could not read the data.', '静态数据读取失败。'), 500);
    }
  };
  function csvCell(value) {
    let text = Array.isArray(value) ? value.join('; ') : value == null ? '' : String(value);
    if (/^[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  }
  document.addEventListener('click', async event => {
    const link = event.target.closest('#export-link');
    if (!link || link.getAttribute('aria-disabled') === 'true') return;
    event.preventDefault();
    try {
      const url = new URL(link.href, window.location.href); const all = filterAndSort(await catalogue(), url.searchParams); const m = await manifest();
      const columns = (m.columns || []).filter(column => column !== 'search_text' && column !== 'normalized_aliases');
      const output = [columns.join(','), ...all.map(row => columns.map(column => csvCell(row[column])).join(','))].join('\r\n');
      const blob = new Blob(['\ufeff', output], { type: 'text/csv;charset=utf-8' }); const download = document.createElement('a');
      download.href = URL.createObjectURL(blob); download.download = 'journal-index.csv'; document.body.append(download); download.click(); download.remove(); setTimeout(() => URL.revokeObjectURL(download.href), 1000);
    } catch (error) { progress(msg(`Export failed: ${error.message || 'Could not read the data.'}`, `导出失败：${error.message || '静态数据读取失败'}`)); }
  });
})();
