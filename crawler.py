"""
강화된 웹 크롤러 (AEO 분석 최적화).
- 본문 텍스트
- JSON-LD / Microdata / RDFa 스키마
- Open Graph / Twitter Card / 메타 태그
- 헤딩 구조 (H1~H3)
- 이미지 + alt 텍스트
- 페이지 제목 / 디스크립션
"""

import re
import logging
from typing import Dict, Any, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    import extruct
    from w3lib.html import get_base_url
    HAS_EXTRUCT = True
except Exception:
    HAS_EXTRUCT = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_YT_TRANSCRIPT = True
except Exception:
    HAS_YT_TRANSCRIPT = False

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Safari/605.1.15"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def crawl_url(url: str, timeout: int = 10) -> Dict[str, Any]:
    """페이지를 크롤링하여 AEO 분석에 필요한 모든 정보 추출."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        html = resp.text
        base_url = url
        soup = BeautifulSoup(html, "lxml")

        # --- 1. 메타 정보 ---
        title = (soup.title.string.strip() if soup.title and soup.title.string else "")
        meta_desc = _meta(soup, "description")
        meta_keywords = _meta(soup, "keywords")

        # --- 2. Open Graph / Twitter ---
        og = _extract_og(soup)
        twitter = _extract_twitter(soup)

        # --- 3. 헤딩 구조 ---
        headings = {
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")][:10],
            "h2": [h.get_text(strip=True) for h in soup.find_all("h2")][:20],
            "h3": [h.get_text(strip=True) for h in soup.find_all("h3")][:30],
        }

        # --- 4. 본문 ---
        for tag in soup(["script", "style", "noscript", "nav", "footer", "aside"]):
            tag.decompose()

        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        body_text = " ".join([p for p in paragraphs if len(p) > 20])
        if not body_text:
            body_text = soup.get_text(separator=" ", strip=True)
        body_text = re.sub(r"\s+", " ", body_text).strip()[:5000]

        # --- 5. 이미지 + alt ---
        images: List[Dict[str, str]] = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            alt = (img.get("alt") or "").strip()
            if not src:
                continue
            absolute = urljoin(base_url, src)
            images.append({"src": absolute, "alt": alt})
            if len(images) >= 30:
                break
        images_no_alt = [i for i in images if not i["alt"]]

        # --- 6. 구조화 데이터 (JSON-LD / Microdata / RDFa) ---
        schemas = _extract_schemas(html, base_url)

        # --- 7. YouTube 자막 + 메타데이터 ---
        is_youtube = "youtube.com" in url or "youtu.be" in url
        yt_text = ""
        if is_youtube:
            yt_text = _try_youtube_transcript(url)
            if yt_text:
                # 자막을 본문 앞에 붙임 (자막이 가장 중요한 신호)
                body_text = ("[자막]\n" + yt_text + "\n\n[페이지 텍스트]\n" + body_text)[:6000]

        # --- 8. AEO 친화 점검 ---
        aeo_checks = {
            "has_title": bool(title),
            "has_meta_desc": bool(meta_desc),
            "has_h1": bool(headings["h1"]),
            "has_og": bool(og),
            "has_schema": bool(schemas),
            "has_faq_schema": any(
                (s.get("@type") == "FAQPage" or s.get("@type") == "Question")
                for s in schemas
            ),
            "image_alt_coverage": (
                round((len(images) - len(images_no_alt)) / len(images) * 100, 1)
                if images else 0.0
            ),
            "body_length": len(body_text),
        }

        return {
            "ok": True,
            "url": url,
            "type": "youtube" if is_youtube else "web",
            "title": title,
            "meta_description": meta_desc,
            "meta_keywords": meta_keywords,
            "og": og,
            "twitter": twitter,
            "headings": headings,
            "text": body_text,
            "images": images,
            "images_missing_alt": len(images_no_alt),
            "schemas": schemas,
            "aeo_checks": aeo_checks,
        }

    except Exception as e:
        log.error(f"crawl_url 실패: {e}")
        return {
            "ok": False,
            "url": url,
            "error": str(e),
            "type": "error",
            "title": "",
            "text": "",
            "images": [],
            "schemas": [],
            "aeo_checks": {},
        }


def _meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _extract_og(soup: BeautifulSoup) -> Dict[str, str]:
    og = {}
    for tag in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
        key = tag.get("property", "").replace("og:", "")
        val = tag.get("content", "").strip()
        if key and val:
            og[key] = val
    return og


def _extract_twitter(soup: BeautifulSoup) -> Dict[str, str]:
    t = {}
    for tag in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
        key = tag.get("name", "").replace("twitter:", "")
        val = tag.get("content", "").strip()
        if key and val:
            t[key] = val
    return t


def _extract_schemas(html: str, base_url: str) -> List[Dict[str, Any]]:
    """JSON-LD, Microdata, RDFa 모두 추출."""
    if not HAS_EXTRUCT:
        return []
    try:
        data = extruct.extract(
            html,
            base_url=get_base_url(html, base_url),
            syntaxes=["json-ld", "microdata", "rdfa"],
            uniform=True,
        )
        merged: List[Dict[str, Any]] = []
        for syntax in ("json-ld", "microdata", "rdfa"):
            for item in data.get(syntax, []) or []:
                if isinstance(item, dict):
                    merged.append(item)
        return merged[:20]
    except Exception as e:
        log.warning(f"schema 추출 실패: {e}")
        return []


def _try_youtube_transcript(url: str) -> str:
    """YouTube 자막을 시도. 실패하면 빈 문자열."""
    if not HAS_YT_TRANSCRIPT:
        return ""
    try:
        m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_\-]{11})", url)
        if not m:
            return ""
        video_id = m.group(1)
        # 우선순위: 한국어 → 영어 → 자동 생성 → 첫 번째 가능한 것
        try:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None
            for langs in (["ko"], ["en"], ["ko-KR"], ["en-US"]):
                try:
                    transcript = transcripts.find_transcript(langs)
                    break
                except Exception:
                    continue
            if not transcript:
                for t in transcripts:
                    transcript = t
                    break
            if transcript:
                items = transcript.fetch()
                text = " ".join([it.get("text", "") for it in items if it.get("text")])
                text = re.sub(r"\s+", " ", text).strip()
                return text[:6000]
        except Exception as e:
            log.warning(f"YouTube transcript list 실패: {e}")
            try:
                items = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
                text = " ".join([it.get("text", "") for it in items])
                return re.sub(r"\s+", " ", text).strip()[:6000]
            except Exception as e2:
                log.warning(f"YouTube transcript fallback 실패: {e2}")
        return ""
    except Exception as e:
        log.warning(f"YouTube transcript 전체 실패: {e}")
        return ""
