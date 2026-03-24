def format_for_prompt(hot_memories, cold_memories):
    if not hot_memories and not cold_memories:
        return ""

    lines = [
        "你拥有以下记忆。请在回答时自然地结合这些背景，不要直接说根据我的记忆：",
        "",
    ]

    if cold_memories:
        lines.append("【历史记忆】")
        for m in cold_memories:
            date = m.get("created_at", "")[:10] or "未知日期"
            lines.append(f"  [{date}] {m['summary']}")
        lines.append("")

    if hot_memories:
        lines.append("【本轮对话】")
        for m in hot_memories:
            lines.append(f"  [第{m['turn']}轮] {m['summary']}")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def estimate_tokens(text):
    """估算文本的 token 数量。

    对中文字符按 1 token/字计，对其余字符按 4 字符/token 计，
    最后乘以 1.2 的安全系数以应对中英混排及 tokenizer 差异。
    """
    chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    others  = len(text) - chinese
    raw     = chinese + others // 4
    return int(raw * 1.2)


def trim_to_budget(hot_memories, cold_memories, token_budget=1200):
    hot_limited  = hot_memories[-20:]
    cold_limited = cold_memories[:]

    candidate = format_for_prompt(hot_limited, cold_limited)
    if estimate_tokens(candidate) <= token_budget:
        return hot_limited, cold_limited

    # 先裁剪冷记忆（优先保留热记忆）
    while cold_limited and estimate_tokens(
        format_for_prompt(hot_limited, cold_limited)
    ) > token_budget:
        cold_limited.pop()

    # 冷记忆裁完仍超出，再从旧到新裁热记忆
    while len(hot_limited) > 1 and estimate_tokens(
        format_for_prompt(hot_limited, cold_limited)
    ) > token_budget:
        hot_limited.pop(0)

    return hot_limited, cold_limited
