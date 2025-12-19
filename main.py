from steam_auth import login_with_cookies
from inventory import get_trading_cards
from badges import get_badges
from logic import compute_surplus_cards
from market import (
    get_lowest_seller_and_qty,
    compute_sale_price_from_histogram,
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

        # 🔇 Aucun surplus → on ignore le jeu
        if not surplus:
            continue

        print(f"\n{data['game_name']} | Badge {badge_level}/{BADGE_MAX_LEVEL}")

        for classid, asset_ids in surplus.items():
            card = data["cards"][classid]
            market_name = card["market_hash_name"]

            # 1️⃣ Lecture du carnet d’ordres vendeur (source de vérité)
            lowest_seller_price, qty_at_lowest = get_lowest_seller_and_qty(
                session,
                market_name
            )

            # print(
            #     f"[DEBUG] {market_name} "
            #     f"lowest_seller={lowest_seller_price:.2f} € "
            #     f"qty_at_lowest={qty_at_lowest}"
            # )

            # 2️⃣ Application de la règle métier
            final_price = compute_sale_price_from_histogram(
                lowest_seller_price,
                qty_at_lowest
            )

            # print(
            #     f"[DEBUG] final_price decided: {final_price:.2f} €"
            # )

            # 3️⃣ Confirmation utilisateur si prix >= 0,10 €
            if final_price >= 0.10:
                if not confirm_price(final_price, market_name):
                    print("Vente annulée par l'utilisateur.")
                    continue

            # 4️⃣ Log de vente (TEST ou réel)
            for asset_id in asset_ids:
                if TEST_MODE:
                    print(
                        f"[TEST] SELL {market_name} "
                        f"(asset {asset_id}) at {final_price:.2f} €"
                    )
                else:
                    # ⚠️ Vente réelle à implémenter plus tard
                    print(
                        f"SELL {market_name} "
                        f"(asset {asset_id}) at {final_price:.2f} €"
                    )

                total_sales += 1

    if total_sales == 0:
        print("Aucune carte à vendre.")
    else:
        print(f"\nTotal cartes à vendre : {total_sales}")


if __name__ == "__main__":
    main()
