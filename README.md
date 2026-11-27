# 期刊索引室

**在线使用：[打开期刊索引室](https://xiaotian-liu-mkt.github.io/journal-rankings-database/)**

合并本地期刊评级、指标及 WoS 索引名录。在线版无需安装，也无需启动 Python，支持组合筛选、历史评级、来源详情和 CSV 导出，条目和来源数量显示在网页顶部。

界面采用简洁的白底表格布局，首次打开默认英文。可在右上角切换 English / 中文，浏览器会记住选择；切换语言保留当前查询与筛选，期刊名和原始来源字段保持原文。

筛选实时生效，无需点击 Apply。评级、分区、WoS 索引、出版物类型及学科大类/细分类均可多选；同一项内满足任一所选值即可，不同项之间同时满足。未选择表示不限，选择全部已知等级仍排除缺失评级。大类增加时保留已有细分类，移除时只清除失去所属大类的细分类。可按 SCIE、SSCI、AHCI 或 ESCI 查询对应本地名录中的期刊；这些名录未标注年份，与 JCR 指标年份分别保留。

在具体评级、指标或索引标记上停留约半秒，可查看中英文解释、当前值的含义与官方说明链接。键盘聚焦也可查看，手机可点按打开；浮窗支持关闭和 Esc。

仓库发布代码及 `site/` 静态数据快照。`sources/` 本地原始文件、`data/`（SQLite、CSV/JSONL 导出）不上传 Git。原始资料保留在本地，以下 CLI 命令用于本地完整项目。

## 发布与更新

网页运行于 GitHub Pages，浏览器读取 gzip 压缩概览，并按需读取 256 个详情分片。首次加载后，筛选与排序在浏览器内完成。需要支持 `DecompressionStream` 的现代浏览器。

`main` 分支推送会触发 `.github/workflows/pages.yml` 发布 `site/`。更新本地数据后执行：

```powershell
python -m journaldb build
python -m journaldb.static_export
git add site web journaldb
git commit -m "Update journal data snapshot"
git push
```

网页与本地服务共享 `web/index.html`。`web/static-client.js` 仅在静态导出的页面启用，负责浏览器搜索与 CSV 下载。线上 AI 数据格式见 [静态数据说明](https://xiaotian-liu-mkt.github.io/journal-rankings-database/AI_QUERY.md)。静态站没有独立的 `/api/journals` HTTP 服务；下文 JSON API 用于本地 Python 服务。

## 真人查询

双击 **打开期刊查询.cmd**，或在此目录运行：

```powershell
python -m journaldb serve --open
```

打开 <http://127.0.0.1:8765>。按刊名、ISSN、学科、ABDC、AJG、JCR 最佳分区、SJR 最佳分区、中科院分区、FT50、UTD24 组合筛选。点击刊名查看全部来源、原始字段和历史评级。CSV 导出包含当前筛选的全部结果，不限于当前页。关闭服务窗口或按 Ctrl+C 停止。

已有端口冲突时运行 `python -m journaldb serve --port 8766 --open`。

## AI 与程序查询

命令行默认输出 UTF-8 JSON。Windows 控制台若编码不匹配，先运行 `$env:PYTHONIOENCODING='utf-8'`。

```powershell
python -m journaldb search "Journal of Consumer Research"
python -m journaldb search "0093-5301"
python -m journaldb search --abdc 'A*' --ajg '4*' --ft50 1 --utd24 1
python -m journaldb search --subject Management --min-if 5 --sort impact_factor --order desc
python -m journaldb search --source-type journal --cas 1 --limit 50 --offset 0
python -m journaldb search --wos-index SSCI --abdc 'A*'
python -m journaldb show <journal_id>
python -m journaldb meta
```

SQLite 位于 `data/journals.sqlite`。不启动网页也能直接用 Python `sqlite3`、DB Browser for SQLite、DBeaver 等查询。可分发的平面数据位于 `data/journals.csv`（Excel 可打开）和 `data/journals.jsonl`。CSV/JSONL 是概览，完整历史与原始行保存在 SQLite。

更完整的 AI 操作约定、SQL 示例和字段解释见 [AI_QUERY.md](AI_QUERY.md)。

## 数据来源与含义

| 体系 | 使用的本地文件（位于 `sources/`） | 概览版本 |
|---|---|---|
| JCR / JIF | 2025 Journal Impact Factor.txt；JCR 2026 最新数据（2025 年指标）.txt | 源表头标注 2025，未独立核验 |
| SCImago / SJR | scimagojr 2025.csv | 2025 |
| ABS / AJG | ABS  AJG 2024 完整数据.txt | 2024 |
| ABDC | ABDC-JQL-2025-v3-210926.xlsx | 2025；另保存 2010、2013、2016、2019、2022 历史版 |
| 中科院 | 中科院分区2025完整版.xlsx | 2025 |
| FT50 | FT50.txt | 本地表标注 FT50 2026，有效日期保留在原始字段 |
| UTD24 | UTD24.txt | 本地表检查日期为 2026/7/26 |
| WoS 索引名录 | SCIE.csv、SSCI.csv、AHCI.csv、ESCI.csv | 未标年份快照；四种索引分别保留，允许同刊多索引 |

两份 JCR 文件字节完全相同，只导入一次，在 `sources.duplicate_of` 中保留另一文件的关联。ABDC 一个工作表对应一个来源版本，因此来源版本数大于文件数。

网页学科筛选使用统一的“大类 → 细分类”。以 Scopus ASJC 层级为骨架，融合当前 SJR、AJG、ABDC FoR 与 JCR/WoS 分类；Marketing、MKT 等相容标签合并，宽泛 Business 作为上级依据，跨学科分支保留。映射为本项目维护的 `journaldb/taxonomy_data.json`，不是官方跨体系对照表。只知道大类时不会猜细分类；未提供分类时保留缺失。来源、版次与直接/上级分类证据可在详情追溯，旧混合标签折叠为辅助信息。

CLI/API 使用 `--broad-area area-1400 --subcategory asjc-1406` / `broad_area=area-1400&subcategory=asjc-1406` 查询市场营销。可选节点见 `meta.taxonomy.nodes`，每个所选细分类须属于所选大类之一；多选大类与细分类必须在同一分类路径匹配。旧 `--subject` 兼容混合标签关键词查询。

JCR 与 SJR 的概览分区均为各自的最佳分区，不可互换；JCR 的各个学科及名次保存在详情 `metrics.categories`。统一学科与最佳分区分别保留，不能据此把最佳分区归给指定学科。

中科院原表没有学科或大类/小类字段，保存为“源表分区”，不做推断。SCImago 包含非期刊类型，默认全部保留；只查 SJR 标注的期刊可筛选 `source_type=journal`。该类型字段仅来自 SJR，使用类型筛选会排除没有 SJR 类型数据的条目。

网页中 CAS 的原始 1–4 分区按用户偏好显示为 Q1–Q4，数据库与 API 仍保留原始数值；CAS、JCR、SJR 三套指标分别存储。

空值表示本地没有当前数据、源字段缺失或当前来源值冲突。不会用历史 ABDC 评级冒充当前评级，也不会把缺失值改为零。FT50/UTD24 为 false 仅表示未匹配本地名单，不是对官方收录状态的判断。

## 合并及溯源

- 校验 ISSN 的格式和校验位，保留前导零；去掉空白、连字符差异和隐藏的方向格式符。无效 ISSN 保留在原始字段和质量标记中，不作为自动合并依据。
- 优先按有效 ISSN 关联，再使用标准化的完整刊名。刊名标准化仅处理大小写、标点、重音、空白、开头的 The、&/and。
- 同名且双方已知 ISSN 完全不相交时先保持独立。后续记录若用有效 ISSN 桥接且所有候选有相同标准化刊名，可合并。冲突或歧义保留 `quality_flags`。
- 不做模糊匹配。仅对 UTD 名单中的 `Journal on Computing` 和 `M&SOM-MANUFACTURING & SERVICE OPERATIONS MANAGEMENT` 设置两条显式本地别名，且目标必须唯一。
- 同版同刊的指标若不一致，概览该字段留空，原始观察值仍全部保留。身份合并不代表确认各源原始数据都准确。
- 每条来源记录均保留文件名、SHA-256、工作表、行号、原刊名、匹配方法、规范指标、原始字段。原始行号是解析后的 CSV 记录序号或 Excel 行号。
- `journal_id` 是给定导入快照的可重复 ID；更新源文件内容后可能改变。跨版本关联优先使用 ISSN 与来源位置。

## 接口与维护

服务只监听 `127.0.0.1`，不需要账户、API key 或云服务。接口均为只读：

```text
GET /api/journals?q=marketing&abdc=A%2A&limit=50&offset=0
GET /api/journals/{journal_id}
GET /api/meta
GET /api/export.csv?ft50=1
```

筛选参数与 CLI 同名（连字符换成下划线）。九个多选参数 `abdc|ajg|cas|jcr_quartile|sjr_quartile|wos_index|source_type|broad_area|subcategory` 可重复传入，例如 `--abdc A* --abdc A` 或 `abdc=A%2A&abdc=A`；兼容单值及逗号分隔值，Python 查询接口也接受列表/元组。`ft50`/`utd24` 接受 `1` 或 `0`。`limit` 为 1–500。排序字段为 `title|abdc|ajg|wos_indexes|lists|impact_factor|jcr_quartile|sjr|cas_zone|subcategory`，方向 `order=asc|desc`。网页点击表头切换升降序。评级/分区的 asc 为最好等级在前，数值按大小排序；缺失在两种方向均最后；名单按本地命中数量、WoS/细分类按名称组合排序。CSV 沿用筛选和排序条件。

首次在另一台机器重建需要 Python 3.10+、带 FTS5 和 JSON1 的 SQLite，以及 `openpyxl`：

```powershell
python -m pip install -r requirements.txt
python -m journaldb build
python -m unittest discover -s tests -v
```

网页、CLI、API 日常查询仅使用 Python 标准库。原始文件名与表头是当前导入合同；替换为新版本时同步调整 `journaldb/build.py` 中来源识别及版本配置，再重建。构建先写临时库，成功后替换正式库。运行中的服务查询按请求重新打开数据库。

## 网页标志

当前页眉与 favicon 使用用户提供的冰霜熊猫帝王场景图：`web/brand/panda-emperor.png`，发布副本为 `site/brand/panda-emperor.png`。原图原样复制，通过页面布局与渐变衔接融入浅冰蓝页眉。

先前的透明徽标保留在 `web/brand/panda-throne.png`（发布副本同名），使用内置 image_gen 生成，保留原始透明通道。

生成提示词（原文）：

> 为期刊查询网页设计原创 logo：一只黑白熊猫正面端坐冰晶王座，背后冰晶与风纹环绕。简洁的矢量感插画，深蓝轮廓、冰蓝点缀，熊猫与王座在56px小尺寸仍清晰，构图紧凑。图标之外真正透明，冰与风属于图标内部背景。无文字、无水印，无皇冠、武器或额外角色。
