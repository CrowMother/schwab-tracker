# # # app.py  (run: streamlit run app.py)
# import schwab.auth
#
import Bot_App
#
# # --- config ---
# APP_KEY    = Bot_App.get_secret("SCHWAB_APP_KEY", "./config/.env", None)
# APP_SECRET = Bot_App.get_secret("SCHWAB_APP_SECRET", "./config/.env", None)
# PUBLIC_REDIRECT   = Bot_App.get_secret("PUBLIC_REDIRECT", "./config/.env", "https://127.0.0.1")
# CALLBACK    = "https://127.0.0.1:8765/callback"
# from schwabdev import Client
#
#
# # get_tokens.py
# import os
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager
# from schwab.auth import easy_client  # <- from schwab-py
#
#  # must EXACTLY match a URL in the portal
#
# def make_driver():
#     opts = Options()
#     # opts.add_argument("--headless=new")   # uncomment if you want headless
#     opts.add_argument("--disable-extensions")
#     return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
#
# client = schwab.auth.client_from_login_flow(
#     api_key= APP_KEY,
#     app_secret= APP_SECRET,
#     callback_url= CALLBACK,
#     token_path="tokens.json",
#     interactive=False,
#     callback_timeout=300
# )
#
# print("OK — tokens.json written and automatic refresh is configured.")
#
#
#
#
# print("OK — tokens.json written and refresh handled automatically.")
#

# pip install schwab-py selenium webdriver-manager

import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from schwab.auth import easy_client

APP_KEY    = Bot_App.get_secret("SCHWAB_APP_KEY", "./config/.env", None)
APP_SECRET = Bot_App.get_secret("SCHWAB_APP_SECRET", "./config/.env", None)
PUBLIC_REDIRECT   = Bot_App.get_secret("PUBLIC_REDIRECT", "./config/.env", "https://127.0.0.1")

# Must be whitelisted in the Schwab portal (you already have 127.0.0.1 allowed)
CALLBACK = "https://127.0.0.1/"

def make_driver():
    opts = Options()
    # opts.add_argument("--headless=new")  # optional
    opts.add_argument("--disable-extensions")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

client = easy_client(
    api_key=APP_KEY,
    app_secret=APP_SECRET,
    callback_url=CALLBACK,
    token_path="tokens.json",
    make_driver=make_driver,   # <-- forces the Selenium (no local server) path
)
print("tokens.json written.")

