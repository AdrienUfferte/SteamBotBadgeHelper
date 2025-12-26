import logging

from badges import (
    get_app_name,
    get_badge_name,
    get_badges_list,
    get_owned_games_map,
    get_profile_badge_names,
)
from config import STEAM_ID
from steam_auth import login_with_cookies

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    logging.info("Starting badge export")
    session = login_with_cookies()

    badges = get_badges_list(STEAM_ID)
    app_names = get_owned_games_map(STEAM_ID)
    profile_badge_names = get_profile_badge_names(session=session, steam_id=STEAM_ID)

    with open("badges.txt", "w", encoding="utf-8") as f:
        for badge in badges:
            level = badge.get("level", 0)
            appid = badge.get("appid")
            badgeid = badge.get("badgeid")
            if appid is not None:
                title = app_names.get(appid)
                if not title:
                    title = get_app_name(appid) or f"App {appid}"
                badge_id = appid
            else:
                title = profile_badge_names.get(badgeid)
                if not title:
                    title = get_badge_name(badgeid, session=session, steam_id=STEAM_ID) or f"Badge {badgeid}"
                badge_id = badgeid

            title = title.replace('"', '\\"')

            f.write(f"\"{title}\"\n")
            f.write(f"    Level = {level}\n")
            f.write(f"    ID = {badge_id}\n\n")

    logging.info(f"Wrote {len(badges)} badges to badges.txt")


if __name__ == "__main__":
    main()
