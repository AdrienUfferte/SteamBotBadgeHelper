import logging
import re
import time
from html import unescape

import requests

from config import STEAM_API_KEY

_APP_NAME_CACHE = {}
_BADGE_NAME_CACHE = {}

def _strip_html(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return " ".join(text.split()).strip()

def _extract_text_by_class(html, class_name):
    pattern = rf'class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'][^>]*>(.*?)</[^>]+>'
    match = re.search(pattern, html, re.S)
    if not match:
        return None
    text = _strip_html(match.group(1))
    return text or None

def _append_query_param(url, query):
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{query}"

def _fetch_text(url, headers, session=None):
    requester = session or requests
    r = requester.get(url, headers=headers)
    r.raise_for_status()
    return r.text

def _parse_badge_names_from_badges_xml(xml_text):
    badge_names = {}
    for block in re.findall(r"<badge>.*?</badge>", xml_text, re.S):
        id_match = re.search(r"<badgeid>(\d+)</badgeid>", block)
        if not id_match:
            id_match = re.search(r"<id>(\d+)</id>", block)
        if not id_match:
            continue
        badge_id = int(id_match.group(1))

        name_match = re.search(r"<name>(.*?)</name>", block, re.S)
        if not name_match:
            name_match = re.search(r"<badge_name>(.*?)</badge_name>", block, re.S)
        if not name_match:
            name_match = re.search(r"<title>(.*?)</title>", block, re.S)
        if not name_match:
            continue
        title = _strip_html(name_match.group(1))
        if title:
            badge_names[badge_id] = title
    return badge_names

def _parse_badge_title_from_xml(xml_text):
    for pattern in (
        r"<badge_name>(.*?)</badge_name>",
        r"<name>(.*?)</name>",
        r"<title>(.*?)</title>",
    ):
        match = re.search(pattern, xml_text, re.S)
        if match:
            title = _strip_html(match.group(1))
            if title:
                return title
    return None

def _parse_badge_names_from_script(html):
    badge_names = {}
    for match in re.finditer(
        r'"badgeid"\s*:\s*(\d+).*?"name"\s*:\s*"([^"]+)"',
        html,
        re.S,
    ):
        title = _strip_html(match.group(2))
        if title:
            badge_names[int(match.group(1))] = title
    return badge_names


def _parse_badge_names_from_badges_page(html):
    badge_names = {}
    rows = re.split(r'<div[^>]+class=["\'][^"\']*\bbadge_row\b[^"\']*["\'][^>]*>', html)
    for row in rows[1:]:
        block = row
        badge_id = None
        for pattern in (r'/badges/(\d+)', r'badgeid=(\d+)', r'data-badgeid=["\'](\d+)["\']'):
            m = re.search(pattern, block)
            if m:
                badge_id = int(m.group(1))
                break
        if badge_id is None:
            continue

        title = (
            _extract_text_by_class(block, "badge_row_title")
            or _extract_text_by_class(block, "badge_title")
            or _extract_text_by_class(block, "badge_title_row")
            or _extract_text_by_class(block, "badge_info_title")
            or _extract_text_by_class(block, "profile_badge_title")
        )
        if not title:
            continue
        if title:
            badge_names[badge_id] = title

    return badge_names


def get_profile_badge_names(session=None, steam_id=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://steamcommunity.com/my/badges",
    }

    try:
        def fetch_all(base_url, session_to_use):
            badge_names = {}
            page = 1
            while True:
                url = f"{base_url}?l=english&p={page}"
                text = _fetch_text(url, headers, session=session_to_use)
                parsed = _parse_badge_names_from_badges_page(text)
                if not parsed:
                    parsed = _parse_badge_names_from_badges_xml(text)
                if not parsed:
                    parsed = _parse_badge_names_from_script(text)
                if not parsed and page == 1:
                    xml_url = _append_query_param(url, "xml=1")
                    xml_text = _fetch_text(xml_url, headers, session=session_to_use)
                    parsed = _parse_badge_names_from_badges_xml(xml_text)
                if not parsed:
                    break
                badge_names.update(parsed)
                if "pagebtn_next" not in text:
                    break
                page += 1
            return badge_names

        candidates = []
        if session:
            candidates.append(("https://steamcommunity.com/my/badges", session))
            if steam_id:
                candidates.append((f"https://steamcommunity.com/profiles/{steam_id}/badges/", session))
        elif steam_id:
            candidates.append((f"https://steamcommunity.com/profiles/{steam_id}/badges/", None))
        else:
            return {}

        for base_url, session_to_use in candidates:
            try:
                badge_names = fetch_all(base_url, session_to_use)
            except requests.exceptions.RequestException as e:
                logging.warning(f"Failed to fetch badge names from {base_url}: {e}")
                continue
            if badge_names:
                return badge_names

        return {}
    except requests.exceptions.RequestException as e:
        logging.warning(f"Failed to fetch badge names from profile page: {e}")
        return {}


