def compute_surplus_cards(badge_level, badge_max_level, cards_by_type):
    surplus = {}

    if badge_level >= badge_max_level:
        for cid, data in cards_by_type.items():
            surplus[cid] = data["asset_ids"].copy()
        return surplus

    remaining = badge_max_level - badge_level

    for cid, data in cards_by_type.items():
        excess = data["quantity"] - remaining
        if excess > 0:
            surplus[cid] = data["asset_ids"][:excess]

    return surplus
