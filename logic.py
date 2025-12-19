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


def compute_missing_cards(badge_level, badge_max_level, cards_by_type):
    missing = {}

    if badge_level >= badge_max_level:
        return missing

    for cid, data in cards_by_type.items():
        needed = badge_max_level - data["quantity"]
        if needed > 0:
            missing[cid] = {
                "market_hash_name": data["market_hash_name"],
                "needed": needed
            }

    return missing
