import time
from config import MIN_PRICE_EUR

# Cache global des prix
_PRICE_CACHE = {}

def get_lowest_price(session, market_hash_name, delay=1.0):
    """
    Récupère le prix le plus bas du market Steam.
    Utilise un cache + un délai pour éviter le rate limit.
    """

    # Cache : un seul appel par item
    if market_hash_name in _PRICE_CACHE:
        return _PRICE_CACHE[market_hash_name]

    time.sleep(delay)  # ⏳ indispensable

    url = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "currency": 3,  # EUR
        "appid": 753,
        "market_hash_name": market_hash_name
    }

    r = session.get(url, params=params)

    # Gestion du rate limit
    if r.status_code == 429:
        print(f"WARNING rate limit on price for {market_hash_name}")
        price = MIN_PRICE_EUR
    else:
        r.raise_for_status()
        data = r.json()

        raw_price = data.get("lowest_price")
        if not raw_price:
            price = MIN_PRICE_EUR
        else:
            price = max(
                float(
                    raw_price
                    .replace("€", "")
                    .replace(",", ".")
                    .strip()
                ),
                MIN_PRICE_EUR
            )

    _PRICE_CACHE[market_hash_name] = price
    return price
