import re
import requests
import time
import logging
from urllib.parse import quote

from config import MIN_PRICE_EUR

# -------------------------------------------------------------------
# Throttling global du market Steam
# -------------------------------------------------------------------

_MARKET_LAST_CALL = 0.0
MARKET_DELAY_SECONDS = 2.5  # augmente à 3.0 si tu vois encore des 429


def _throttle_market(backoff=False):
    global _MARKET_LAST_CALL

    delay = MARKET_DELAY_SECONDS * (2 if backoff else 1)
    now = time.time()
    elapsed = now - _MARKET_LAST_CALL

    if elapsed < delay:
        time.sleep(delay - elapsed)

    _MARKET_LAST_CALL = time.time()


# -------------------------------------------------------------------
# Caches
# -------------------------------------------------------------------

_PRICEOVERVIEW_CACHE = {}      # market_hash_name -> lowest_price (buyer) en EUR
_ITEM_NAMEID_CACHE = {}        # market_hash_name -> item_nameid
_HISTOGRAM_CACHE = {}          # market_hash_name -> (lowest_seller_price_eur, qty_at_lowest)


# -------------------------------------------------------------------
# Outils parsing prix
# -------------------------------------------------------------------

def _parse_eur_price(price_str: str) -> float:
    """
    Convertit un prix type '0,05 €' ou '€0.05' en float 0.05
    """
    s = price_str.replace("€", "").replace(",", ".").strip()
    return float(s)


# -------------------------------------------------------------------
# (Optionnel) priceoverview: utile pour log/affichage, mais pas fiable pour ta règle de quantité
# -------------------------------------------------------------------

def get_lowest_price_buyer(session, market_hash_name):
    """
    Prix le plus bas côté acheteur (priceoverview). Peut diverger du prix vendeur à cause des frais/arrondis.
    Cache + throttling.
    """
    if market_hash_name in _PRICEOVERVIEW_CACHE:
        return _PRICEOVERVIEW_CACHE[market_hash_name]

    _throttle_market()

    url = "https://steamcommunity.com/market/priceoverview/"
    params = {"currency": 3, "appid": 753, "market_hash_name": market_hash_name}
    r = session.get(url, params=params)

    if r.status_code == 429:
        _throttle_market(backoff=True)
        return MIN_PRICE_EUR

    r.raise_for_status()
    data = r.json()

    raw = data.get("lowest_price")
    if not raw:
        price = MIN_PRICE_EUR
    else:
        price = max(_parse_eur_price(raw), MIN_PRICE_EUR)

    _PRICEOVERVIEW_CACHE[market_hash_name] = price
    return price


# -------------------------------------------------------------------
# Récupération item_nameid (indispensable pour itemordershistogram)
# -------------------------------------------------------------------

def get_item_nameid(session, market_hash_name):
    """
    Récupère l'item_nameid en scrappant la page listing (HTML).
    Cache + throttling.
    """
    if market_hash_name in _ITEM_NAMEID_CACHE:
        return _ITEM_NAMEID_CACHE[market_hash_name]

    _throttle_market()

    encoded = quote(market_hash_name, safe="")
    url = f"https://steamcommunity.com/market/listings/753/{encoded}"

    r = session.get(url)
    if r.status_code == 429:
        _throttle_market(backoff=True)
        r = session.get(url)

    r.raise_for_status()
    html = r.text

    # Pattern le plus courant
    m = re.search(r"Market_LoadOrderSpread\(\s*(\d+)\s*\)", html)
    if not m:
        # Pattern alternatif parfois rencontré
        m = re.search(r"item_nameid\"\s*:\s*\"?(\d+)\"?", html)

    if not m:
        raise RuntimeError(f"Impossible de trouver item_nameid pour {market_hash_name}")

    item_nameid = int(m.group(1))
    _ITEM_NAMEID_CACHE[market_hash_name] = item_nameid
    return item_nameid


# -------------------------------------------------------------------
# Lecture du carnet d'ordres vendeur (ce qui correspond à ton tableau Prix/Quantité)
# -------------------------------------------------------------------

