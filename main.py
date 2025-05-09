# File: main.py
import json
from datetime import datetime
import time
import requests
import logging
from Bot_App.core.schwab_client import SchwabClient
from Bot_App.core.database import store_orders, get_unposted_orders, mark_as_posted
from Bot_App.services.discord import send_discord_alert
from Bot_App.config.secrets import get_secret, str_to_bool
import json, time, logging



# partial open/close orders updated
FILTER = "FILLED"
TIME_DELTA=int(get_secret("TIME_DELTA", "config/.env", 24))
#initialize logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    print("Initializing Schwab Tracker...")

    client = SchwabClient(
        get_secret("SCHWAB_APP_KEY", "config/.env"),
        get_secret("SCHWAB_APP_SECRET", "config/.env")
    )
    print("Schwab client initialized")

    drop_tables = str_to_bool(get_secret("DROP_TABLES", "config/.env", False))
    from Bot_App.core import database
    database.initialize_db("orders.db", drop_tables)
    print("Database initialized")

    try:
        while True:
            # Fetch orders from Schwab
            schwab_orders = client.get_account_positions(
                status_filter="FILLED",
                hours=int(get_secret("TIME_DELTA", "config/.env", 24))
            )

            # Store and process orders
            store_orders(schwab_orders)
            orders = get_unposted_orders()

            for order_id, raw_json in orders:
                order = json.loads(raw_json)
                if send_discord_alert(
                    order,
                    get_secret("WEBHOOK_URL", "config/.env"),
                    get_secret("DISCORD_CHANNEL_ID", "config/.env"),
                    get_secret("SUFFIX", "config/.env")
                ):
                    mark_as_posted(order_id)
                    print(f"Posted order {order_id} to Discord")

            time.sleep(5)

    except KeyboardInterrupt:
        print("Exiting program.")
    except Exception as e:
        logging.error(f"Fatal error: {e}")



if __name__ == "__main__":
    main()