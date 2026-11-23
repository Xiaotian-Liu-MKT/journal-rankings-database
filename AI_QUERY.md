# AI 查询约定

工作目录：`E:/GitHub/期刊分区表`。先查数据库，不要每次重新解析 Excel，也不要凭模型记忆声称本地值是最新官方值。

## 推荐流程

1. 用 `python -m journaldb search "刊名或ISSN"` 查候选。默认排序时，完整标准化刊名匹配优先；其余检索支持词项前缀及原文子串。
2. 查询返回多个候选时先核对 ISSN、别名、出版类型与来源。按 ISSN 查询也可能返回多个有歧义的条目，不能任意取第一条。
3. 对选中 `journal_id` 运行 `python -m journaldb show <id>`，核对版次与质量标记，读取各学科分区、原始名次和历史评级。
4. 给用户回答时标注体系、版次和本地来源；例如“ABDC 2025：A*；AJG 2024：4*”。JCR 指标年须写“源表标注 2025，未独立核验”。

`search` 不支持自然语言条件解析。AI 应把“ABDC A* 且 UTD24”转换成 `--abdc 'A*' --utd24 1`；把“影响因子至少5”转换成 `--min-if 5`。未知评级、空值和名单 false 不等同于零。

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
