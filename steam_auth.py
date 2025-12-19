import json
import requests

def login_with_cookies(cookie_file="steam_cookies.json"):
    session = requests.Session()

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/")
        )

    return session
