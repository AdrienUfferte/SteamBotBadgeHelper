from steam_auth import login_with_cookies
from inventory import get_trading_cards
from badges import get_badges
from logic import compute_surplus_cards
from market import (
    get_lowest_price,
    has_three_or_more_at_lowest_price,
    compute_sale_price
)
from config import (
    TEST_MODE,
    BADGE_MAX_LEVEL,
    STEAM_ID
)


def confirm_price(price, card_name):
    """
    Demande confirmation utilisateur pour les ventes >= 0,10 €
    """
    while True:
        answer = input(
            f"Confirmer la vente de '{card_name}' à {price:.2f} € ? (y/n): "
        ).strip().lower()

        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


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

        # 🔇 Rien à vendre → on ignore complètement ce jeu
        if not surplus:
            continue

        print(f"\n{data['game_name']} | Badge {badge_level}/{BADGE_MAX_LEVEL}")

        for classid, asset_ids in surplus.items():
            card = data["cards"][classid]

            # 1️⃣ Prix le plus bas actuel
            lowest_price = get_lowest_price(
                session,
                card["market_hash_name"]
            )

            # 2️⃣ Récupération des offres en vente au prix le plus bas
            has_three_or_more = has_three_or_more_at_lowest_price(
                session,
                card["market_hash_name"],
                lowest_price
            )

            # 3️⃣ Calcul du prix final selon la règle
            final_price = compute_sale_price(
                lowest_price,
                has_three_or_more
)

            # 4️⃣ Confirmation utilisateur si prix >= 0,10 €
            if final_price >= 0.10:
                if not confirm_price(final_price, card["market_hash_name"]):
                    print("Vente annulée par l'utilisateur.")
                    continue

            # 5️⃣ Log de vente (TEST ou réel)
            for asset_id in asset_ids:
                if TEST_MODE:
                    print(
                        f"[TEST] SELL {card['market_hash_name']} "
                        f"(asset {asset_id}) at {final_price:.2f} €"
                    )
                else:
                    # ⚠️ Vente réelle à implémenter ici plus tard
                    print(
                        f"SELL {card['market_hash_name']} "
                        f"(asset {asset_id}) at {final_price:.2f} €"
                    )

                total_sales += 1

    if total_sales == 0:
        print("Aucune carte à vendre.")
    else:
        print(f"\nTotal cartes à vendre : {total_sales}")


if __name__ == "__main__":
    main()
