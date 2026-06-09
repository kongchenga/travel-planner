"""Web search tool — tries Baidu direct search (may be blocked by captcha).

In restricted network environments, this tool may return empty results.
Agents should gracefully fall back to LLM knowledge.
"""

import re
from typing import Optional
from urllib.parse import quote

import requests

from .cache import cache_result
from .retry import retry_http


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@cache_result(ttl=7200)
@retry_http
def baidu_search(query: str, num_results: int = 5) -> list[dict[str, str]]:
    """Search via Baidu. Returns list of {title, snippet, url}.

    May be blocked by Baidu's captcha (returns empty list).
    Results cached for 2 hours.
    """
    try:
        url = f"https://www.baidu.com/s?wd={quote(query)}&rn={num_results}"
        resp = requests.get(url, headers=_HEADERS, timeout=8)
        resp.encoding = "utf-8"
        html = resp.text
    except requests.RequestException:
        return []

    # Baidu blocks automated requests
    if "安全验证" in html or len(html) < 500:
        return []

    results = []
    blocks = re.findall(
        r'<div\s+class="result[^"]*"\s*(?:id="\d+")?.*?>(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL,
    )
    for block in blocks[:num_results]:
        t = re.search(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.DOTALL)
        if not t:
            continue
        s = re.search(
            r'<span\s+class="content-right_[^"]*">(.*?)</span>', block, re.DOTALL
        )
        u = re.search(r'<a\s+href="(https?://[^"]+)"', block)
        results.append({
            "title": _clean(t.group(1)),
            "snippet": _clean(s.group(1)) if s else "",
            "url": u.group(1) if u else "",
        })
    return results


@cache_result(ttl=7200)
def baidu_baike(query: str) -> Optional[dict[str, str]]:
    """Look up a term on Baidu Baike."""
    try:
        url = f"https://baike.baidu.com/item/{quote(query)}"
        resp = requests.get(url, headers=_HEADERS, timeout=8)
        resp.encoding = "utf-8"
        html = resp.text
    except requests.RequestException:
        return None

    if "安全验证" in html or len(html) < 500:
        return None

    title_m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
    summary_m = re.search(r'<div\s+class="para"[^>]*>(.*?)</div>', html, re.DOTALL)

    title = _clean(title_m.group(1)) if title_m else query
    description = desc_m.group(1) if desc_m else ""
    summary = _clean(summary_m.group(1)) if summary_m else ""

    return {
        "title": title.replace("_百度百科", "").strip(),
        "description": description,
        "summary": summary,
    }


def _clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
