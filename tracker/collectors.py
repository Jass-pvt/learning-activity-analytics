"""Best-effort public-profile collectors. No login cookies or credentials required."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import PROFILES

TIMEOUT = 20
HEADERS = {
    "User-Agent": "learning-activity-tracker/1.0 (personal learning log; public profile fetcher)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


def _get(url: str, *, json_body: dict | None = None) -> requests.Response:
    if json_body is None:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    else:
        response = requests.post(
            url,
            headers={**HEADERS, "Content-Type": "application/json", "Referer": "https://leetcode.com/"},
            json=json_body,
            timeout=TIMEOUT,
        )
    response.raise_for_status()
    return response


def _page_text_and_json(url: str) -> tuple[str, list[Any], str]:
    response = _get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    scripts: list[Any] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            scripts.append(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError):
            continue
    for script in soup.find_all("script", id=re.compile(r"__NEXT_DATA__|__NUXT_DATA__")):
        try:
            scripts.append(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError):
            continue
    return soup.get_text(" ", strip=True), scripts, title


def collect_google_skills() -> dict[str, Any]:
    cfg = PROFILES["google_skills"]
    text, structured, title = _page_text_and_json(cfg["url"])
    # Public profiles commonly expose earned badge names in page text/structured data.
    # Do not infer completion from generic page copy; only capture explicitly labelled badge links/cards.
    response = _get(cfg["url"])
    soup = BeautifulSoup(response.text, "html.parser")
    badges: set[str] = set()
    for node in soup.select('[class*="badge"], [data-testid*="badge"], a[href*="badge"]'):
        label = node.get("aria-label") or node.get("title") or node.get_text(" ", strip=True)
        label = re.sub(r"\s+", " ", label).strip()
        if label and len(label) <= 180 and label.lower() not in {"badge", "badges", "view badge", "share badge"}:
            badges.add(label)
    return {
        "profile_url": cfg["url"],
        "page_title": title or None,
        "earned_badges": sorted(badges),
        "badge_count_observed": len(badges),
        "collection_note": "Best-effort public-page extraction; empty badge list means the page did not expose parseable badge labels.",
    }


def collect_leetcode() -> dict[str, Any]:
    cfg = PROFILES["leetcode"]
    endpoint = "https://leetcode.com/graphql"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; learning-activity-tracker/1.0)",
        "Referer": "https://leetcode.com/",
        "Origin": "https://leetcode.com",
        "Content-Type": "application/json",
    }

    # Keep the profile query limited to fields confirmed by LeetCode's current schema.
    profile_query = """query userActivity($username: String!) {
      matchedUser(username: $username) {
        username
        profile { realName ranking }
        submitStats: submitStatsGlobal {
          acSubmissionNum { difficulty count submissions }
        }
      }
    }"""
    response = requests.post(
        endpoint,
        headers=headers,
        json={"query": profile_query, "variables": {"username": cfg["username"]}},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError("LeetCode profile query returned errors: " + str(payload["errors"])[:300])
    user = (payload.get("data") or {}).get("matchedUser")
    if not user:
        raise RuntimeError("LeetCode profile was not returned; check username or public visibility.")

    stats = user.get("submitStats") or {}
    counts = {
        str(item.get("difficulty", "unknown")).lower(): int(item.get("count", 0))
        for item in stats.get("acSubmissionNum", [])
    }

    # Recent accepted submissions are a top-level GraphQL field, not a field on UserNode.
    # Treat this as optional so profile stats still work if the public schema changes.
    recent: list[dict[str, Any]] = []
    recent_note = "Recent accepted submissions were not available from the public endpoint."
    recent_query = """query recentAccepted($username: String!) {
      recentAcSubmissionList(username: $username) {
        id title titleSlug timestamp
      }
    }"""
    try:
        recent_response = requests.post(
            endpoint,
            headers=headers,
            json={"query": recent_query, "variables": {"username": cfg["username"]}},
            timeout=TIMEOUT,
        )
        recent_response.raise_for_status()
        recent_payload = recent_response.json()
        recent_items = (recent_payload.get("data") or {}).get("recentAcSubmissionList")
        if recent_items is not None and not recent_payload.get("errors"):
            for item in recent_items:
                timestamp = item.get("timestamp")
                recent.append({
                    "id": str(item.get("id", "")),
                    "title": item.get("title"),
                    "title_slug": item.get("titleSlug"),
                    "timestamp": int(timestamp) if str(timestamp or "").isdigit() else None,
                    "status": "Accepted",
                })
            recent_note = "Limited recent accepted-submission feed; not a complete lifetime activity history."
        elif recent_payload.get("errors"):
            recent_note = "Recent submissions query was rejected by the public GraphQL schema; profile totals were collected."
    except (requests.RequestException, ValueError, TypeError) as exc:
        recent_note = f"Recent submissions unavailable ({type(exc).__name__}); profile totals were collected."

    return {
        "profile_url": cfg["url"],
        "username": user.get("username"),
        "real_name": (user.get("profile") or {}).get("realName") or None,
        "ranking": (user.get("profile") or {}).get("ranking"),
        "accepted_problem_counts": counts,
        "recent_accepted_submissions": recent,
        "recent_submissions_note": recent_note,
    }


def _find_first_number(text: str, patterns: list[str]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def collect_geeksforgeeks() -> dict[str, Any]:
    cfg = PROFILES["geeksforgeeks"]
    text, structured, title = _page_text_and_json(cfg["url"])
    # The GFG page layout changes over time. Extract only numbers with explicit nearby labels.
    total = _find_first_number(text, [
        r"(?:total\s+)?problems?\s+solved\s*[:\-]?\s*([\d,]+)",
        r"solved\s+problems?\s*[:\-]?\s*([\d,]+)",
        r"questions?\s+solved\s*[:\-]?\s*([\d,]+)",
    ])
    score = _find_first_number(text, [r"coding\s+score\s*[:\-]?\s*([\d,]+)"])
    # Use a public, no-auth stats endpoint only as a fallback for aggregate counts.
    fallback_used = False
    if total is None:
        try:
            fallback = _get("https://gfg-stats.tashif.codes/jaswanthrathore/profile").json()
            data = fallback.get("data", fallback)
            for key in ("totalProblemsSolved", "total_problems_solved", "problemsSolved"):
                if isinstance(data, dict) and isinstance(data.get(key), (int, float, str)):
                    value = str(data[key]).replace(",", "")
                    if value.isdigit():
                        total = int(value)
                        break
            for key in ("codingScore", "coding_score"):
                if isinstance(data, dict) and isinstance(data.get(key), (int, float, str)):
                    value = str(data[key]).replace(",", "")
                    if value.isdigit():
                        score = int(value)
                        break
            fallback_used = total is not None or score is not None
        except (requests.RequestException, ValueError, TypeError):
            pass
    return {
        "profile_url": cfg["url"],
        "page_title": title or None,
        "total_problems_solved": total,
        "coding_score": score,
        "fallback_stats_api_used": fallback_used,
        "collection_note": "Null values mean the public page/API did not expose a reliably labelled value; no value is guessed.",
    }


COLLECTORS = {
    "google_skills": collect_google_skills,
    "leetcode": collect_leetcode,
    "geeksforgeeks": collect_geeksforgeeks,
}


def collect_all() -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {},
    }
    for name, collector in COLLECTORS.items():
        try:
            result["sources"][name] = {"status": "ok", "data": collector()}
        except Exception as exc:  # keep other platforms working if one source blocks requests
            result["sources"][name] = {
                "status": "error",
                "error": f"{type(exc).__name__}: {str(exc)[:350]}",
            }
    return result
