import logging
import requests

def is_trading_card(desc):
    for tag in desc.get("tags", []):
        if (
            tag.get("category") == "item_class"
            and tag.get("localized_tag_name") == "Trading Card"
        ):
            return True
    return False


def get_trading_cards(session, steam_id, badges):
    logging.debug("start fetching inventory")

    base_url = f"https://steamcommunity.com/inventory/{steam_id}/753/6"

    # Warm up by visiting the inventory page
    inventory_page_url = f"https://steamcommunity.com/profiles/{steam_id}/inventory/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    warmup_resp = session.get(inventory_page_url, headers=headers)
    logging.debug(f"Inventory page warmup status: {warmup_resp.status_code}")

    start_assetid = 0
    all_assets = []
    all_descriptions = {}

    # --- Pagination ---
    while True:
        params = {
            "l": "english",
            "count": 200,
            "start_assetid": start_assetid
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://steamcommunity.com/my/inventory",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://steamcommunity.com",
        }

        r = session.get(base_url, params=params, headers=headers)
        logging.debug(f"Request URL: {r.url}")
        logging.debug(f"Response status: {r.status_code}")
        logging.debug(f"Response reason: {r.reason}")
        if r.status_code != 200:
            logging.debug(f"Response headers: {dict(r.headers)}")
            logging.debug(f"Response text (first 500 chars): {r.text[:500]}")
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            logging.error("Failed to fetch inventory. Proceeding with empty inventory.")
            return {}
        data = r.json()

        assets = data.get("assets", [])
        descriptions = data.get("descriptions", [])

        logging.debug(
            f"page: assets={len(assets)}, "
            f"descriptions={len(descriptions)}, "
            f"more_items={data.get('more_items')}"
        )

        all_assets.extend(assets)

        for d in descriptions:
            all_descriptions[d["classid"]] = d

        if not data.get("more_items"):
            break

        start_assetid = data.get("last_assetid")
        if not start_assetid:
            break

    from config import BADGE_MAX_LEVEL
    from badges import get_card_names

    cards_by_app = {}
    for appid, level in badges.items():
        if level >= BADGE_MAX_LEVEL:
            continue
        card_names = get_card_names(appid, session=session, steam_id=steam_id)
        cards_by_app[appid] = {
            "game_name": "",  # will set later
            "cards": {
                name: {"market_hash_name": name, "quantity": 0, "asset_ids": []}
                for name in card_names
            }
        }

    # Update from assets
    for asset in all_assets:
        desc = all_descriptions.get(asset["classid"])
        if not desc or not is_trading_card(desc):
            continue
        appid = desc.get("market_fee_app")
        if not appid or appid not in cards_by_app:
            continue
        name = desc["market_hash_name"]
        if name in cards_by_app[appid]["cards"]:
            amount = int(asset.get("amount", 1))
            cards_by_app[appid]["cards"][name]["quantity"] += amount
            cards_by_app[appid]["cards"][name]["asset_ids"].extend([asset["assetid"]] * amount)

    # Set game_name
    for appid in cards_by_app:
        for desc in all_descriptions.values():
            if desc.get("market_fee_app") == appid:
                game_name = None
                for tag in desc.get("tags", []):
                    if tag.get("category") == "Game":
                        game_name = tag.get("localized_tag_name")
                        break
                cards_by_app[appid]["game_name"] = game_name or str(appid)
                break

    print(f"DEBUG inventory result: {len(cards_by_app)} games detected")

    return cards_by_app