def get_lowest_seller_and_qty(session, market_hash_name, country="FR", language="french"):
    """
    Retourne (lowest_seller_price_eur, qty_at_lowest) à partir de itemordershistogram.
    Cache + throttling.
    """
    if market_hash_name in _HISTOGRAM_CACHE:
        return _HISTOGRAM_CACHE[market_hash_name]

    item_nameid = get_item_nameid(session, market_hash_name)

    _throttle_market()

    url = "https://steamcommunity.com/market/itemordershistogram"
    params = {
        "country": country,
        "language": language,
        "currency": 3,          # EUR
        "item_nameid": item_nameid,
        "two_step": 1
    }

    r = session.get(url, params=params)

    if r.status_code == 429:
        _throttle_market(backoff=True)
        r = session.get(url, params=params)

    if r.status_code == 429:
        # On abandonne proprement: on ne veut pas crasher le run
        result = (MIN_PRICE_EUR, 999999)
        _HISTOGRAM_CACHE[market_hash_name] = result
        return result

    r.raise_for_status()
    data = r.json()

    # sell_order_graph: liste de points [price, quantity, ...]
    graph = data.get("sell_order_graph") or []
    # print(
    #     f"[DEBUG] HISTOGRAM {market_hash_name} "
    #     f"(country={country}, currency=EUR)"
    # )

    # for price, qty, *_ in graph[:5]:
    #     print(f"[DEBUG]   SELL {price:.2f} € -> qty {int(qty)}")
    if not graph:
        # Aucun ordre vendeur visible (rare), on retombe sur min
        result = (MIN_PRICE_EUR, 0)
        _HISTOGRAM_CACHE[market_hash_name] = result
        return result

    lowest_price = float(graph[0][0])
    qty_at_lowest = int(graph[0][1])

    lowest_price = max(lowest_price, MIN_PRICE_EUR)

    result = (lowest_price, qty_at_lowest)
    _HISTOGRAM_CACHE[market_hash_name] = result
    return result


def get_highest_buy_price(session, market_hash_name):
    """
    Retourne le prix d'achat le plus élevé depuis buy_order_graph.
    """
    item_nameid = get_item_nameid(session, market_hash_name)

    _throttle_market()

    url = "https://steamcommunity.com/market/itemordershistogram"
    params = {
        "country": "FR",
        "language": "french",
        "currency": 3,          # EUR
        "item_nameid": item_nameid,
        "two_step": 1
    }

    r = session.get(url, params=params)

    if r.status_code == 429:
        _throttle_market(backoff=True)
        r = session.get(url, params=params)

    if r.status_code == 429:
        return MIN_PRICE_EUR

    r.raise_for_status()
    data = r.json()

    buy_graph = data.get("buy_order_graph") or []

    if not buy_graph:
        return MIN_PRICE_EUR

    highest_price = float(buy_graph[0][0])
    highest_price = max(highest_price, MIN_PRICE_EUR)

    return highest_price


# -------------------------------------------------------------------
# Décision de prix selon ta règle
# -------------------------------------------------------------------

def compute_sale_price_from_histogram(lowest_seller_price, qty_at_lowest):
    """
    Règle métier:
    - si qty <= 2: vendre au prix mini
    - si qty >= 3: vendre à (prix mini - 0.01), plancher MIN_PRICE_EUR
    """
    if qty_at_lowest <= 2:
        return lowest_seller_price

    return max(lowest_seller_price - 0.01, MIN_PRICE_EUR)

def sell_item(session, assetid, price_eur):
    """
    Met en vente un item Steam (1 exemplaire).
    price_eur = prix acheteur final (ex: 0.04)
    """
    _throttle_market()

    # Steam attend un prix en centimes (acheteur)
    price_cents = int(round(price_eur * 100))

    url = "https://steamcommunity.com/market/sellitem/"

    payload = {
        "sessionid": session.cookies.get("sessionid"),
        "appid": 753,
        "contextid": 6,
        "assetid": assetid,
        "amount": 1,
        "price": price_cents,
    }

    headers = {
        "Referer": "https://steamcommunity.com/my/inventory",
        "Origin": "https://steamcommunity.com",
    }

    r = session.post(url, data=payload, headers=headers)

    if r.status_code == 429:
        _throttle_market(backoff=True)
        raise RuntimeError("Rate limit lors de la vente")

    r.raise_for_status()
    data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Echec vente asset {assetid}: {data}")

    return True


