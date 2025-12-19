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

    if TEST_MODE:
        print("=== MODE TEST ===")

    total_sales = 0

    for appid, data in inventory.items():
        badge_level = badges.get(appid, 0)

        surplus = compute_surplus_cards(
            badge_level,
            BADGE_MAX_LEVEL,
            data["cards"]
        )

        # 🔇 Rien à vendre → on ignore complètement le jeu
        if not surplus:
            continue

        # À partir d'ici : il y a AU MOINS une carte à vendre
        print(f"\n{data['game_name']} | Badge {badge_level}/{BADGE_MAX_LEVEL}")

        for classid, asset_ids in surplus.items():
            card = data["cards"][classid]

            price = get_lowest_price(
                session,
                card["market_hash_name"]
            )

            for asset_id in asset_ids:
                if TEST_MODE:
                    print(
                        f"[TEST] SELL {card['market_hash_name']} "
                        f"(asset {asset_id}) at {price:.2f} €"
                    )
                else:
                    print(
                        f"SELL {card['market_hash_name']} "
                        f"(asset {asset_id}) at {price:.2f} €"
                    )

                total_sales += 1

    if total_sales == 0:
        print("Aucune carte à vendre.")
    else:
        print(f"\nTotal cartes à vendre : {total_sales}")


if __name__ == "__main__":
    main()