def _parse_badge_title(html):
    for pattern in (
        "badge_info_title",
        "profile_badge_title",
        "badge_title",
        "badge_detail_title",
        "badge_title_row",
    ):
        title = _extract_text_by_class(html, pattern)
        if title:
            return title
    return None


def get_badge_name(badge_id, session=None, steam_id=None):
    if badge_id in _BADGE_NAME_CACHE:
        return _BADGE_NAME_CACHE[badge_id]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://steamcommunity.com/my/badges",
    }

    urls = []
    if session:
        urls.append(f"https://steamcommunity.com/my/badges/{badge_id}?l=english")
    if steam_id:
        urls.append(f"https://steamcommunity.com/profiles/{steam_id}/badges/{badge_id}?l=english")
    urls.append(f"https://steamcommunity.com/badges/{badge_id}?l=english")

    for url in urls:
        for session_to_use in ((session, None) if session else (None,)):
            try:
                text = _fetch_text(url, headers, session=session_to_use)
            except requests.exceptions.RequestException as e:
                logging.debug(f"Badge name request failed for {badge_id} at {url}: {e}")
                continue

            title = _parse_badge_title(text) or _parse_badge_title_from_xml(text)
            if title:
                _BADGE_NAME_CACHE[badge_id] = title
                return title

            xml_url = _append_query_param(url, "xml=1")
            try:
                xml_text = _fetch_text(xml_url, headers, session=session_to_use)
            except requests.exceptions.RequestException as e:
                logging.debug(f"Badge name XML request failed for {badge_id} at {xml_url}: {e}")
                continue
            title = _parse_badge_title_from_xml(xml_text) or _parse_badge_title(xml_text)
            if title:
                _BADGE_NAME_CACHE[badge_id] = title
                return title

    _BADGE_NAME_CACHE[badge_id] = None
    return None

def _fetch_badges(steam_id):
    url = "https://api.steampowered.com/IPlayerService/GetBadges/v1/"
    params = {"key": STEAM_API_KEY, "steamid": steam_id}

    for attempt in range(3):
        try:
            r = requests.get(url, params=params)
            r.raise_for_status()
            return r.json()["response"]["badges"]
        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600:
                logging.warning(
                    f"{e.response.status_code} Server Error for badges API, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)"
                )
                time.sleep(2**attempt)
            else:
                raise
        except requests.exceptions.RequestException as e:
            logging.warning(
                f"Request error fetching badges: {e}, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)"
            )
            time.sleep(2**attempt)

    logging.error("Failed to fetch badges after 3 attempts, returning empty list.")
    return []


def get_owned_games_map(steam_id):
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": 1,
        "include_played_free_games": 1,
    }

    for attempt in range(3):
        try:
            r = requests.get(url, params=params)
            r.raise_for_status()
            games = r.json().get("response", {}).get("games", [])
            return {game["appid"]: game["name"] for game in games if "name" in game}
        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600:
                logging.warning(
                    f"{e.response.status_code} Server Error for owned games, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)"
                )
                time.sleep(2**attempt)
            else:
                raise
        except requests.exceptions.RequestException as e:
            logging.warning(
                f"Request error fetching owned games: {e}, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)"
            )
            time.sleep(2**attempt)

    logging.warning("Failed to fetch owned games after 3 attempts, returning empty map.")
    return {}


