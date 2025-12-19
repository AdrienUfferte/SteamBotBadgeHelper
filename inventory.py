def is_trading_card(desc):
    for tag in desc.get("tags", []):
        if (
            tag.get("category") == "item_class"
            and tag.get("localized_tag_name") == "Trading Card"
        ):
            return True
    return False


def get_trading_cards(session, steam_id):
    print("DEBUG inventory: start fetching inventory")

    base_url = f"https://steamcommunity.com/inventory/{steam_id}/753/6"

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

        r = session.get(base_url, params=params)
        r.raise_for_status()
        data = r.json()

        assets = data.get("assets", [])
        descriptions = data.get("descriptions", [])

        print(
            f"DEBUG page: assets={len(assets)}, "
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

    cards_by_app = {}
    total_cards_found = 0

    # --- Analyse ---
    for asset in all_assets:
        desc = all_descriptions.get(asset["classid"])
        if not desc:
            continue

        if not is_trading_card(desc):
            continue

        # ✅ appid CORRECT
        appid = desc.get("market_fee_app")
        if not appid:
            continue

        # Nom du jeu
        game_name = None
        for tag in desc.get("tags", []):
            if tag.get("category") == "Game":
                game_name = tag.get("localized_tag_name")
                break

        cards_by_app.setdefault(appid, {
            "game_name": game_name,
            "cards": {}
        })

        cards = cards_by_app[appid]["cards"]
        classid = asset["classid"]

        cards.setdefault(classid, {
            "quantity": 0,
            "asset_ids": [],
            "market_hash_name": desc["market_hash_name"]
        })

        amount = int(asset.get("amount", 1))

        cards[classid]["quantity"] += amount
        cards[classid]["asset_ids"].extend(
            [asset["assetid"]] * amount
        )

        total_cards_found += amount

        print(
            f"FOUND CARD: {desc.get('name')} "
            f"| game={game_name} "
            f"| appid={appid} "
            f"| qty={amount}"
        )

    print(f"DEBUG inventory result: {len(cards_by_app)} games detected")
    print(f"DEBUG total cards found: {total_cards_found}")

    return cards_by_app
