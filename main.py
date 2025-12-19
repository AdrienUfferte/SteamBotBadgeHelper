from steam_auth import login_with_cookies
from inventory import get_trading_cards
from badges import get_badges
from logic import compute_surplus_cards, compute_missing_cards
from market import (
    get_lowest_seller_and_qty,
    compute_sale_price_from_histogram,
    sell_item,
    get_buy_orders,
    get_lowest_price_buyer,
    create_buy_order,
    get_highest_buy_price,
)
from config import (
    TEST_MODE,
    BADGE_MAX_LEVEL,
    STEAM_ID,
    MIN_PRICE_EUR,
    SKIP_SELLING,
    MAX_CARD_PRICE,
    MAX_BOOSTER_PRICE
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

    print(f"Configuration:")
    print(f"- Max card price: {MAX_CARD_PRICE:.2f} €")
    print(f"- Max booster price: {MAX_BOOSTER_PRICE:.2f} €")
    print(f"- Test mode: {TEST_MODE}")
    print(f"- Skip selling: {SKIP_SELLING}")

    answer = input("Proceed with these settings? (y/n): ").strip().lower()
    if answer not in ("y", "yes"):
        print("Aborted.")
        return

    inventory = get_trading_cards(session, steam_id)
    badges = get_badges(steam_id)

    if TEST_MODE:
        print("=== MODE TEST ===")

    total_sales = 0

    if not SKIP_SELLING:
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
                        try:
                            sell_item(session, asset_id, final_price)
                            print(
                                f"SOLD {market_name} "
                                f"(asset {asset_id}) at {final_price:.2f} €"
                            )
                        except Exception as e:
                            print(
                                f"ERROR selling {market_name} "
                                f"(asset {asset_id}): {e}"
                            )

                    total_sales += 1

        if total_sales == 0:
            print("Aucune carte à vendre.")
        else:
            print(f"\nTotal cartes à vendre : {total_sales}")
    else:
        print("Selling skipped.")

    # --- Buying logic ---
    print("\n=== CHECKING MISSING CARDS FOR BADGES ===")

    buy_orders = get_buy_orders(session)
    print(f"Current buy orders: {len(buy_orders)}")

    skipped_items = []

    for appid, data in inventory.items():
        badge_level = badges.get(appid, 0)

        missing = compute_missing_cards(
            badge_level,
            BADGE_MAX_LEVEL,
            data["cards"]
        )

        if not missing:
            continue

        print(f"\n{data['game_name']} | Badge {badge_level}/{BADGE_MAX_LEVEL}")

        # Check if buying one card would complete the badge
        if badge_level >= BADGE_MAX_LEVEL - 1:
            # Buy individual cards
            for classid, miss_data in missing.items():
                market_name = miss_data["market_hash_name"]
                needed = miss_data["needed"]

                if market_name in buy_orders:
                    existing_price, existing_qty = buy_orders[market_name]
                    print(f"  {market_name}: Already have buy order at {existing_price:.2f} € (qty {existing_qty})")
                    continue

                lowest_seller_price, qty_at_lowest = get_lowest_seller_and_qty(
                    session,
                    market_name
                )

                suggested_buy_price = max(lowest_seller_price - 0.01, MIN_PRICE_EUR)

                if TEST_MODE:
                    print(f"[TEST] Create buy order for {market_name} x{needed} at {suggested_buy_price:.2f} €")
                else:
                    try:
                        create_buy_order(session, market_name, suggested_buy_price, quantity=needed)
                        print(f"Created buy order for {market_name} x{needed} at {suggested_buy_price:.2f} €")
                    except Exception as e:
                        print(f"Error creating buy order for {market_name}: {e}")
        else:
            # Check for booster pack buy order
            booster_names = [
                f"{appid}-{data['game_name']} Booster Pack",
                f"{appid}-Booster Pack {data['game_name']}",
                f"{data['game_name']} Booster Pack",
                f"Booster Pack {data['game_name']}",
            ]

            booster_found = False
            booster_name = None
            lowest_seller_price = None

            for bn in booster_names:
                try:
                    lsp, qty = get_lowest_seller_and_qty(session, bn)
                    booster_name = bn
                    lowest_seller_price = lsp
                    booster_found = True
                    break
                except Exception as e:
                    continue

            if not booster_found:
                print(f"  No booster pack found for {data['game_name']}, buying individual cards instead")
                # Fall back to individual cards
                for classid, miss_data in missing.items():
                    market_name = miss_data["market_hash_name"]
                    needed = miss_data["needed"]

                    if market_name in buy_orders:
                        existing_price, existing_qty = buy_orders[market_name]
                        print(f"  {market_name}: Already have buy order at {existing_price:.2f} € (qty {existing_qty})")
                        continue

                    try:
                        lowest_seller_price, qty_at_lowest = get_lowest_seller_and_qty(
                            session,
                            market_name
                        )

                        suggested_buy_price = max(lowest_seller_price - 0.01, MIN_PRICE_EUR)

                        if suggested_buy_price > MAX_CARD_PRICE:
                            skipped_items.append(f"Card {market_name} at {suggested_buy_price:.2f} € > {MAX_CARD_PRICE:.2f} €")
                            continue

                        if TEST_MODE:
                            print(f"[TEST] Create buy order for {market_name} x{needed} at {suggested_buy_price:.2f} €")
                        else:
                            create_buy_order(session, market_name, suggested_buy_price, quantity=needed)
                            print(f"Created buy order for {market_name} x{needed} at {suggested_buy_price:.2f} €")
                    except Exception as e:
                        print(f"Error for {market_name}: {e}")
                continue

            # Check if already have buy order for the booster
            if booster_name in buy_orders:
                print(f"  Already have buy order for {booster_name}")
                continue  # Skip this badge

            # Create buy order for booster pack
            try:
                suggested_buy_price = get_highest_buy_price(session, booster_name)

                if suggested_buy_price > MAX_BOOSTER_PRICE:
                    skipped_items.append(f"Booster {booster_name} at {suggested_buy_price:.2f} € > {MAX_BOOSTER_PRICE:.2f} €")
                    continue

                if TEST_MODE:
                    print(f"[TEST] Create buy order for {booster_name} at {suggested_buy_price:.2f} €")
                else:
                    create_buy_order(session, booster_name, suggested_buy_price)
                    print(f"Created buy order for {booster_name} at {suggested_buy_price:.2f} €")
            except Exception as e:
                print(f"Error creating buy order for {booster_name}: {e}")
                # If fails, perhaps fall back, but for now skip


    if skipped_items:
        print("\nSkipped items due to price limits:")
        for item in skipped_items:
            print(f"- {item}")


if __name__ == "__main__":
    main()
