import requests
from config import STEAM_API_KEY

def get_badges(steam_id):
    url = "https://api.steampowered.com/IPlayerService/GetBadges/v1/"
    params = {"key": STEAM_API_KEY, "steamid": steam_id}

    r = requests.get(url, params=params)
    r.raise_for_status()

    return {
        badge["appid"]: badge["level"]
        for badge in r.json()["response"]["badges"]
        if "appid" in badge
    }
