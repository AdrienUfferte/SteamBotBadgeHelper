from config import MIN_PRICE_EUR, GAME_ID, CURRENCY_EUR, TEST_MODE

def get_lowest_market_price(client, market_hash_name):
    price_info = client.market.fetch_price(market_hash_name)

    if not price_info or not price_info.get("lowest_price"):
        return MIN_PRICE_EUR

    raw_price = price_info["lowest_price"]
    price = float(
        raw_price
        .replace("€", "")
        .replace(",", ".")
        .strip()
    )

    return max(price, MIN_PRICE_EUR)


def sell_card(client, asset_id, market_hash_name):
    price = get_lowest_market_price(client, market_hash_name)

    if TEST_MODE:
        print(
            f"[TEST] SELL asset_id={asset_id} "
            f"({market_hash_name}) at {price:.2f} €"
        )
        return

    print(
        f"[LIVE] SELL asset_id={asset_id} "
        f"({market_hash_name}) at {price:.2f} €"
    )

    client.market.sell_item(
        asset_id=asset_id,
        price=price,
        game_id=GAME_ID,
        currency=CURRENCY_EUR
    )
