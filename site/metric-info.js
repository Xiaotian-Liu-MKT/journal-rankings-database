/* Short, bilingual explanations. Official links describe each evaluation system;
   displayed journal values still come from the supplied local source snapshots. */
(() => {
  'use strict';
  const text = (en, zh) => window.JournalI18n?.locale === 'zh' ? zh : en;
  const sources = {
    abdc: ['ABDC', 'https://abdc.edu.au/abdc-journal-quality-list/'],
    ajg: ['Chartered ABS', 'https://assets.charteredabs.org/ajg-2024-methodology.pdf'],
    jif: ['Clarivate', 'https://clarivate.com/academia-government/blog/closer-look-journal-impact-factor-numerator/'],
    jcr: ['Clarivate', 'https://supportcenter.clarivate.com/s/article/Journal-Citation-Reports-Quartile-rankings-and-other-metrics?language=en_US'],
    sjr: ['SCImago', 'https://www.scimagojr.com/help.php'],
    cas: ['CAS', 'https://www.fenqubiao.com/User/Help.aspx'],
    wos: ['Clarivate', 'https://clarivate.com/academia-government/scientific-and-academic-research/research-discovery-and-referencing/web-of-science/web-of-science-core-collection/content-collection-and-indexing-process/'],
    ft50: ['Financial Times', 'https://www.ft.com/ft50-journals'],
    utd24: ['UT Dallas', 'https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/index.php']
  };
  const indexes = {
    SCIE: ['Science Citation Index Expanded', '自然科学引文索引扩展版', 'Science journal coverage in the Web of Science Core Collection.', 'Web of Science 核心合集中的自然科学期刊索引。'],
    SSCI: ['Social Sciences Citation Index', '社会科学引文索引', 'Social-science journal coverage in the Web of Science Core Collection.', 'Web of Science 核心合集中的社会科学期刊索引。'],
    AHCI: ['Arts & Humanities Citation Index', '艺术与人文引文索引', 'Arts and humanities journal coverage in the Web of Science Core Collection.', 'Web of Science 核心合集中的艺术与人文期刊索引。'],
    ESCI: ['Emerging Sources Citation Index', '新兴来源引文索引', 'A Web of Science Core Collection index for journals meeting its quality-selection criteria.', 'Web of Science 核心合集中的新兴来源索引，期刊须符合其质量遴选标准。']
  };
  function get(type, suppliedValue = '', edition = '') {
    const value = String(suppliedValue ?? '').trim();
    const missing = !value || value === '—';
    let title, description, detail, source = type;
    const unavailable = text('No value was provided or matched in the local snapshot.', '本地快照未提供或未匹配到该值。');
    if (type === 'abdc') {
      const year = edition || '2025';
      title = 'ABDC · ' + year;
      description = text('The Australian Business Deans Council rates business-related journals in four categories: A*, A, B and C.', '澳大利亚商学院院长理事会对商科相关期刊进行分类，依次为 A*、A、B、C。');
      const meanings = {'A*': ['the highest category', '最高类别'], A: ['the second category', '第二类别'], B: ['the third category', '第三类别'], C: ['the fourth category', '第四类别']};
      detail = missing ? unavailable : text(`${value}: ${meanings[value]?.[0] || 'the recorded rating'} in the supplied ${year} list.`, `${value}：所提供的 ${year} 名单中的${meanings[value]?.[1] || '原始评级'}。`);
    } else if (type === 'ajg') {
      title = 'AJG / ABS · ' + (edition || '2024');
      description = text('The Chartered ABS Academic Journal Guide rates business and management journals: 4*, 4, 3, 2 and 1.', '英国 Chartered ABS 的 Academic Journal Guide 对商科与管理学期刊分为 4*、4、3、2、1。');
      const meanings = {'4*': ['a Journal of Distinction', '卓越期刊类别'], '4': ['a leading journal category', '高水平领军期刊类别'], '3': ['a highly regarded journal category', '较高认可度类别'], '2': ['a well-regarded research category', '有认可度的研究期刊类别'], '1': ['recognised research at a more modest level', '有认可度、标准相对较基础的类别']};
      detail = missing ? unavailable : text(`${value}: ${meanings[value]?.[0] || 'the recorded category'} in the supplied guide.`, `${value}：所提供指南中的${meanings[value]?.[1] || '原始类别'}。`);
    } else if (type === 'jif') {
      title = text('JIF · Journal Impact Factor', 'JIF · 期刊影响因子');
      description = text('Clarivate divides citations in an indicator year to the previous two years of journal content by the scholarly items published in those two years.', 'Clarivate 以指标年对前两年期刊内容的引用次数，除以前两年的学术文献数量计算此指标。');
      detail = (missing ? unavailable : text(`Recorded JIF: ${value}. `, `原始 JIF：${value}。`)) + text(' The local header labels this as 2025; that year was not independently verified.', ' 本地表头标注为 2025，该指标年未独立核验。');
    } else if (type === 'jcr') {
      title = text('JCR · JIF quartile', 'JCR · 影响因子分区');
      description = text('Clarivate ranks journals by JIF within a subject category. Q1–Q4 identify successive quarters of that ranking.', 'Clarivate 按期刊在某学科中的 JIF 排名划分四组，Q1–Q4 依次对应四个分位区间。');
      const quarters = {Q1: ['the highest quarter', '最高的约前四分之一'], Q2: ['the second quarter', '第二个四分之一'], Q3: ['the third quarter', '第三个四分之一'], Q4: ['the lowest quarter', '末四分之一']};
      detail = (missing ? unavailable : text(`${value}: ${quarters[value]?.[0] || 'the recorded quartile'}. `, `${value}：${quarters[value]?.[1] || '原始分区'}。`)) + text(' The overview shows the best recorded category; other categories can differ.', ' 概览取本地记录中的最佳分区，不同学科的分区可能不同。');
    } else if (type === 'sjr') {
      title = 'SJR · SCImago Journal Rank';
      description = text('A Scopus-based citation indicator that weights citations by the influence of the citing journals, using a three-year publication window.', '基于 Scopus 数据的引文指标，结合引用来源期刊的影响力加权，采用前三年的发文窗口。');
      detail = (missing ? unavailable : text(`Recorded value: ${value}. `, `原始值：${value}。`)) + text(' Q1 is the highest quarter; Q4 the lowest. The overview shows the best SJR category, separately from JCR.', ' Q1 为最高的四分之一，Q4 为末四分之一。概览显示最佳 SJR 学科分区，与 JCR 分开。');
    } else if (type === 'cas') {
      title = text('CAS · Journal partition', 'CAS · 中科院分区');
      description = text('A separate journal classification from the Chinese Academy of Sciences Library. The local table supplies a zone without major/minor subject details.', '中国科学院文献情报中心的另一套期刊分类；本地源表只有分区，未提供大类或小类学科。');
      const zone = value.match(/[1-4]/)?.[0];
      detail = (zone ? text(`This site displays source zone ${zone} as Q${zone}. `, `本站将源表 ${zone} 区显示为 Q${zone}。`) : unavailable + ' ') + text('This is a display label, not a JCR quartile or a 25% band.', '这是显示标记，不等同于 JCR 四分位，也不代表每区占 25%。');
    } else if (type === 'ft50') {
      title = 'FT50';
      description = text('The Financial Times selects a basket of 50 journals for its business-school research ranking.', '《金融时报》选取的 50 本期刊集合，用于其商学院科研排名。');
      detail = text('This journal matches the supplied FT50 2026 list. Membership is a list flag, not a numeric score or an all-discipline rank.', '该刊匹配所提供的 FT50 2026 名单。这是名单身份，不是数值评分或全学科总排名。');
    } else if (type === 'utd24') {
      title = 'UTD24';
      description = text('UT Dallas tracks publications in 24 business journals to measure business-school research output.', '德州大学达拉斯分校跟踪 24 本商科期刊的论文产出，用于商学院科研产出排名。');
      detail = text('This journal matches the local UTD24 list, checked on 26 July 2026. It is a journal basket, not an individual journal score.', '该刊匹配本地 UTD24 名单，源表检查日期为 2026 年 7 月 26 日。这是期刊集合，不是期刊评分。');
    } else if (indexes[type]) {
      source = 'wos';
      title = type + ' · ' + text(indexes[type][0], indexes[type][1]);
      description = text(indexes[type][2], indexes[type][3]);
      detail = text('This journal matches the supplied undated list. Index membership is coverage, not a quartile or a universal quality score.', '该刊匹配所提供的未标年份名录。索引表示收录身份，不是分区或通用质量评分。');
    } else if (type === 'wos') {
      title = text('WoS · Web of Science indexes', 'WoS · Web of Science 索引');
      description = text('SCIE, SSCI, AHCI and ESCI are indexes in the Web of Science Core Collection.', 'SCIE、SSCI、AHCI、ESCI 是 Web of Science 核心合集中的索引。');
      detail = text('They describe journal coverage. This site uses four supplied undated lists and allows a journal to have multiple indexes.', '它们表示期刊收录范围。本站使用四份未标年份名录，同一本期刊可以属于多个索引。');
    } else return null;
    return {title, description, detail, sourceLabel: sources[source][0], sourceUrl: sources[source][1]};
  }
  window.JournalMetricInfo = {get};
})();
