import sqlite3
import json
import hashlib
from datetime import datetime
import time
import requests
import logging
# Local imports
import Bot_App as bot



# partial open/close orders updated
FILTER = "FILLED"
TIME_DELTA=24

def main():
    print("Initializing Schwab Tracker...")
    #create schwab client
    client = bot.Schwab_client(
                bot.util.get_secret("SCHWAB_APP_KEY", "config/.env"),
                bot.util.get_secret("SCHWAB_APP_SECRET", "config/.env")
            )
    print("Schwab client initialized")
    
    #initialize database
    bot.SQL.initialize_db("orders.db")
    print("Database initialized")
    try:
        while True:
            # Get orders from Schwab API
            schwab_orders = client.get_account_positions(FILTER, TIME_DELTA)

            # store orders in database
            store_orders(schwab_orders)
            # print("Orders stored in database")

            # get unposted orders from database
            orders = get_unposted_orders()

            # Send unposted orders to Discord
            for order_id, raw_json in orders:
                order = json.loads(raw_json)
                if bot.webhook.post_to_discord(order, bot.util.get_secret("WEBHOOK_URL", "config/.env"), bot.util.get_secret("DISCORD_CHANNEL_ID", "config/.env"), bot.util.get_secret("SUFFIX", "config/.env")):
                    mark_as_posted(order_id)
                    print(f"Posted order {order_id} to Discord")
            # Sleep for 5 seconds before checking again
            time.sleep(5)

    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
        logging.error(f"Fatal connection error occurred: {e}. Exiting loop.")
    except KeyboardInterrupt:
        print("Exiting program.")


def generate_order_id(order):
    entered_time = order.get('enteredTime', '')
    # Safely extract instruction from first leg
    instruction = ''
    symbol = ''

    if 'orderLegCollection' in order and len(order['orderLegCollection']) > 0:
        first_leg = order['orderLegCollection'][0]
        instruction = first_leg.get('instruction', '')
        symbol = first_leg.get('instrument', {}).get('symbol', '')

    unique_string = f"{entered_time}_{instruction}_{symbol}"
    return hashlib.sha256(unique_string.encode()).hexdigest()


def store_orders(orders, db_path="orders.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
# make this more generic and lass hardcoded so it can be used for parsing open orders
    for order in orders:
        # Default values
        instruction = None
        position_effect = None
        symbol = None

        # Extract from orderLegCollection if available
        if 'orderLegCollection' in order and len(order['orderLegCollection']) > 0:
            first_leg = order['orderLegCollection'][0]
            instruction = first_leg.get('instruction', None)
            position_effect = first_leg.get('positionEffect', None)
            instrument = first_leg.get('instrument', {})
            symbol = instrument.get('symbol', None)
            description = instrument.get('description', None)

        order_id = generate_order_id(order)
        full_json = json.dumps(order)

        try:
            cursor.execute("""
                INSERT INTO schwab_orders (
                    id, entered_time, ticker, instruction, position_effect, 
                    order_status, quantity, tag, full_json, posted_to_discord, posted_at, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                order.get('enteredTime'),
                symbol,
                instruction,
                position_effect,
                order.get('status'),
                order.get('quantity'),
                order.get('tag'),
                full_json,
                0,  # posted_to_discord default
                None,  # posted_at default
                description
            ))
        except sqlite3.IntegrityError:
            pass  # Order already exists

    conn.commit()
    conn.close()



DISCORD_WEBHOOK_URL = "http://localhost:3000/trades/live_tracker"

def get_unposted_orders(db_path="orders.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, full_json FROM schwab_orders
        WHERE posted_to_discord = FALSE
    """)

    orders = cursor.fetchall()
    conn.close()

    return orders


def mark_as_posted(order_id, db_path="orders.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE schwab_orders
        SET posted_to_discord = TRUE, posted_at = ?
        WHERE id = ?
    """, (datetime.utcnow().isoformat(), order_id))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()