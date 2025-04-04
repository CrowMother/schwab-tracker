import sqlite3
import json
import hashlib
import requests
from datetime import datetime
import time
# Local imports
import Bot_App as bot

FILTER = "FILLED"
TIME_DELTA=168

def main():
    client = bot.Schwab_client(
                bot.util.get_secret("SCHWAB_APP_KEY", "config/.env"),
                bot.util.get_secret("SCHWAB_APP_SECRET", "config/.env")
            )
    while True:
        #initialize database
        bot.SQL.initialize_db("orders.db")
        print("Database initialized")
        #create schwab client
        
        schwab_orders = client.get_account_positions(FILTER, TIME_DELTA)
        store_orders(schwab_orders)
        print("Orders stored in database")

        orders = get_unposted_orders()
        for order_id, raw_json in orders:
            order = json.loads(raw_json)
            if post_to_discord(order):
                mark_as_posted(order_id)
        print("Orders posted to Discord")
        # Sleep for 5 seconds before checking again
        time.sleep(5)


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

        order_id = generate_order_id(order)
        full_json = json.dumps(order)

        try:
            cursor.execute("""
                INSERT INTO schwab_orders (
                    id, entered_time, ticker, instruction, position_effect, 
                    order_status, quantity, tag, full_json, posted_to_discord, posted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                None  # posted_at default
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

def get_open_close_symbol(position_effect):
    if position_effect == "OPENING":
        return f"{position_effect} 🟢"
    elif position_effect == "CLOSING":
        return f"{position_effect} 🔴"
    else:
        return f"{position_effect} 🟡"

def format_discord_message(order):
    """
    Format a Schwab order dictionary into a string suitable for posting to Discord.

    :param order: A dictionary of a Schwab order
    :return: A string representation of the order
    """
    legs = order.get("orderLegCollection", [])
    price = order.get("price", "?")
    position_effects = []
    leg_lines = []

    for leg in legs:
        instruction = leg.get("instruction", "UNKNOWN")
        position_effect = leg.get("positionEffect", "")
        position_effect = get_open_close_symbol(position_effect)
        instrument = leg.get("instrument", {})
        symbol = instrument.get("symbol", "???").split(" ")[0]
        description = instrument.get("description", "")
        # Extract important parts of the option description
        # date is the first part of the description
        # strike is the second part
        # put or call is the fourth part
        date = bot.data.parse_option_description(description, 2)
        strike = bot.data.parse_option_description(description, 3)
        put_call = bot.data.parse_option_description(description, 4)

        # Build a string for each leg with the instruction and symbol
        leg_lines.append(f"## {symbol}")
        # Add the symbol and strike price
        leg_lines.append(f"> **{date} ${strike} {put_call}**")
        position_effects.append(position_effect)
        
    effect_summary = ', '.join(set(position_effects)) or "UNKNOWN"
    body = "\n".join(leg_lines)

    gain_line = ""
    if any(pe == "CLOSING 🔴" for pe in position_effects):
        opening_price = find_opening_price(order)
        if opening_price and price:
            pct_change = ((price - opening_price) / opening_price) * 100
            emoji = ":chart_with_upwards_trend:" if pct_change >= 0 else ":chart_with_downwards_trend: "
            gain_line = f"\n{emoji} **{pct_change:+.2f}%** vs open"

    return f"{body}\n@ ${price} *{effect_summary}*{gain_line}"
    # Collapse the position effects into a single string
    effect_summary = ', '.join(set(position_effects)) or "UNKNOWN"
    # Join all the lines of the leg strings into a single string
    body = "\n".join(leg_lines)

    return f"{body}\n@ ${price} *{effect_summary}*"

def extract_execution_price(order):
    activities = order.get("orderActivityCollection", [])
    if activities:
        legs = activities[0].get("executionLegs", [])
        if legs:
            return float(legs[0].get("price", 0))
    return None

def find_opening_price(order, db_path="orders.db"):
    leg = order.get("orderLegCollection", [{}])[0]
    instrument = leg.get("instrument", {})
    symbol = instrument.get("symbol", None)
    entry_time = order.get("enteredTime", None)

    if not symbol or not entry_time:
        return None

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT full_json FROM schwab_orders
        WHERE ticker = ? AND position_effect = 'OPENING'
        AND entered_time < ?
        ORDER BY entered_time DESC
        LIMIT 1
    """, (symbol, entry_time))

    row = cursor.fetchone()
    conn.close()

    if row:
        opening_order = json.loads(row[0])
        return extract_execution_price(opening_order)
    return None

def post_to_discord(order_json):
    content = format_discord_message(order_json)
    payload = {
        "channel": "1337475225650200576",
        "content": content}

    response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    return response.status_code == 204 or response.status_code == 200

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