import sys
sys.path.insert(0, r"D:\mcsv3")

import memory_skill_v2 as skill

skill.setup()

user_id    = "user_001"
session_id = "session_001"

# 第一轮
skill.memorize(user_id, session_id, turn=1,
    summary  = "用户想用 Python 做聊天机器人",
    keywords = ["Python", "聊天机器人"],
    raw_q    = "我想用 Python 做聊天机器人",
    raw_a    = "推荐你用 LangChain 或 Rasa",
)

# 第二轮：看看能不能检索到第一轮的记忆
context = skill.remember(user_id, session_id, turn=2,
    query_text = "有没有更轻量的方案"
)
print(context)

skill.flush(user_id, session_id)