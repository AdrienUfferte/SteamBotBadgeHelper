from steam_client import connect
from logic import compute_surplus_cards
from market import sell_card
from config import TEST_MODE

def main():
    client = connect()

    print(
        "=== MODE TEST ==="
        if TEST_MODE else
        "=== MODE LIVE ==="
    )

    # ------------------------------------------------------------------
    # IMPORTANT :
    # Cette partie dépend de la façon dont vous récupérez les badges
    # Elle est volontairement simplifiée ici
    # ------------------------------------------------------------------

    badges = get_badges_with_cards(client)

    for badge in badges:
        print(
            f"\nBadge: {badge['name']} "
            f"({badge['level']} / {badge['max_level']})"
        )

        surplus = compute_surplus_cards(
            badge_level=badge["level"],
            badge_max_level=badge["max_level"],
            cards_by_type=badge["cards"]
        )

        if not surplus:
            print("  Aucun surplus à vendre")
            continue

        for card_type, asset_ids in surplus.items():
            for asset_id in asset_ids:
                sell_card(
                    client,
                    asset_id,
                    badge["cards"][card_type]["market_hash_name"]
                )


# ----------------------------------------------------------------------
# EXEMPLE DE STRUCTURE ATTENDUE
# (à adapter selon votre récupération réelle)
# ----------------------------------------------------------------------
def get_badges_with_cards(client):
    """
    Retour attendu :
    [
        {
            "name": "Game name",
            "level": 3,
            "max_level": 5,
            "cards": {
                "card_A": {
                    "quantity": 4,
                    "asset_ids": ["123", "124", "125", "126"],
                    "market_hash_name": "Trading Card A"
                },
                ...
            }
        }
    ]
    """
    raise NotImplementedError(
        "À implémenter selon votre méthode de récupération des badges"
    )


if __name__ == "__main__":
    main()
