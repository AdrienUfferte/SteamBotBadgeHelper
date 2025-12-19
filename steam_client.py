from steampy.client import SteamClient
from config import *

def connect():
    client = SteamClient(STEAM_API_KEY)
    client.login(
        STEAM_USERNAME,
        STEAM_PASSWORD
    )
    return client
