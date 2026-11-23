import json
import logging
from collections import OrderedDict
from typing import List, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

from ..config import Settings

logger = logging.getLogger("harness.analysis")

CACHE_LIMIT = 200

ANALYSIS_PROMPT = """你是科研论文导读助手。你只能看到论文的标题、作者、年份、出处和摘要，看不到全文。
请据此为刚入门的读者写一份结构化分析，只输出一个 JSON 对象，字段如下：
{
  "research_problem": "论文要解决的问题，1-2 句",
  "method": "核心方法或技术路线，1-3 句",
  "contributions": ["主要贡献，2-3 条，每条一句"],
  "limitations": ["可能的局限，1-2 条，每条一句"],
  "prerequisites": ["读这篇需要的前置知识，2-4 个短语"],
  "difficulty": "入门 | 中等 | 较难 三选一",
  "difficulty_reason": "判断难度的依据，一句",
  "reading_time": "精读预计时间，例如：约 3 小时",
  "paper_type": "综述 | 方法 | 实证 | 理论 | 系统 | 其他 六选一"
}
要求：
1. 用中文。只依据给出的信息，摘要没提到的内容不要编造；局限如果摘要没写，可以基于方法类型推测，但措辞要用"可能""通常"。
2. 摘要缺失或过短时，各字段尽量简短，并在 difficulty_reason 里说明信息不足。
3. 不要输出 JSON 以外的任何文字。"""


class PaperInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    authors: str = Field(default="", max_length=200)
    year: str = Field(default="", max_length=8)
    url: str = Field(min_length=1, max_length=500)
    category: str = Field(default="", max_length=60)
    summary: str = Field(default="", max_length=2000)


class PaperAnalysis(BaseModel):
    research_problem: str = ""
    method: str = ""
    contributions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    difficulty: Literal["入门", "中等", "较难"] = "中等"
    difficulty_reason: str = ""
    reading_time: str = ""
    paper_type: Literal["综述", "方法", "实证", "理论", "系统", "其他"] = "其他"


def _paper_text(paper: PaperInput) -> str:
    lines = [f"标题：{paper.title}"]
    if paper.authors:
        lines.append(f"作者：{paper.authors}")
    if paper.year:
        lines.append(f"年份：{paper.year}")
    if paper.category:
        lines.append(f"出处/分类：{paper.category}")
    lines.append(f"摘要：{paper.summary or '（无摘要）'}")
    return "\n".join(lines)


def _parse(raw: str) -> PaperAnalysis:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("模型没有返回 JSON")
    data = json.loads(text[start : end + 1])
    for key in ("contributions", "limitations", "prerequisites"):
        value = data.get(key)
        if isinstance(value, str):
            data[key] = [value]
        elif isinstance(value, list):
            data[key] = [str(item)[:200] for item in value][:5]
    if data.get("difficulty") not in ("入门", "中等", "较难"):
        data["difficulty"] = "中等"
    if data.get("paper_type") not in ("综述", "方法", "实证", "理论", "系统", "其他"):
        data["paper_type"] = "其他"
    return PaperAnalysis(**data)


class PaperAnalyzer:
    def __init__(self, settings: Settings):
        self._llm = ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.2,
            max_retries=1,
            timeout=60,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        self._cache: "OrderedDict[str, PaperAnalysis]" = OrderedDict()

    def cached(self, url: str) -> Optional[PaperAnalysis]:
        result = self._cache.get(url)
        if result is not None:
            self._cache.move_to_end(url)
        return result

    async def analyze(self, paper: PaperInput) -> PaperAnalysis:
        hit = self.cached(paper.url)
        if hit is not None:
            return hit
        response = await self._llm.ainvoke(
            [SystemMessage(content=ANALYSIS_PROMPT), HumanMessage(content=_paper_text(paper))]
        )
        try:
            result = _parse(str(response.content))
        except (ValueError, ValidationError) as exc:
            logger.warning("paper analysis parse failed: %s", exc)
            raise ValueError("论文分析结果格式异常，请重试。") from exc
        self._cache[paper.url] = result
        if len(self._cache) > CACHE_LIMIT:
            self._cache.popitem(last=False)
        return result


def demo_analysis(paper: PaperInput) -> PaperAnalysis:
    return PaperAnalysis(
        research_problem=f"（演示）《{paper.title[:40]}》试图解决的核心问题会显示在这里。",
        method="（演示）配置 DeepSeek API Key 后，这里会根据摘要概括论文方法。",
        contributions=["（演示）主要贡献一", "（演示）主要贡献二"],
        limitations=["（演示）可能的局限"],
        prerequisites=["机器学习基础", "概率论"],
        difficulty="中等",
        difficulty_reason="演示模式，未调用模型。",
        reading_time="约 3 小时",
        paper_type="其他",
    )
