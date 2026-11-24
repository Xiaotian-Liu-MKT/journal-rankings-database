# 期刊索引室静态数据接口

网页在 GitHub Pages 完全由浏览器运行，无独立搜索服务器。
所有数据保持源文件的版次含义，不代表已独立核验的最新官方数据。

- `assets/manifest.json`：字段顺序、来源、数据版本、统计。
- `assets/catalogue.json.gz`：gzip JSON 二维数组，按 manifest.columns 映射为对象。
- `assets/details/{前两位ID}.json.gz`：完整详情分片。ID 为 j_abc... 时分片为 ab。
- 浏览器界面提供组合查询与 CSV 下载。静态站不提供 /api/journals HTTP 服务。
- 支持刊名首字母缩写（如 ejm），忽略大小写及连接词；缩写重名时保留全部候选。search_acronyms 为派生检索值，不是官方别名。
- manifest.taxonomy 提供统一学科节点；概览 taxonomy_paths 包含大类、细分类与 direct/broader 来源证据。网页按 broad_area/subcategory 筛选，subjects 仅作旧版辅助标签。映射以ASJC为骨架，由本项目归并AJG、ABDC FoR、SJR与JCR/WoS，不是官方跨体系对照表；不由宽类猜细类。

Python 读取当前站点数据（BASE 替换为该页面所在目录的 HTTPS 地址）：

```python
import gzip, json
from urllib.request import urlopen
BASE = 'https://xiaotian-liu-mkt.github.io/journal-rankings-database/'
manifest = json.load(urlopen(BASE + 'assets/manifest.json'))
payload = gzip.decompress(urlopen(BASE + 'assets/' + manifest['catalogue']).read())
records = [dict(zip(manifest['columns'], row)) for row in json.loads(payload)]
print([r for r in records if r['abdc']=='A*' and r['utd24']])
jid = next(r['journal_id'] for r in records if r['title']=='JOURNAL OF CONSUMER RESEARCH')
detail_url = BASE + 'assets/details/' + jid[2:4] + '.json.gz'
detail = json.loads(gzip.decompress(urlopen(detail_url).read()))[jid]
print(detail['observations'])
```

保留空值、0、False 的差别。JCR 学科分区见同一 categories 对象，不能将最佳分区归给所有学科。
`wos_indexes` 为 SCIE/SSCI/AHCI/ESCI 四份未标年份名录的匹配数组；`languages` 为出版语言。
四份名录的 edition 为 undated、metric_year 为 null，与 JCR 指标年份分开。空数组仅表示未匹配本地名录。