def get_app_name(appid):
    if appid in _APP_NAME_CACHE:
        return _APP_NAME_CACHE[appid]

    url = "https://store.steampowered.com/api/appdetails/"
    params = {"appids": appid}

    for attempt in range(3):
        try:
            time.sleep(0.4)
            r = requests.get(url, params=params)
            if r.status_code == 429:
                time.sleep(2**attempt)
                continue
            r.raise_for_status()
            payload = r.json().get(str(appid), {})
            name = payload.get("data", {}).get("name") if payload.get("success") else None
            _APP_NAME_CACHE[appid] = name
            return name
        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600:
                logging.warning(
                    f"{e.response.status_code} Server Error for appdetails, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)"
                )
                time.sleep(2**attempt)
            else:
                raise
        except requests.exceptions.RequestException as e:
            logging.warning(
                f"Request error fetching app name for {appid}: {e}, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)"
            )
            time.sleep(2**attempt)

    logging.warning(f"Failed to fetch app name for {appid}, using fallback.")
    _APP_NAME_CACHE[appid] = None
    return None


def get_badges(steam_id):
    return {
        badge["appid"]: badge["level"]
        for badge in _fetch_badges(steam_id)
        if "appid" in badge
    }


def get_badges_list(steam_id):
    return _fetch_badges(steam_id)

def _parse_card_names_from_gamecards(html):
    names = set()
    blocks = re.findall(r'<div class="badge_card_set_title[^>]*>(.*?)</div>', html, re.S)
    for block in blocks:
        text = re.sub(r"<[^>]+>", "", block)
        text = unescape(text).strip()
        if not text:
            continue
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line:
            names.add(first_line)
    return names


def get_card_names(appid, session=None, steam_id=None):
    count = 100
    json_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://steamcommunity.com/market/search?appid=753",
        "Origin": "https://steamcommunity.com",
        "X-Requested-With": "XMLHttpRequest",
    }
    html_headers = {
        "User-Agent": json_headers["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://steamcommunity.com/my/badges",
    }

    def fetch_with_filters(filter_params):
        card_names = set()
        start = 0
        retry_count = 0
        max_429_retries = 6
        session_to_use = session or requests
        while True:
            time.sleep(1)  # Rate limit delay
            url = "https://steamcommunity.com/market/search/render/"
            params = {
                "query": "",
                "start": start,
                "count": count,
                "search_descriptions": 0,
                "sort_column": "name",
                "sort_dir": "asc",
                "appid": 753,
                "category_753_ContextId[]": 6,
                "category_753_ItemClass[]": "tag_item_class_2",  # Trading Card
                "norender": 1,
            }
            params.update(filter_params)

            r = session_to_use.get(url, params=params, headers=json_headers)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 5
                retry_count += 1
                if retry_count > max_429_retries:
                    logging.warning(
                        f"Rate limit persists for appid {appid}, skipping market lookup after {max_429_retries} retries."
                    )
                    return set()
                logging.warning(f"Rate limited fetching card names for appid {appid}, retrying in {delay} seconds...")
                time.sleep(delay)
                continue
            r.raise_for_status()
            data = r.json()
            results = data.get("results") or []
            for item in results:
                name = item.get("hash_name") or item.get("market_hash_name")
                if name:
                    card_names.add(name)
            if len(results) < count:
                break
            start += count
        return card_names

    try:
        if session or steam_id:
            if session:
                url = f"https://steamcommunity.com/my/gamecards/{appid}"
                r = session.get(url, headers=html_headers)
            else:
                url = f"https://steamcommunity.com/profiles/{steam_id}/gamecards/{appid}"
                r = requests.get(url, headers=html_headers)
            r.raise_for_status()
            card_names = _parse_card_names_from_gamecards(r.text)
            if card_names:
                return card_names

        for filter_params in (
            {"category_753_Game[]": f"tag_app_{appid}"},
            {"category_753_Appid[]": appid},
        ):
            card_names = fetch_with_filters(filter_params)
            if card_names:
                return card_names
    except requests.exceptions.RequestException as e:
        logging.warning(f"Failed to fetch card names for appid {appid}: {e}")
        return set()
    logging.warning(f"No card names found for appid {appid}")
    return set()
