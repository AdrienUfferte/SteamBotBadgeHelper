import json
import logging
import requests

def login_with_cookies(cookie_file="steam_cookies.json"):
    session = requests.Session()

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    logging.debug(f"Loaded {len(cookies)} cookies from {cookie_file}")
    cookie_names = [c["name"] for c in cookies]
    logging.debug(f"Cookie names: {cookie_names}")

    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/")
        )

    # Warm up the session by visiting the main page
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    warmup_response = session.get("https://steamcommunity.com", headers=headers)
    logging.debug(f"Warmup response status: {warmup_response.status_code}")

    return session
