def compute_surplus_cards(badge_level, badge_max_level, cards_by_type):
    """
    cards_by_type = {
        "card_type_id": {
            "quantity": int,
            "asset_ids": [asset_id_1, asset_id_2, ...]
        }
    }

    Retourne :
    {
        "card_type_id": [asset_id_to_sell_1, asset_id_to_sell_2, ...]
    }
    """

    surplus = {}

    # Badge déjà au niveau max => tout vendre
    if badge_level >= badge_max_level:
        for card_type, data in cards_by_type.items():
            if data["quantity"] > 0:
                surplus[card_type] = data["asset_ids"].copy()
        return surplus

    remaining_levels = badge_max_level - badge_level
    keep_per_type = remaining_levels

    for card_type, data in cards_by_type.items():
        qty = data["quantity"]
        if qty > keep_per_type:
            to_sell_count = qty - keep_per_type
            surplus[card_type] = data["asset_ids"][:to_sell_count]

    return surplus
