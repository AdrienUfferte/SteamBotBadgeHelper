from steam_auth import login_with_cookies
from inventory import get_trading_cards
from badges import get_badges
from logic import compute_surplus_cards
from market import get_lowest_price
from config import TEST_MODE, BADGE_MAX_LEVEL, STEAM_ID

def main():
    session = login_with_cookies()
    steam_id = STEAM_ID

    inventory = get_trading_cards(session, steam_id)
    badges = get_badges(steam_id)

    print(f"{len(inventory)} jeux avec des cartes trouvés")

    print("=== MODE TEST ===" if TEST_MODE else "=== MODE LIVE ===")

    for appid, data in inventory.items():
        level = badges.get(appid, 0)

        print(
            f"\n{data['game_name']} | "
            f"Badge {level}/{BADGE_MAX_LEVEL}"
        )

        for classid, card in data["cards"].items():
            print(
                f"  - {card['market_hash_name']}: "
                f"{card['quantity']} exemplaire(s)"
            )

        surplus = compute_surplus_cards(
            level, BADGE_MAX_LEVEL, data["cards"]
        )

        if not surplus:
            print("  Aucun surplus")
            continue

        for classid, asset_ids in surplus.items():
            card = data["cards"][classid]
            price = get_lowest_price(session, card["market_hash_name"])

            for asset_id in asset_ids:
                print(
                    f"[TEST] SELL {card['market_hash_name']} "
                    f"(asset {asset_id}) at {price:.2f} €"
                )

if __name__ == "__main__":
    main()
