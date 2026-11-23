from datetime import date
from typing import List
from urllib.parse import quote


def build_demo_reply(question: str) -> str:
    return f"""> **演示模式**：还没有配置 `DEEPSEEK_API_KEY`。下面是界面流程示例，不是真实检索或模型输出。

### 你问的是

**{question}**

### 接入模型后会发生什么

一轮完整的调研会经过四步：

1. **拆解问题**：识别领域、任务和评价指标，生成 1-3 组英文检索词。
2. **检索文献**：调用 arXiv 工具，按关键词取回近期论文。
3. **组织脉络**：按方法分组，标出共识、分歧和尚未解决的空白。
4. **排出路线**：按入门、基础、进阶、前沿四个阶段排好阅读顺序，每篇论文附推荐理由、前置知识和预计阅读时间。

### 阅读路线骨架

| 阶段 | 读什么 | 读完应掌握 |
| --- | --- | --- |
| 入门 | 代表性综述、基础概念 | 领域全景、核心术语 |
| 基础 | 经典论文 | 主要研究方法及其假设 |
| 进阶 | 方法改进、不同技术路线 | 各路线的差异与取舍 |
| 前沿 | 最新研究 | 当前热点与未解决问题 |

### 下一步

- 在 `backend/.env` 填入 `DEEPSEEK_API_KEY`，重启后端；
- 再问一次同一个问题，我会检索真实文献并替换上面的骨架；
- 后续追问会沿用当前会话的短期记忆。

*这一段由演示流生成，接入 API Key 后自动切换为真实模型。*"""


def build_demo_sources(question: str) -> List[dict]:
    year = str(date.today().year)
    return [
        {
            "title": f"arXiv 检索入口：{question}",
            "authors": "演示入口",
            "year": year,
            "url": f"https://arxiv.org/search/?query={quote(question)}&searchtype=all",
            "category": "DEMO",
            "summary": "接入模型后，真实检索到的论文会以卡片形式出现在这里。",
        },
        {
            "title": "arXiv cs.LG 最新论文",
            "authors": "arXiv",
            "year": year,
            "url": "https://arxiv.org/list/cs.LG/recent",
            "category": "DEMO",
            "summary": "示例来源：用于展示来源卡片的样式，不代表本轮检索结果。",
        },
    ]
