#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  万能数据库查询脚本 - SQL Server & Redis
  Universal Database Query Tool
================================================================================
  支持功能:
    SQL Server: 查询/插入/更新/删除/统计/列出表/列出字段/导出CSV
    Redis:      GET/SET/DEL/KEYS/SCAN/TTL/TYPE/HGET/HSET/LRANGE/SMEMBERS/
                ZRANGE/统计/导出/批量删除

  依赖安装:
    pip install pyodbc redis colorama

  用法示例:
    python db_universal.py sqlserver --help
    python db_universal.py redis --help
================================================================================
"""

import argparse
import sys
import os
import json
import csv
import re
from datetime import datetime

# ──────────────────────────────────────────────
# 颜色输出（可选）
# ──────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    def ok(s):   return f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    def err(s):  return f"{Fore.RED}{s}{Style.RESET_ALL}"
    def warn(s): return f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    def info(s): return f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    def bold(s): return f"{Style.BRIGHT}{s}{Style.RESET_ALL}"
except ImportError:
    def ok(s):   return s
    def err(s):  return s
    def warn(s): return s
    def info(s): return s
    def bold(s): return s


# ──────────────────────────────────────────────
# 依赖检查
# ──────────────────────────────────────────────
def check_dep(pkg, import_name=None):
    import importlib
    name = import_name or pkg
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        print(err(f"[缺少依赖] 请先安装: pip install {pkg}"))
        return False


# ══════════════════════════════════════════════
#  SQL Server 模块
# ══════════════════════════════════════════════

def get_sqlserver_conn(args):
    if not check_dep("pyodbc"):
        sys.exit(1)
    import pyodbc

    driver = args.driver or "ODBC Driver 17 for SQL Server"
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={args.host},{args.port}",
        f"DATABASE={args.database}",
    ]
    if args.trusted:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={args.user}")
        parts.append(f"PWD={args.password}")
    if args.encrypt:
        parts.append("Encrypt=yes;TrustServerCertificate=yes")

    conn_str = ";".join(parts)
    try:
        conn = pyodbc.connect(conn_str, timeout=args.timeout)
        print(ok(f"[OK] 已连接 SQL Server => {args.host}:{args.port}/{args.database}"))
        return conn
    except Exception as e:
        print(err(f"[连接失败] {e}"))
        sys.exit(1)


def print_table(columns, rows, max_col_width=40):
    """美化打印结果表格"""
    if not rows:
        print(warn("  (无数据)"))
        return
    col_widths = [len(str(c)) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            s = str(val) if val is not None else "NULL"
            col_widths[i] = min(max_col_width, max(col_widths[i], len(s)))

    header = "  " + " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(columns))
    sep    = "  " + "-+-".join("-" * w for w in col_widths)
    print(bold(header))
    print(sep)
    for row in rows:
        line_vals = []
        for i, val in enumerate(row):
            s = "NULL" if val is None else str(val)
            if len(s) > max_col_width:
                s = s[:max_col_width - 3] + "..."
            line_vals.append(s.ljust(col_widths[i]))
        print("  " + " | ".join(line_vals))


def export_csv(columns, rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows(rows)
    print(ok(f"[导出] 已保存到 {path}  ({len(rows)} 行)"))


# ── SQL Server 子命令 ──────────────────────────

def ss_query(conn, args):
    """执行任意 SQL 语句"""
    sql = args.sql
    if args.top and "select" in sql.lower() and "top" not in sql.lower():
        sql = re.sub(r"(?i)^(SELECT)", f"SELECT TOP {args.top}", sql, count=1)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(args.limit) if args.limit else cur.fetchall()
            print(info(f"\n[结果] 返回 {len(rows)} 行，字段数 {len(cols)}"))
            print_table(cols, rows)
            if args.export:
                export_csv(cols, rows, args.export)
        else:
            conn.commit()
            print(ok(f"[OK] 执行成功，影响行数: {cur.rowcount}"))
    except Exception as e:
        print(err(f"[SQL错误] {e}"))


def ss_list_tables(conn, args):
    """列出所有表并统计行数"""
    cur = conn.cursor()
    schema_filter = f"AND t.TABLE_SCHEMA = '{args.schema}'" if getattr(args, "schema", None) else ""
    cur.execute(f"""
        SELECT t.TABLE_SCHEMA, t.TABLE_NAME, t.TABLE_TYPE,
               ISNULL(p.rows, 0) AS RowCount
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN sys.tables st ON st.name = t.TABLE_NAME
        LEFT JOIN sys.partitions p
            ON p.object_id = st.object_id AND p.index_id IN (0, 1)
        WHERE t.TABLE_CATALOG = DB_NAME() {schema_filter}
        ORDER BY t.TABLE_SCHEMA, t.TABLE_TYPE, t.TABLE_NAME
    """)
    rows = cur.fetchall()
    cols = ["Schema", "Table Name", "Type", "Row Count"]
    print(info(f"\n[表列表] 共 {len(rows)} 个对象"))
    print_table(cols, rows)


def ss_desc_table(conn, args):
    """查看表字段结构"""
    cur = conn.cursor()
    cur.execute("""
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            ISNULL(CAST(c.CHARACTER_MAXIMUM_LENGTH AS VARCHAR), '') AS MaxLen,
            c.IS_NULLABLE,
            ISNULL(c.COLUMN_DEFAULT, '') AS DefaultVal,
            ISNULL(CAST(ep.value AS NVARCHAR(500)), '') AS Comment,
            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'YES' ELSE '' END AS IsPK
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN sys.columns sc
            ON sc.name = c.COLUMN_NAME
            AND sc.object_id = OBJECT_ID(?)
        LEFT JOIN sys.extended_properties ep
            ON ep.major_id = sc.object_id
            AND ep.minor_id = sc.column_id
            AND ep.name = 'MS_Description'
        LEFT JOIN (
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' AND ku.TABLE_NAME = ?
        ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
        WHERE c.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
    """, args.table, args.table, args.table)
    rows = cur.fetchall()
    cols = ["字段名", "类型", "最大长度", "可空", "默认值", "注释", "主键"]
    print(info(f"\n[表结构] {args.table}  共 {len(rows)} 个字段"))
    print_table(cols, rows)


def ss_count(conn, args):
    """统计表行数（支持 WHERE 条件）"""
    schema = getattr(args, "schema", None)
    table  = f"[{schema}].[{args.table}]" if schema else f"[{args.table}]"
    where  = f"WHERE {args.where}" if getattr(args, "where", None) else ""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table} {where}")
    cnt = cur.fetchone()[0]
    print(info(f"\n[统计] {table} {where}"))
    print(f"  行数: {cnt:,}")


def ss_sample(conn, args):
    """取样查询（前N条 / 随机N条）"""
    schema = getattr(args, "schema", None)
    table  = f"[{schema}].[{args.table}]" if schema else f"[{args.table}]"
    fields = getattr(args, "fields", None) or "*"
    where  = f"WHERE {args.where}" if getattr(args, "where", None) else ""
    order  = f"ORDER BY {args.order_by}" if getattr(args, "order_by", None) else ""
    n = args.limit or 20

    if getattr(args, "random", False):
        sql = f"SELECT TOP {n} {fields} FROM {table} {where} ORDER BY NEWID()"
    else:
        sql = f"SELECT TOP {n} {fields} FROM {table} {where} {order}"

    cur = conn.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print(info(f"\n[取样] {table}  返回 {len(rows)} 行"))
        print_table(cols, rows)
        if getattr(args, "export", None):
            export_csv(cols, rows, args.export)
    except Exception as e:
        print(err(f"[错误] {e}"))


def ss_distinct(conn, args):
    """查看某字段的不重复值及出现次数"""
    schema = getattr(args, "schema", None)
    table  = f"[{schema}].[{args.table}]" if schema else f"[{args.table}]"
    field  = args.field
    where  = f"WHERE {args.where}" if getattr(args, "where", None) else ""
    limit  = args.limit or 100
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT TOP {limit} [{field}], COUNT(*) AS cnt
            FROM {table} {where}
            GROUP BY [{field}]
            ORDER BY cnt DESC
        """)
        cols = [field, "count"]
        rows = cur.fetchall()
        print(info(f"\n[不重复值] {table}.{field}  共 {len(rows)} 种值"))
        print_table(cols, rows)
    except Exception as e:
        print(err(f"[错误] {e}"))


