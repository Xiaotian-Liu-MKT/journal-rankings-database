import argparse
import json
import sys

from . import DEFAULT_DB


def main():
    parser = argparse.ArgumentParser(description="本地期刊评级与指标数据库；JSON 输出适合 AI 读取")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 路径")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="从原始文件重建数据库及 CSV/JSONL")
    build.add_argument("--source-dir", default=None)
    query = commands.add_parser("search", help="搜索刊名、ISSN 或学科")
    query.add_argument("q", nargs="?", default="")
    for name in ("abdc", "ajg", "cas", "jcr-quartile", "sjr-quartile", "subject", "broad-area", "subcategory", "source-type", "wos-index", "min-if", "ft50", "utd24"):
        query.add_argument("--" + name)
    query.add_argument("--sort", default="title", choices=("title", "impact_factor", "sjr"))
    query.add_argument("--order", default="asc", choices=("asc", "desc"))
    query.add_argument("--limit", type=int, default=50)
    query.add_argument("--offset", type=int, default=0)
    detail = commands.add_parser("show", help="完整记录、别名、来源、历史评级")
    detail.add_argument("journal_id")
    commands.add_parser("meta", help="来源版本和计数")
    server = commands.add_parser("serve", help="启动真人网页和只读 JSON API")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--open", action="store_true", help="打开默认浏览器")
    args = parser.parse_args()
    try:
        if args.command == "build":
            from .build import build
            from . import ROOT
            build(args.source_dir or ROOT, args.db)
            return
        if args.command == "serve":
            from .server import serve
            serve(args.db, args.port, args.open)
            return
        from .query import connect, search, detail, meta
        con = connect(args.db)
        try:
            if args.command == "search":
                params = vars(args).copy()
                for key in ("db", "command"):
                    params.pop(key)
                result = search(con, **{k: v for k, v in params.items() if v is not None})
            elif args.command == "show":
                result = detail(con, args.journal_id)
                if result is None:
                    raise ValueError("未找到 journal_id")
            else:
                result = meta(con)
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        finally:
            con.close()
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
