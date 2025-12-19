import time
from config import MIN_PRICE_EUR

# -------------------------------------------------------------------
# Configuration du throttling global du market Steam
# -------------------------------------------------------------------

_MARKET_LAST_CALL = 0.0
MARKET_DELAY_SECONDS = 2.5  # 🔒 2.5s recommandé (3.0 si inventaire énorme)

# Cache global des prix (1 appel max par item)
_PRICE_CACHE = {}


def _throttle_market(backoff=False):
    """
    Garantit un délai minimum entre TOUTES les requêtes market.
    backoff=True double le délai (utile après un 429).
    """
    global _MARKET_LAST_CALL

    delay = MARKET_DELAY_SECONDS * (2 if backoff else 1)

    now = time.time()
    elapsed = now - _MARKET_LAST_CALL

    if elapsed < delay:
        time.sleep(delay - elapsed)

    _MARKET_LAST_CALL = time.time()


# -------------------------------------------------------------------
# Prix le plus bas actuel
# -------------------------------------------------------------------

def get_lowest_price(session, market_hash_name):
    """
    Récupère le prix le plus bas du market Steam (EUR).
    Cache + throttling global.
    """

    # Cache : un seul appel par item
    if market_hash_name in _PRICE_CACHE:
        return _PRICE_CACHE[market_hash_name]

    _throttle_market()

    url = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "currency": 3,  # EUR
        "appid": 753,
        "market_hash_name": market_hash_name
    }

    r = session.get(url, params=params)

    if r.status_code == 429:
        print(f"WARNING rate limit (priceoverview) for {market_hash_name}")
        _throttle_market(backoff=True)
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


# -------------------------------------------------------------------
# Analyse de la concurrence (3 premières offres)
# -------------------------------------------------------------------

def has_three_or_more_at_lowest_price(session, market_hash_name, lowest_price):
    """
    Retourne True si les 3 premières offres visibles
    sont au même prix que lowest_price.
    Gère les deux formats possibles de listinginfo (dict ou list).
    """

    _throttle_market()

    url = f"https://steamcommunity.com/market/listings/753/{market_hash_name}/render/"
    params = {
        "start": 0,
        "count": 3,
        "currency": 3
    }

    r = session.get(url, params=params)

    if r.status_code == 429:
        print(f"WARNING rate limit (listings) for {market_hash_name}")
        _throttle_market(backoff=True)
        return False

    r.raise_for_status()
    data = r.json()

    listinginfo = data.get("listinginfo", [])

    prices = []

    # ✅ Cas 1 : listinginfo est un dict
    if isinstance(listinginfo, dict):
        iterable = listinginfo.values()
    # ✅ Cas 2 : listinginfo est une liste
    elif isinstance(listinginfo, list):
        iterable = listinginfo
    else:
        return False

    for info in iterable:
        price_cents = info.get("price")
        if price_cents is not None:
            prices.append(price_cents / 100.0)

    # Marché saturé si les 3 premières sont au même prix
    return (
        len(prices) == 3
        and all(abs(p - lowest_price) < 0.0001 for p in prices)
    )



# -------------------------------------------------------------------
# Calcul du prix final de vente
# -------------------------------------------------------------------

def compute_sale_price(lowest_price, has_three_or_more):
    """
    Applique la règle métier :
    - ≤ 2 offres → on garde le prix
    - ≥ 3 offres → on baisse d'1 centime
    - jamais < MIN_PRICE_EUR
    """
    if not has_three_or_more:
        return lowest_price

    return max(lowest_price - 0.01, MIN_PRICE_EUR)