def ss_search(conn, args):
    """在表的所有文本字段中搜索关键词"""
    table   = args.table
    keyword = args.keyword
    cur     = conn.cursor()
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND DATA_TYPE IN
        ('char','varchar','nchar','nvarchar','text','ntext')
    """, table)
    text_cols = [r[0] for r in cur.fetchall()]
    if not text_cols:
        print(warn("该表无文本类字段"))
        return
    conditions = " OR ".join([f"[{c}] LIKE ?" for c in text_cols])
    params = [f"%{keyword}%"] * len(text_cols)
    limit  = args.limit or 50
    try:
        cur.execute(f"SELECT TOP {limit} * FROM [{table}] WHERE {conditions}", params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print(info(f"\n[搜索] 关键词 '{keyword}' 在 {table} 中，命中 {len(rows)} 行"))
        print_table(cols, rows)
    except Exception as e:
        print(err(f"[错误] {e}"))


def ss_indexes(conn, args):
    """列出表的所有索引"""
    cur = conn.cursor()
    cur.execute("""
        SELECT
            i.name           AS IndexName,
            i.type_desc      AS IndexType,
            CASE i.is_unique WHEN 1 THEN 'YES' ELSE 'NO' END AS IsUnique,
            CASE i.is_primary_key WHEN 1 THEN 'YES' ELSE 'NO' END AS IsPK,
            (
                SELECT STRING_AGG(c2.name, ', ') WITHIN GROUP (ORDER BY ic2.key_ordinal)
                FROM sys.index_columns ic2
                JOIN sys.columns c2
                    ON ic2.object_id = c2.object_id AND ic2.column_id = c2.column_id
                WHERE ic2.object_id = i.object_id AND ic2.index_id = i.index_id
            ) AS Columns
        FROM sys.indexes i
        WHERE i.object_id = OBJECT_ID(?) AND i.name IS NOT NULL
        ORDER BY i.is_primary_key DESC, i.name
    """, args.table)
    rows = cur.fetchall()
    cols = ["索引名", "类型", "唯一", "主键", "字段"]
    print(info(f"\n[索引] {args.table}"))
    print_table(cols, rows)


def ss_db_info(conn, args):
    """查看数据库整体信息"""
    cur = conn.cursor()
    cur.execute("""
        SELECT
            DB_NAME()  AS DatabaseName,
            @@VERSION  AS SQLVersion,
            (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE') AS TableCount,
            (SELECT COUNT(*) FROM INFORMATION_SCHEMA.VIEWS) AS ViewCount,
            (SELECT SUM(CAST(size AS BIGINT)) * 8 / 1024
             FROM sys.database_files WHERE type_desc='ROWS') AS DataSizeMB
    """)
    row = cur.fetchone()
    print(info("\n[数据库信息]"))
    labels = ["数据库名", "SQL 版本", "表数量", "视图数量", "数据大小(MB)"]
    for label, val in zip(labels, row):
        print(f"  {label:<16}: {val}")


def handle_sqlserver(args):
    if not getattr(args, "password", None) and not getattr(args, "trusted", False):
        args.password = os.environ.get("SS_PASSWORD", "")

    conn = get_sqlserver_conn(args)
    cmd  = args.ss_cmd

    if   cmd == "query":    ss_query(conn, args)
    elif cmd == "tables":   ss_list_tables(conn, args)
    elif cmd == "desc":     ss_desc_table(conn, args)
    elif cmd == "count":    ss_count(conn, args)
    elif cmd == "sample":   ss_sample(conn, args)
    elif cmd == "distinct": ss_distinct(conn, args)
    elif cmd == "search":   ss_search(conn, args)
    elif cmd == "indexes":  ss_indexes(conn, args)
    elif cmd == "dbinfo":   ss_db_info(conn, args)
    else:
        print(err(f"未知子命令: {cmd}"))

    conn.close()


# ══════════════════════════════════════════════
#  Redis 模块
# ══════════════════════════════════════════════

def get_redis_conn(args):
    if not check_dep("redis"):
        sys.exit(1)
    import redis

    try:
        kwargs = dict(
            host=args.host,
            port=args.port,
            db=args.db,
            password=args.password or os.environ.get("REDIS_PASSWORD") or None,
            decode_responses=True,
            socket_connect_timeout=args.timeout,
            socket_timeout=args.timeout,
        )
        if getattr(args, "ssl", False):
            kwargs["ssl"] = True
        r = redis.Redis(**kwargs)
        r.ping()
        print(ok(f"[OK] 已连接 Redis => {args.host}:{args.port} db={args.db}"))
        return r
    except Exception as e:
        print(err(f"[连接失败] {e}"))
        sys.exit(1)


def redis_key_detail(r, key):
    """打印单个 key 详情（自动识别类型）"""
    ktype = r.type(key)
    ttl   = r.ttl(key)
    ttl_s = f"{ttl}s" if ttl >= 0 else ("永不过期" if ttl == -1 else "已过期/不存在")

    print(info(f"\n  Key  : {key}"))
    print(f"  Type : {ktype}")
    print(f"  TTL  : {ttl_s}")

    if ktype == "string":
        val = r.get(key)
        print(f"  Value: {val}")
    elif ktype == "hash":
        data = r.hgetall(key)
        print(f"  Fields ({len(data)}):")
        for k, v in list(data.items())[:30]:
            print(f"    {k}: {v}")
    elif ktype == "list":
        length = r.llen(key)
        items  = r.lrange(key, 0, 29)
        print(f"  Length: {length}")
        for i, v in enumerate(items):
            print(f"    [{i}] {v}")
    elif ktype == "set":
        card  = r.scard(key)
        items = list(r.smembers(key))[:30]
        print(f"  Members ({card}):")
        for v in items:
            print(f"    {v}")
    elif ktype == "zset":
        card  = r.zcard(key)
        items = r.zrange(key, 0, 29, withscores=True)
        print(f"  Members ({card}):")
        for v, score in items:
            print(f"    score={score}  {v}")
    elif ktype == "stream":
        length = r.xlen(key)
        print(f"  Stream Length: {length}")
    else:
        print(f"  (未知类型: {ktype})")


def r_get(r, args):
    redis_key_detail(r, args.key)


def r_set(r, args):
    kwargs = {}
    if getattr(args, "ex", None):  kwargs["ex"] = args.ex
    if getattr(args, "px", None):  kwargs["px"] = args.px
    if getattr(args, "nx", False): kwargs["nx"] = True
    if getattr(args, "xx", False): kwargs["xx"] = True
    result = r.set(args.key, args.value, **kwargs)
    print(ok(f"[SET] {args.key} = {args.value}  =>  {result}"))


def r_del(r, args):
    keys = args.keys
    n = r.delete(*keys)
    print(ok(f"[DEL] 已删除 {n} 个 key"))


def r_keys(r, args):
    pattern = getattr(args, "pattern", None) or "*"
    keys    = r.keys(pattern)
    limit   = getattr(args, "limit", None) or 200
    print(info(f"\n[KEYS] 匹配 '{pattern}'，共 {len(keys)} 个（显示前 {min(len(keys), limit)} 个）"))
    for k in keys[:limit]:
        ktype = r.type(k)
        ttl   = r.ttl(k)
        print(f"  {k:<50}  type={ktype:<8}  ttl={ttl}")


def r_scan(r, args):
    pattern    = getattr(args, "pattern", None) or "*"
    count      = getattr(args, "scan_count", None) or 100
    limit      = getattr(args, "limit", None) or 500
    cursor     = 0
    result     = []
    print(info(f"\n[SCAN] 匹配 '{pattern}'，批次={count}，最多 {limit} 个"))
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=count)
        result.extend(keys)
        if cursor == 0 or len(result) >= limit:
            break
    for k in result[:limit]:
        ktype = r.type(k)
        ttl   = r.ttl(k)
        print(f"  {k:<50}  type={ktype:<8}  ttl={ttl}")
    print(info(f"  共扫描到 {len(result)} 个 key"))


def r_hget(r, args):
    field = getattr(args, "field", None)
    if field:
        val = r.hget(args.key, field)
        print(f"  {args.key}[{field}] = {val}")
    else:
        data = r.hgetall(args.key)
        print(info(f"\n[HGETALL] {args.key}  共 {len(data)} 个字段"))
        for k, v in data.items():
            print(f"  {k}: {v}")


def r_hset(r, args):
    n = r.hset(args.key, args.field, args.value)
    print(ok(f"[HSET] {args.key}[{args.field}] = {args.value}  =>  新增字段数 {n}"))


def r_list_ops(r, args):
    op = args.list_op
    if op == "lrange":
        start = getattr(args, "start", None) or 0
        stop  = args.stop if getattr(args, "stop", None) is not None else -1
        items = r.lrange(args.key, start, stop)
        print(info(f"\n[LRANGE] {args.key}[{start}:{stop}]  共 {len(items)} 个元素"))
        for i, v in enumerate(items):
            print(f"  [{start + i}] {v}")
    elif op == "llen":
        print(f"  {args.key} 列表长度: {r.llen(args.key)}")
    elif op == "lpush":
        n = r.lpush(args.key, *(args.values or []))
        print(ok(f"[LPUSH] => 列表长度 {n}"))
    elif op == "rpush":
        n = r.rpush(args.key, *(args.values or []))
        print(ok(f"[RPUSH] => 列表长度 {n}"))


def r_set_ops(r, args):
    op = args.set_op
    if op == "smembers":
        members = r.smembers(args.key)
        print(info(f"\n[SMEMBERS] {args.key}  共 {len(members)} 个成员"))
        for v in sorted(members):
            print(f"  {v}")
    elif op == "scard":
        print(f"  {args.key} 成员数: {r.scard(args.key)}")
    elif op == "sadd":
        n = r.sadd(args.key, *(args.values or []))
        print(ok(f"[SADD] 新增 {n} 个成员"))
    elif op == "srem":
        n = r.srem(args.key, *(args.values or []))
        print(ok(f"[SREM] 移除 {n} 个成员"))


def r_zset_ops(r, args):
    op = args.zset_op
    if op == "zrange":
        start = getattr(args, "start", None) or 0
        stop  = args.stop if getattr(args, "stop", None) is not None else -1
        items = r.zrange(args.key, start, stop, withscores=True)
        print(info(f"\n[ZRANGE] {args.key}[{start}:{stop}]  共 {len(items)} 个成员"))
        for v, score in items:
            print(f"  score={score:<12}  {v}")
    elif op == "zrangebyscore":
        mn    = args.min_score if getattr(args, "min_score", None) is not None else "-inf"
        mx    = args.max_score if getattr(args, "max_score", None) is not None else "+inf"
        items = r.zrangebyscore(
            args.key, mn, mx, withscores=True,
            start=getattr(args, "offset", None) or 0,
            num=getattr(args, "limit", None) or 100
        )
        print(info(f"\n[ZRANGEBYSCORE] {args.key} [{mn}, {mx}]  共 {len(items)} 个"))
        for v, score in items:
            print(f"  score={score:<12}  {v}")
    elif op == "zcard":
        print(f"  {args.key} 成员数: {r.zcard(args.key)}")
    elif op == "zscore":
        print(f"  {args.key}[{args.member}] score = {r.zscore(args.key, args.member)}")
    elif op == "zadd":
        mapping = {}
        for pair in (args.score_members or []):
            score, member = pair.split(":", 1)
            mapping[member] = float(score)
        n = r.zadd(args.key, mapping)
        print(ok(f"[ZADD] 新增/更新 {n} 个成员"))


def r_ttl(r, args):
    op = args.ttl_op
    if op == "ttl":
        print(f"  {args.key} TTL = {r.ttl(args.key)} 秒")
    elif op == "pttl":
        print(f"  {args.key} PTTL = {r.pttl(args.key)} 毫秒")
    elif op == "expire":
        r.expire(args.key, args.seconds)
        print(ok(f"[EXPIRE] {args.key} 设置 {args.seconds} 秒后过期"))
    elif op == "persist":
        r.persist(args.key)
        print(ok(f"[PERSIST] {args.key} 已移除过期时间"))


def r_info(r, args):
    section   = getattr(args, "section", None) or "all"
    info_data = r.info(section)
    print(info(f"\n[Redis INFO] section={section}"))
    for k, v in info_data.items():
        print(f"  {k:<40}: {v}")


def r_stats(r, args):
    """SCAN 统计 key 类型分布"""
    pattern  = getattr(args, "pattern", None) or "*"
    count    = getattr(args, "scan_count", None) or 200
    cursor   = 0
    total    = 0
    type_cnt = {}
    print(info(f"\n[统计] SCAN 匹配 '{pattern}'..."))
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=count)
        for k in keys:
            t = r.type(k)
            type_cnt[t] = type_cnt.get(t, 0) + 1
            total += 1
        if cursor == 0:
            break
    print(f"\n  总 Key 数: {total}")
    for t, n in sorted(type_cnt.items(), key=lambda x: -x[1]):
        bar = "=" * min(50, n * 50 // max(total, 1))
        pct = n * 100 // max(total, 1)
        print(f"  {t:<10} {n:>8}  {pct:>3}%  [{bar}]")


def r_batch_del(r, args):
    """批量删除匹配 pattern 的 key"""
    pattern = args.pattern
    dry_run = getattr(args, "dry_run", False)
    cursor  = 0
    keys    = []
    while True:
        cursor, batch = r.scan(cursor, match=pattern, count=500)
        keys.extend(batch)
        if cursor == 0:
            break
    print(warn(f"[批量删除] 匹配 '{pattern}'，共 {len(keys)} 个 key"))
    if dry_run:
        print(warn("  --dry-run 模式，仅预览，不执行删除"))
        for k in keys[:50]:
            print(f"  {k}")
        if len(keys) > 50:
            print(f"  ... 还有 {len(keys) - 50} 个")
        return
    if not keys:
        print("  没有匹配的 key")
        return
    confirm = input(warn(f"  确认删除 {len(keys)} 个 key？[yes/N] ")).strip()
    if confirm.lower() != "yes":
        print("  已取消")
        return
    pipe = r.pipeline()
    for k in keys:
        pipe.delete(k)
    pipe.execute()
    print(ok(f"  已删除 {len(keys)} 个 key"))


def r_export(r, args):
    """导出 key 到 JSON 文件"""
    pattern = getattr(args, "pattern", None) or "*"
    output  = getattr(args, "export", None) or f"redis_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    limit   = getattr(args, "limit", None) or 10000
    cursor  = 0
    data    = {}
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=500)
        for k in keys:
            if len(data) >= limit:
                break
            ktype = r.type(k)
            ttl   = r.ttl(k)
            if ktype == "string":
                val = r.get(k)
            elif ktype == "hash":
                val = r.hgetall(k)
            elif ktype == "list":
                val = r.lrange(k, 0, -1)
            elif ktype == "set":
                val = list(r.smembers(k))
            elif ktype == "zset":
                val = {v: s for v, s in r.zrange(k, 0, -1, withscores=True)}
            else:
                val = None
            data[k] = {"type": ktype, "ttl": ttl, "value": val}
        if cursor == 0 or len(data) >= limit:
            break
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(ok(f"[导出] {len(data)} 个 key => {output}"))


def r_pipeline_exec(r, args):
    """从文件读取命令并通过 pipeline 批量执行"""
    cmd_file = args.cmd_file
    with open(cmd_file, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    pipe = r.pipeline()
    for line in lines:
        parts = line.split()
        cmd   = parts[0].lower()
        rest  = parts[1:]
        getattr(pipe, cmd)(*rest)
    results = pipe.execute()
    print(info(f"\n[Pipeline] 执行 {len(lines)} 条命令"))
    for i, (cmd_line, res) in enumerate(zip(lines, results)):
        print(f"  [{i + 1}] {cmd_line:<40}  => {res}")


def handle_redis(args):
    r   = get_redis_conn(args)
    cmd = args.r_cmd

    if   cmd == "get":       r_get(r, args)
    elif cmd == "set":       r_set(r, args)
    elif cmd == "del":       r_del(r, args)
    elif cmd == "keys":      r_keys(r, args)
    elif cmd == "scan":      r_scan(r, args)
    elif cmd == "hget":      r_hget(r, args)
    elif cmd == "hset":      r_hset(r, args)
    elif cmd == "list":      r_list_ops(r, args)
    elif cmd == "set_ops":   r_set_ops(r, args)
    elif cmd == "zset":      r_zset_ops(r, args)
    elif cmd == "ttl":       r_ttl(r, args)
    elif cmd == "info":      r_info(r, args)
    elif cmd == "stats":     r_stats(r, args)
    elif cmd == "batch_del": r_batch_del(r, args)
    elif cmd == "export":    r_export(r, args)
    elif cmd == "pipeline":  r_pipeline_exec(r, args)
    else:
        print(err(f"未知子命令: {cmd}"))


# ══════════════════════════════════════════════
#  参数解析
# ══════════════════════════════════════════════

def build_parser():
    parser = argparse.ArgumentParser(
        prog="db_universal",
        description="万能数据库查询工具 - SQL Server & Redis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
快速示例
--------

SQL Server:
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb dbinfo
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb tables
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb desc -t orders
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb count -t orders --where "status=1"
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb sample -t orders -n 50 --random
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb sample -t orders -n 100 --export out.csv
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb distinct -t orders --field status
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb search -t users --keyword alice
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb indexes -t orders
  python db_universal.py sqlserver -H 127.0.0.1 -U sa -P pass -d mydb query --sql "SELECT TOP 10 * FROM orders"

Redis:
  python db_universal.py redis -H 127.0.0.1 get --key user:1001
  python db_universal.py redis -H 127.0.0.1 set --key foo --value bar --ex 3600
  python db_universal.py redis -H 127.0.0.1 keys --pattern "user:*" --limit 100
  python db_universal.py redis -H 127.0.0.1 scan --pattern "order:*" --limit 200
  python db_universal.py redis -H 127.0.0.1 hget --key user:1001
  python db_universal.py redis -H 127.0.0.1 hget --key user:1001 --field email
  python db_universal.py redis -H 127.0.0.1 hset --key user:1001 --field score --value 99
  python db_universal.py redis -H 127.0.0.1 list lrange --key mylist --start 0 --stop 9
  python db_universal.py redis -H 127.0.0.1 list lpush --key mylist --values a b c
  python db_universal.py redis -H 127.0.0.1 set_ops smembers --key myset
  python db_universal.py redis -H 127.0.0.1 zset zrange --key rank --start 0 --stop 9
  python db_universal.py redis -H 127.0.0.1 zset zrangebyscore --key rank --min-score 0 --max-score 100
  python db_universal.py redis -H 127.0.0.1 zset zadd --key rank --score-members 100:alice 200:bob
  python db_universal.py redis -H 127.0.0.1 ttl ttl --key user:1001
  python db_universal.py redis -H 127.0.0.1 ttl expire --key user:1001 --seconds 7200
  python db_universal.py redis -H 127.0.0.1 stats --pattern "*"
  python db_universal.py redis -H 127.0.0.1 batch_del --pattern "tmp:*" --dry-run
  python db_universal.py redis -H 127.0.0.1 export --pattern "user:*" --export users.json --limit 5000
  python db_universal.py redis -H 127.0.0.1 info --section memory
  python db_universal.py redis -H 127.0.0.1 pipeline --cmd-file cmds.txt

密码也可通过环境变量传入:
  export SS_PASSWORD=yourpass    (SQL Server)
  export REDIS_PASSWORD=yourpass (Redis)
        """
    )

    sub = parser.add_subparsers(dest="db_type", required=True)

    # ══ SQL Server ════════════════════════════════
    ss = sub.add_parser(
        "sqlserver", aliases=["ss", "mssql"],
        help="SQL Server 操作",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ss.add_argument("-H", "--host",     default="127.0.0.1", help="主机地址")
    ss.add_argument("--port",           default=1433, type=int, help="端口（默认1433）")
    ss.add_argument("-U", "--user",     default="sa",  help="用户名")
    ss.add_argument("-P", "--password", default="",   help="密码（或环境变量 SS_PASSWORD）")
    ss.add_argument("-d", "--database", default="master", help="数据库名")
    ss.add_argument("--schema",         default=None, help="Schema（默认 dbo）")
    ss.add_argument("--driver",         default=None, help="ODBC 驱动名")
    ss.add_argument("--trusted",        action="store_true", help="Windows 集成认证")
    ss.add_argument("--encrypt",        action="store_true", help="启用 TLS 加密")
    ss.add_argument("--timeout",        default=30, type=int, help="连接超时秒数")

    ss_sub = ss.add_subparsers(dest="ss_cmd", required=True)

    # query
    p = ss_sub.add_parser("query", help="执行任意 SQL")
    p.add_argument("--sql",    required=True, help="SQL 语句")
    p.add_argument("--top",    type=int, help="自动在 SELECT 前插入 TOP N")
    p.add_argument("--limit",  type=int, help="最多取回行数（fetchmany）")
    p.add_argument("--export", help="导出结果到 CSV 文件路径")

    # tables
    p = ss_sub.add_parser("tables", help="列出所有表（含行数）")
    p.add_argument("--schema", help="过滤 Schema")

    # desc
    p = ss_sub.add_parser("desc", help="查看表结构（字段/类型/主键/注释）")
    p.add_argument("-t", "--table", required=True, help="表名")

    # count
    p = ss_sub.add_parser("count", help="统计行数")
    p.add_argument("-t", "--table",  required=True)
    p.add_argument("--where",        help="WHERE 条件（不含 WHERE 关键字）")
    p.add_argument("--schema")

    # sample
    p = ss_sub.add_parser("sample", help="取样查询（前N条或随机N条）")
    p.add_argument("-t", "--table",   required=True)
    p.add_argument("-n", "--limit",   type=int, default=20, help="行数（默认20）")
    p.add_argument("--fields",        default="*", help="字段列表，逗号分隔")
    p.add_argument("--where",         help="WHERE 条件")
    p.add_argument("--order-by",      dest="order_by", help="ORDER BY 子句")
    p.add_argument("--random",        action="store_true", help="随机抽样（ORDER BY NEWID()）")
    p.add_argument("--schema")
    p.add_argument("--export",        help="导出到 CSV")

    # distinct
    p = ss_sub.add_parser("distinct", help="字段不重复值 + 频次统计")
    p.add_argument("-t", "--table",  required=True)
    p.add_argument("--field",        required=True, help="要分析的字段名")
    p.add_argument("--where",        help="WHERE 条件")
    p.add_argument("--limit",        type=int, default=100, help="最多显示多少种值")
    p.add_argument("--schema")

    # search
    p = ss_sub.add_parser("search", help="在表的所有文本字段中搜索关键词")
    p.add_argument("-t", "--table",   required=True)
    p.add_argument("--keyword",       required=True)
    p.add_argument("--limit",         type=int, default=50)

    # indexes
    p = ss_sub.add_parser("indexes", help="查看表的所有索引")
    p.add_argument("-t", "--table", required=True)

    # dbinfo
    ss_sub.add_parser("dbinfo", help="数据库整体信息（版本/表数/大小）")

    # ══ Redis ════════════════════════════════════
    rd = sub.add_parser(
        "redis", aliases=["r"],
        help="Redis 操作",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    rd.add_argument("-H", "--host",     default="127.0.0.1")
    rd.add_argument("--port",           default=6379, type=int)
    rd.add_argument("--db",             default=0,    type=int, help="DB 编号（默认0）")
    rd.add_argument("-P", "--password", default="",   help="密码（或环境变量 REDIS_PASSWORD）")
    rd.add_argument("--ssl",            action="store_true", help="启用 TLS/SSL")
    rd.add_argument("--timeout",        default=10,   type=int)

    rd_sub = rd.add_subparsers(dest="r_cmd", required=True)

    # get
    p = rd_sub.add_parser("get", help="获取 key 内容（自动识别类型展示）")
    p.add_argument("--key", required=True)

    # set
    p = rd_sub.add_parser("set", help="SET 字符串 key")
    p.add_argument("--key",   required=True)
    p.add_argument("--value", required=True)
    p.add_argument("--ex",    type=int, help="过期秒数")
    p.add_argument("--px",    type=int, help="过期毫秒")
    p.add_argument("--nx",    action="store_true", help="仅 key 不存在时设置")
    p.add_argument("--xx",    action="store_true", help="仅 key 存在时设置")

    # del
    p = rd_sub.add_parser("del", help="删除一个或多个 key")
    p.add_argument("--keys", nargs="+", required=True)

    # keys
    p = rd_sub.add_parser("keys", help="KEYS 模式匹配（仅小数据集）")
    p.add_argument("--pattern", default="*")
    p.add_argument("--limit",   type=int, default=200)

    # scan
    p = rd_sub.add_parser("scan", help="SCAN 迭代（大数据集安全方式）")
    p.add_argument("--pattern",    default="*")
    p.add_argument("--limit",      type=int, default=500)
    p.add_argument("--scan-count", type=int, default=100, dest="scan_count")

    # hget
    p = rd_sub.add_parser("hget", help="Hash 获取（不加 --field 则 HGETALL）")
    p.add_argument("--key",   required=True)
    p.add_argument("--field", help="字段名（不填则获取全部）")

    # hset
    p = rd_sub.add_parser("hset", help="Hash 设置字段值")
    p.add_argument("--key",   required=True)
    p.add_argument("--field", required=True)
    p.add_argument("--value", required=True)

    # list
    p = rd_sub.add_parser("list", help="List 操作 [lrange|llen|lpush|rpush]")
    p.add_argument("list_op", choices=["lrange", "llen", "lpush", "rpush"])
    p.add_argument("--key",    required=True)
    p.add_argument("--start",  type=int, help="lrange 起始索引")
    p.add_argument("--stop",   type=int, help="lrange 结束索引")
    p.add_argument("--values", nargs="*", help="lpush/rpush 的值（多个）")

    # set_ops
    p = rd_sub.add_parser("set_ops", help="Set 操作 [smembers|scard|sadd|srem]")
    p.add_argument("set_op", choices=["smembers", "scard", "sadd", "srem"])
    p.add_argument("--key",    required=True)
    p.add_argument("--values", nargs="*", help="sadd/srem 的值")

    # zset
    p = rd_sub.add_parser("zset", help="ZSet 操作 [zrange|zrangebyscore|zcard|zscore|zadd]")
    p.add_argument("zset_op", choices=["zrange", "zrangebyscore", "zcard", "zscore", "zadd"])
    p.add_argument("--key",           required=True)
    p.add_argument("--start",         type=int, help="zrange 起始")
    p.add_argument("--stop",          type=int, help="zrange 结束")
    p.add_argument("--min-score",     type=float, dest="min_score")
    p.add_argument("--max-score",     type=float, dest="max_score")
    p.add_argument("--offset",        type=int,   help="zrangebyscore 偏移量")
    p.add_argument("--limit",         type=int,   help="zrangebyscore 返回数量")
    p.add_argument("--member",        help="zscore 要查询的成员")
    p.add_argument("--score-members", nargs="*", dest="score_members",
                   metavar="SCORE:MEMBER", help="zadd 用，如: 100:alice 200:bob")

    # ttl
    p = rd_sub.add_parser("ttl", help="TTL 操作 [ttl|pttl|expire|persist]")
    p.add_argument("ttl_op", choices=["ttl", "pttl", "expire", "persist"])
    p.add_argument("--key",     required=True)
    p.add_argument("--seconds", type=int, help="expire 使用的秒数")

    # info
    p = rd_sub.add_parser("info", help="Redis 服务器信息")
    p.add_argument("--section", default="all",
                   choices=["all", "server", "clients", "memory", "stats",
                            "replication", "cpu", "keyspace"])

    # stats
    p = rd_sub.add_parser("stats", help="SCAN 统计 key 类型分布")
    p.add_argument("--pattern",    default="*")
    p.add_argument("--scan-count", type=int, default=200, dest="scan_count")

    # batch_del
    p = rd_sub.add_parser("batch_del", help="批量删除匹配 pattern 的 key")
    p.add_argument("--pattern",  required=True)
    p.add_argument("--dry-run",  action="store_true", dest="dry_run", help="预览，不实际删除")

    # export
    p = rd_sub.add_parser("export", help="导出匹配 pattern 的 key 到 JSON 文件")
    p.add_argument("--pattern", default="*")
    p.add_argument("--export",  help="输出文件名（默认自动命名）")
    p.add_argument("--limit",   type=int, default=10000, help="最多导出 key 数量")

    # pipeline
    p = rd_sub.add_parser("pipeline", help="从文件批量执行 Redis 命令（pipeline）")
    p.add_argument("--cmd-file", required=True, dest="cmd_file",
                   help="命令文件路径（每行一条命令，# 开头为注释）")

    return parser


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════

def main():
    parser  = build_parser()
    args    = parser.parse_args()
    db_type = args.db_type.lower()

    if db_type in ("sqlserver", "ss", "mssql"):
        handle_sqlserver(args)
    elif db_type in ("redis", "r"):
        handle_redis(args)
    else:
        print(err(f"未知数据库类型: {db_type}"))
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
