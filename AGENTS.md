# 期刊数据库查询入口

先读 [DEV_CONTEXT.md](DEV_CONTEXT.md) 和 [AI_QUERY.md](AI_QUERY.md)。

- 日常查询使用 `python -m journaldb search` / `show`，或只读打开 `data/journals.sqlite`。
- 数据源与不同年份不可混写；本地字段缺失、未匹配本地名单、指标为 0 是不同状态。
- 源文件原件不改，保留每行来源和版本；没有请求时不另存诊断报告、排障记录或运行总结。
- 所有运行结果直接输出到终端；不要默认生成日志文件。
