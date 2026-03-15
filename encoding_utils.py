#!/usr/bin/env python3
"""
encoding_utils.py — 公共编码检测工具模块
供 read_gbk.py / write_gbk.py / gbktoutf8.py / utf8togbk.py 共享使用。
"""

from __future__ import annotations
import sys

# ── 可选依赖：charset-normalizer（优先）或 chardet ──────────────────────────
try:
    from charset_normalizer import from_bytes as _cn_from_bytes

    def detect_encoding(raw: bytes) -> tuple[str | None, float]:
        """返回 (编码名称, 置信度)，无法判断时返回 (None, 0.0)。
        charset-normalizer 的 chaos ∈ [0,1]，0 表示最可信，故置信度 = 1 - chaos。
        """
        if not raw:
            return None, 0.0
        result = _cn_from_bytes(raw).best()
        if result is None:
            return None, 0.0
        return result.encoding, round(1.0 - result.chaos, 3)

    DETECTOR = "charset-normalizer"

except ImportError:
    try:
        import chardet as _chardet

        def detect_encoding(raw: bytes) -> tuple[str | None, float]:
            if not raw:
                return None, 0.0
            r = _chardet.detect(raw)
            return r.get("encoding"), r.get("confidence", 0.0) or 0.0

        DETECTOR = "chardet"

    except ImportError:
        def detect_encoding(raw: bytes) -> tuple[str | None, float]:
            """无第三方库时的降级实现（仅区分 UTF-8 / 疑似 GBK / 未知）。"""
            if not raw:
                return None, 0.0
            # 尝试 UTF-8（严格模式）
            try:
                raw.decode("utf-8", errors="strict")
                # 纯 ASCII 子集：置信度稍低，因为 GBK 也能解
                confidence = 0.6 if all(b < 0x80 for b in raw) else 0.99
                return "utf-8", confidence
            except (UnicodeDecodeError, ValueError):
                pass
            # 尝试 GBK
            try:
                raw.decode("gbk", errors="strict")
                return "gbk", 0.7
            except (UnicodeDecodeError, ValueError):
                pass
            return None, 0.0

        DETECTOR = "builtin-fallback"


# ── 基础判断函数 ─────────────────────────────────────────────────────────────

UTF8_BOM = b"\xef\xbb\xbf"


def strip_utf8_bom(raw: bytes) -> bytes:
    return raw[len(UTF8_BOM):] if raw.startswith(UTF8_BOM) else raw


def is_utf8_strict(raw: bytes) -> bool:
    """严格判断：去 BOM 后能无损解码为 UTF-8。"""
    try:
        strip_utf8_bom(raw).decode("utf-8", errors="strict")
        return True
    except (UnicodeDecodeError, ValueError):
        return False


def is_gbk_strict(raw: bytes) -> bool:
    try:
        raw.decode("gbk", errors="strict")
        return True
    except (UnicodeDecodeError, ValueError):
        return False


def is_pure_ascii(raw: bytes) -> bool:
    return all(b < 0x80 for b in raw)


# ── 带置信度的智能判断 ────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.80   # 低于此值视为"不确定"


def guess_encoding(raw: bytes) -> tuple[str, float, bool]:
    """
    返回 (规范编码名, 置信度, 是否确定)。
    规范编码名只会是 'utf-8' / 'gbk' / 'ascii' / 'unknown'。
    """
    if not raw:
        return "utf-8", 1.0, True  # 空文件视为 UTF-8

    if is_pure_ascii(raw):
        return "ascii", 1.0, True

    # 先用第三方库检测
    enc, conf = detect_encoding(raw)

    # 规范化编码名
    canonical = _normalize_enc(enc)

    # 双重验证：检测结果为 GBK/UTF-8 时，用严格解码确认
    if canonical == "utf-8" and is_utf8_strict(raw) and conf >= CONFIDENCE_THRESHOLD:
        return "utf-8", conf, True
    if canonical == "gbk" and is_gbk_strict(raw) and conf >= CONFIDENCE_THRESHOLD:
        return "gbk", conf, True

    # 置信度不足时降级：先试 UTF-8，再试 GBK
    if is_utf8_strict(raw):
        return "utf-8", max(conf or 0.0, 0.6), False
    if is_gbk_strict(raw):
        return "gbk", max(conf or 0.0, 0.5), False

    return "unknown", 0.0, False


def _normalize_enc(enc: str | None) -> str:
    if enc is None:
        return "unknown"
    e = enc.lower().replace("-", "").replace("_", "")
    if e in ("utf8", "utf8sig"):
        return "utf-8"
    if e in ("gbk", "gb2312", "gb18030", "gbk2312", "cngb2312", "hz"):
        return "gbk"
    if e in ("ascii", "usascii"):
        return "ascii"
    return enc.lower()


# ── 文件类型白名单 ────────────────────────────────────────────────────────────

TEXT_EXTENSIONS: frozenset[str] = frozenset({
    ".txt", ".log", ".md", ".rst", ".csv", ".tsv", ".ini", ".cfg", ".conf",
    ".toml", ".yaml", ".yml", ".json", ".xml", ".html", ".htm", ".css",
    ".svg", ".properties", ".env", ".editorconfig", ".gitignore", ".gitattributes",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
    ".java", ".kt", ".kts", ".scala",
    ".py", ".pyw", ".pyi",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte",
    ".cs", ".vb", ".fs",
    ".go", ".rs",
    ".rb", ".rake", ".gemspec",
    ".php",
    ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1",
    ".swift", ".m", ".mm",
    ".dart", ".lua",
    ".pl", ".pm",
    ".r", ".rmd",
    ".sql",
    ".cmake", ".make", ".mk", ".gradle", ".tf", ".tfvars",
    ".diff", ".patch", ".tex", ".srt", ".vtt",
})


def is_text_file(path: str) -> bool:
    import os
    return os.path.splitext(path)[1].lower() in TEXT_EXTENSIONS


def print_detector_info(file=sys.stderr):
    print(f"[encoding_utils] 使用检测器: {DETECTOR}", file=file)
