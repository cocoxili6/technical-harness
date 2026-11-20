import json
import re
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

from ..config import get_settings

ATOM = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@tool
def search_arxiv(query: str, max_results: int = 5) -> str:
    """检索 arXiv 学术论文。适用于需要文献、方法对比或研究现状的问题。

    Args:
        query: 检索关键词，优先使用英文术语，例如 "multi-agent reinforcement learning credit assignment"。
        max_results: 返回论文数量，1 到 8 之间，默认 5。
    """
    cleaned_query = _clean(query)
    if not cleaned_query:
        return json.dumps(
            {"query": cleaned_query, "results": [], "error": "检索关键词为空"},
            ensure_ascii=False,
        )

    try:
        limit = max(1, min(int(max_results), 8))
    except (TypeError, ValueError):
        limit = 5

    try:
        response = httpx.get(
            get_settings().arxiv_endpoint,
            params={
                "search_query": f"all:{cleaned_query}",
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            headers={"User-Agent": "ResearchHarness/0.1"},
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return json.dumps(
            {
                "query": cleaned_query,
                "results": [],
                "error": "arXiv 检索暂时不可用，请稍后再试",
            },
            ensure_ascii=False,
        )

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return json.dumps(
            {
                "query": cleaned_query,
                "results": [],
                "error": "arXiv 返回内容无法解析",
            },
            ensure_ascii=False,
        )

    results = []
    for entry in root.findall("a:entry", ATOM):
        title = _clean(entry.findtext("a:title", default="", namespaces=ATOM))
        summary = _clean(entry.findtext("a:summary", default="", namespaces=ATOM))
        entry_id = _clean(entry.findtext("a:id", default="", namespaces=ATOM))
        published = _clean(entry.findtext("a:published", default="", namespaces=ATOM))
        authors = [
            _clean(node.findtext("a:name", default="", namespaces=ATOM))
            for node in entry.findall("a:author", ATOM)
        ]
        category_node = entry.find("arxiv:primary_category", ATOM)
        category = category_node.attrib.get("term", "") if category_node is not None else ""

        if not title or not entry_id:
            continue

        author_text = ", ".join(authors[:4])
        if len(authors) > 4:
            author_text += " 等"

        results.append(
            {
                "title": title,
                "authors": author_text,
                "year": published[:4],
                "url": entry_id,
                "category": category,
                "summary": summary[:320],
            }
        )

    return json.dumps(
        {"query": cleaned_query, "results": results},
        ensure_ascii=False,
    )


@tool
def search_scholar(query: str, max_results: int = 5) -> str:
    """检索 Google Scholar 学术结果（期刊、会议、综述，含引用量）。适用于需要正式发表文献或判断影响力的学术问题。

    Args:
        query: 检索关键词，优先使用英文术语，例如 "multi-agent reinforcement learning credit assignment"。
        max_results: 返回结果数量，1 到 8 之间，默认 5。
    """
    cleaned_query = _clean(query)
    if not cleaned_query:
        return json.dumps(
            {"query": cleaned_query, "results": [], "error": "检索关键词为空"},
            ensure_ascii=False,
        )

    api_key = get_settings().serper_api_key.strip()
    if not api_key:
        return json.dumps(
            {
                "query": cleaned_query,
                "results": [],
                "error": "未配置 SERPER_API_KEY，Google Scholar 检索不可用",
            },
            ensure_ascii=False,
        )

    try:
        limit = max(1, min(int(max_results), 8))
    except (TypeError, ValueError):
        limit = 5

    try:
        response = httpx.post(
            get_settings().serper_scholar_endpoint,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": cleaned_query},
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            message = "Google Scholar 检索鉴权失败，请检查 SERPER_API_KEY"
        elif status == 429:
            message = "Google Scholar 检索请求过于频繁，请稍后再试"
        else:
            message = "Google Scholar 检索暂时不可用，请稍后再试"
        return json.dumps(
            {"query": cleaned_query, "results": [], "error": message},
            ensure_ascii=False,
        )
    except httpx.HTTPError:
        return json.dumps(
            {
                "query": cleaned_query,
                "results": [],
                "error": "Google Scholar 检索暂时不可用，请稍后再试",
            },
            ensure_ascii=False,
        )

    try:
        payload = response.json()
    except ValueError:
        return json.dumps(
            {
                "query": cleaned_query,
                "results": [],
                "error": "Google Scholar 返回内容无法解析",
            },
            ensure_ascii=False,
        )

    organic = payload.get("organic") if isinstance(payload, dict) else None
    if not isinstance(organic, list):
        organic = []

    results = []
    for item in organic:
        if not isinstance(item, dict):
            continue
        title = _clean(str(item.get("title", "")))
        url = str(item.get("link", "")).strip()
        if not title or not (url.startswith("https://") or url.startswith("http://")):
            continue

        venue = _clean(str(item.get("publicationInfo", "")))
        year = str(item.get("year", "")).strip()
        if not year:
            match = re.search(r"\b(?:19|20)\d{2}\b", venue)
            year = match.group(0) if match else ""

        cited_by = item.get("citedBy")
        results.append(
            {
                "title": title[:300],
                "authors": _clean(str(item.get("authors", "")))[:200],
                "year": year[:8],
                "url": url[:500],
                "category": venue[:40],
                "summary": _clean(str(item.get("snippet", "")))[:320],
                "cited_by": cited_by if isinstance(cited_by, int) else None,
            }
        )
        if len(results) >= limit:
            break

    return json.dumps(
        {"source": "google_scholar", "query": cleaned_query, "results": results},
        ensure_ascii=False,
    )
