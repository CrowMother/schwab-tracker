# File: main.py
import json
from datetime import datetime
import time
import requests
import logging
# Local imports
import Bot_App as bot
from Bot_App import util, webhook, data



# partial open/close orders updated
FILTER = "FILLED"
TIME_DELTA=int(util.get_secret("TIME_DELTA", "config/.env", 24))
#initialize logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    print("Initializing Schwab Tracker...")
    #create schwab client
    client = bot.Schwab_client(
                bot.util.get_secret("SCHWAB_APP_KEY", "config/.env"),
                bot.util.get_secret("SCHWAB_APP_SECRET", "config/.env")
            )
    print("Schwab client initialized")
    
    #initialize database
    drop_tables = util.str_to_bool(util.get_secret("DROP_TABLES", "config/.env", False))
    bot.SQL.initialize_db("orders.db", drop_tables)
    print("Database initialized")
    try:
        while True:
            # Get orders from Schwab API
            schwab_orders = client.get_account_positions(FILTER, TIME_DELTA)

            # store orders in database
            bot.data.store_orders(schwab_orders)
            # print("Orders stored in database")

            # get unposted orders from database
            orders = bot.data.get_unposted_orders()

            # Send unposted orders to Discord
            for order_id, raw_json in orders:
                order = json.loads(raw_json)
                if bot.webhook.post_to_discord(order, bot.util.get_secret("WEBHOOK_URL", "config/.env"), bot.util.get_secret("DISCORD_CHANNEL_ID", "config/.env"), bot.util.get_secret("SUFFIX", "config/.env")):
                    bot.data.mark_as_posted(order_id)
                    print(f"Posted order {order_id} to Discord")
            # Sleep for 5 seconds before checking again
            time.sleep(5)

    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
        logging.error(f"Fatal connection error occurred: {e}. Exiting loop.")
    except KeyboardInterrupt:
        print("Exiting program.")


if __name__ == "__main__":
    main()