def get_buy_orders(session):
    """
    Récupère les ordres d'achat actifs depuis la page My Listings.
    Retourne un dict market_hash_name -> (price_eur, quantity)
    """
    for attempt in range(3):
        try:
            _throttle_market()

            url = "https://steamcommunity.com/market/mylistings/"
            r = session.get(url)

            if r.status_code == 429:
                _throttle_market(backoff=True)
                r = session.get(url)

            r.raise_for_status()
            html = r.text

            buy_orders = {}

            # Chercher les lignes d'ordres d'achat
            # Les ordres d'achat sont dans des div avec classe "market_listing_row"
            # et contiennent "Buy Order" dans le texte

            # Utiliser regex pour trouver les ordres d'achat
            # Pattern approximatif pour extraire les infos
            # C'est fragile, mais pour commencer

            # Trouver tous les blocs d'ordres d'achat
            buy_order_pattern = r'<div class="market_listing_row market_recent_listing_row"[^>]*>.*?Ordre d\'achat.*?</div>'
            matches = re.findall(buy_order_pattern, html, re.DOTALL)

            for match in matches:
                # Extraire le nom de l'item
                name_match = re.search(r'<span class="market_listing_item_name"[^>]*>([^<]+)</span>', match)
                if not name_match:
                    continue
                market_hash_name = name_match.group(1).strip()

                # Extraire le prix
                price_match = re.search(r'<span class="market_listing_price[^"]*">([^<]+)</span>', match)
                if not price_match:
                    continue
                price_str = price_match.group(1).strip()
                price_eur = _parse_eur_price(price_str)

                # Extraire la quantité
                qty_match = re.search(r'<span class="market_listing_buyorder_qty">(\d+)</span>', match)
                if not qty_match:
                    continue
                quantity = int(qty_match.group(1))

                buy_orders[market_hash_name] = (price_eur, quantity)

            return buy_orders
        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600:
                logging.warning(f"{e.response.status_code} Server Error for market listings, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)")
                time.sleep(2**attempt)
            else:
                raise
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error fetching market listings: {e}, retrying in {2**attempt} seconds... (attempt {attempt+1}/3)")
            time.sleep(2**attempt)
    
    logging.error("Failed to fetch market listings after 3 attempts, returning empty dict.")
    return {}


def create_buy_order(session, market_hash_name, price_eur, quantity=1):
    """
    Crée un ordre d'achat pour un item.
    price_eur = prix par unité (acheteur)
    """
    _throttle_market()

    item_nameid = get_item_nameid(session, market_hash_name)

    # Prix en centimes
    price_cents = int(round(price_eur * 100))

    url = "https://steamcommunity.com/market/createbuyorder/"

    payload = {
        "sessionid": session.cookies.get("sessionid"),
        "currency": 3,  # EUR
        "appid": 753,
        "market_hash_name": market_hash_name,
        "price_total": price_cents * quantity,
        "quantity": quantity,
        "billing_state": "",
        "save_my_address": 0
    }

    headers = {
        "Referer": f"https://steamcommunity.com/market/listings/753/{quote(market_hash_name)}",
        "Origin": "https://steamcommunity.com",
    }

    r = session.post(url, data=payload, headers=headers)

    if r.status_code == 429:
        _throttle_market(backoff=True)
        raise RuntimeError("Rate limit lors de la création d'ordre d'achat")

    r.raise_for_status()
    data = r.json()

    if data.get("success") != 1:
        raise RuntimeError(f"Echec création ordre d'achat pour {market_hash_name}: {data}\n")
    print(f"Steam buy order response: {data}")
    return data
