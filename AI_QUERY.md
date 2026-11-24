# AI 查询约定

工作目录：`E:/GitHub/期刊分区表`。先查数据库，不要每次重新解析 Excel，也不要凭模型记忆声称本地值是最新官方值。

## 推荐流程

1. 用 `python -m journaldb search "刊名、缩写或ISSN"` 查候选。支持从来源刊名生成的首字母缩写（如 `ejm` → European Journal of Marketing），忽略大小写，可省略 of/and/the 等连接词，也接受 `E.J.M.`。默认排序依次优先完整标准化刊名、完整缩写，再按刊名排列；其余检索支持词项前缀及原文子串。缩写可能对应多本刊物，保留全部候选，不用于实体合并，也不作为官方别名。
2. 查询返回多个候选时先核对 ISSN、别名、出版类型与来源。按 ISSN 查询也可能返回多个有歧义的条目，不能任意取第一条。
3. 对选中 `journal_id` 运行 `python -m journaldb show <id>`，核对版次与质量标记，读取各学科分区、原始名次和历史评级。
4. 给用户回答时标注体系、版次和本地来源；例如“ABDC 2025：A*；AJG 2024：4*”。JCR 指标年须写“源表标注 2025，未独立核验”。

`search` 不支持自然语言条件解析。AI 应把“ABDC A* 且 UTD24”转换成 `--abdc 'A*' --utd24 1`；把“影响因子至少5”转换成 `--min-if 5`。未知评级、空值和名单 false 不等同于零。

排序支持 `title`、`abdc`、`ajg`、`wos_indexes`、`lists`、`impact_factor`、`jcr_quartile`、`sjr`、`cas_zone`、`subcategory`，方向为 `asc`/`desc`，两个方向均将缺失放最后。ABDC/AJG/JCR/CAS 按等级排序（asc 最好在前）；名单按本地 FT50/UTD24 命中数量排序，0 为有效值；WoS 按索引名称组合、细分类按全部英文细分类名称组合排序。细分类不由大类回填。分页与 CSV 导出使用同一排序条件。

## 统一学科分类

网页使用一套统一的两层分类，CLI/API 对应 `--broad-area` / `broad_area` 和 `--subcategory` / `subcategory`。例如 `python -m journaldb search --broad-area area-1400 --subcategory asjc-1406` 查询市场营销。节点 ID 与双语标签见 `meta.taxonomy.nodes`；大类查询包含该大类直接归属和全部细分类，细分类查询只命中有明确细分类依据的条目。父子参数必须来自同一分支。

分类以 Scopus ASJC 层级为骨架，融合 SJR、AJG 2024、ABDC 2025 的 ANZSRC 2020 FoR，以及 JCR/WoS 标签。`journaldb/taxonomy_data.json` 是版本化的本项目映射，跨体系关系不宣称为官方对照表。相容的宽类被细类替代展示，真实多学科分支保留；不从刊名、宽泛学科或历史版次推断更细归属。

`taxonomy_paths` 是当前统一分类路径与逐项来源依据。每条证据的 `relation=direct` 支持该节点，`broader` 只支持上级范围，不能解读为该来源也给出了细分类。`subjects` 继续保留旧版混合标签作为辅助数据；旧 `--subject` 仍为兼容性关键词检索，网页不再将它作为分类筛选。学科标签与 JCR 最佳分区是独立字段，查“某学科 Q1”仍须配对核对来源类别与分区。

## 数据表

| 表 / 视图 | 用途 |
|---|---|
| catalogue / journal_overview | 每刊一行的当前概览；快速组合筛选 |
| journals | 刊物实体与显示刊名 |
| identifiers | 有效 ISSN；与期刊是多对多关系，允许源歧义 |
| aliases | 来源中的所有刊名写法与标准化值 |
| observations | 每个源数据行，含 metrics、raw、quality_flags JSON |
| sources | 文件、SHA-256、体系、版次、指标年、行数、duplicate_of |
| journal_search | FTS5 搜索索引 |
| metadata | schema_version、built_at |

`catalogue.issns`、`subjects`、`quality_flags` 为 JSON 数组文本。`ft50`、`utd24` 为 0/1；`cas_top` 为可空 0/1。所有缺失数值使用 SQL NULL。`abdc_year` 等字段指本地概览使用的来源版次。

`jcr_quartile` 与 `sjr_quartile` 均为最佳分区。若用户问“某学科 Q1”，必须展开 JCR `categories` 并将学科与同一对象的分区配对。不要用跨学科最佳分区作答。

`wos_indexes` 是 SCIE/SSCI/AHCI/ESCI 四份新名录的匹配结果，`languages` 为来源提供的出版语言，两者均为 JSON 数组。用 `python -m journaldb search --wos-index SSCI` 或 API `wos_index=SSCI` 进行精确索引筛选。四份名录没有源年份，edition=`undated`、metric_year=NULL；不得用 JCR 2025 年字段替这些名单推断年份。空数组仅表示未匹配本地名录。

网页按用户偏好将 CAS 原始分区 1–4 显示为 Q1–Q4；数据库 `cas_zone` 与 `cas` 筛选参数仍为 1–4。这是 CAS 的显示映射，与 JCR/SJR 各自的分区体系分别保留。

## Python / SQL 示例

```python
import sqlite3
from pathlib import Path

db = Path('data/journals.sqlite').resolve()
con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
con.row_factory = sqlite3.Row
rows = con.execute('''
    SELECT title, issns, abdc, abdc_year, ajg, ajg_year, ft50, utd24
    FROM journal_overview
    WHERE abdc=? AND utd24=1
    ORDER BY title
''', ('A*',)).fetchall()
print([dict(r) for r in rows])
con.close()
```

查询某个学科的实际 JCR 分区（同一类别对象，避免跨类别错配）：

```sql
SELECT c.title, s.edition, s.metric_year,
       json_extract(cat.value,'$.category') AS category,
       json_extract(cat.value,'$.quartile') AS quartile,
       json_extract(cat.value,'$.rank') AS category_rank,
       s.filename, o.source_row
FROM observations o
JOIN sources s USING(source_id)
JOIN catalogue c USING(journal_id)
JOIN json_each(o.metrics,'$.categories') cat
WHERE s.system='JCR'
  AND json_extract(cat.value,'$.category')='MANAGEMENT'
  AND json_extract(cat.value,'$.quartile')='Q1';
```

查询历史 ABDC（不要只查概览）：

```sql
SELECT s.edition, json_extract(o.metrics,'$.rating') AS rating,
       o.title, s.filename, o.source_sheet, o.source_row
FROM observations o JOIN sources s USING(source_id)
WHERE o.journal_id=? AND s.system='ABDC'
ORDER BY s.metric_year DESC;
```

完整原始指标可从 `observations.raw` 获取，包括 SCImago 的发文数、引文数、覆盖年份、重复 Publisher 列（第二列保留为 `Publisher__2`）和 FT50 有效日期。概览 CSV/JSONL 不包含这些细节。

## 质量边界

`quality_flags` 中 `invalid_issn:*` 为源值格式或校验位问题；`same_title_disjoint_issn`、`ambiguous_title`、`multiple_issn_candidates` 表示身份匹配遇到差异；`conflicting_current_value:*` 表示当前同源同字段冲突。详情的原始记录可用于进一步人工核对。标记是本地处理结果，不能替代官方数据核验。

未经明确授权，不修改原始源文件，不创建诊断报告文件。查询本地资料不需要联网；用户要求最新官方信息或核实时，再单独执行在线核验。
