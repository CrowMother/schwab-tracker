import logging
import requests
import sqlite3
import time

# Local imports
import Bot_App as bot

# Constants
BROKER = bot.util.get_secret("BROKER", "config/.env")
FILTER = "FILLED"

WEBHOOK_URL = bot.util.get_secret("WEBHOOK_URL", "config/.env")
WEBHOOK_EXTENSION = bot.util.get_secret("WEBHOOK_EXTENSION", "config/.env")
DISCORD_CHANNEL_ID = bot.util.get_secret("DISCORD_CHANNEL_ID", "config/.env")

DATABASE_PATH = bot.util.get_secret("DATABASE_PATH", "config/.env")

LOOP_FREQUENCY = int(bot.util.get_secret("LOOP_FREQUENCY", "config/.env"))
TIME_DELTA = int(bot.util.get_secret("TIME_DELTA", "config/.env"))

MESSAGE_TEMPLATE_OPENING = bot.util.get_secret("MESSAGE_TEMPLATE_OPENING", "config/.env")
MESSAGE_TEMPLATE_CLOSING = bot.util.get_secret("MESSAGE_TEMPLATE_CLOSING", "config/.env")

DROP_TABLES = bool(bot.util.get_secret("DROP_TABLES", "config/.env"))


def format_webhook(order):
    """
    Formats the order data for sending to the webhook dynamically based on an environment variable template.

    Args:
        order (dict): The order data to be formatted.

    Returns:
        message (dict): Discord channel ID and message content.
    """
    try:
        print(order)

        # Calculate percentage gain if order has an open price
        order["percentage_gain"] = (
            f"{((order['price'] - order['open_price']) / order['open_price'] * 100):.2f}%" 
            if "open_price" in order else "N/A"
        )

        # Determine which message template to use
        if "open_price" in order:
            message_content = MESSAGE_TEMPLATE_CLOSING.format(**order)
        else:
            message_content = MESSAGE_TEMPLATE_OPENING.format(**order)

        message = {
            "channel": DISCORD_CHANNEL_ID,
            "content": message_content
        }

        return message

    except KeyError as e:
        logging.error(f"Missing key in order data: {e}")
    except Exception as e:
        logging.error(f"Error formatting webhook message: {str(e)}")

def send_to_webhook(order):
    """
    Sends the given order to the specified webhook URL.
    Logs success or failure of the request.
    """
    try:
        order = format_webhook(order)
        print(f"Sending order to {WEBHOOK_URL}:\n {order}")
        response = requests.post(WEBHOOK_URL, json=order)
        if response.status_code == 200:
            logging.info("Successfully sent order to webhook.")
        else:
            logging.error(f"Failed to send order to webhook. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending data to webhook: {str(e)}")


def initialize_database(sql):
    """
    Initializes the database by creating necessary tables and dropping existing ones (for testing).
    """
    # Drop existing tables (for testing purposes)
    if DROP_TABLES:
        sql.execute_query("DROP TABLE IF EXISTS orders")
        sql.execute_query("DROP TABLE IF EXISTS positions")
        sql.execute_query("DROP TABLE IF EXISTS open_positions")

    # Create `orders` table
    sql.execute_query("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY,
        symbol TEXT,
        quantity INTEGER,
        description TEXT,
        putCall TEXT,
        date TEXT,
        strike REAL,
        price REAL,
        instruction TEXT,
        complexOrderStrategy TEXT,
        orderStrategyType TEXT,
        legId INTEGER,
        instrumentId INTEGER,
        executionTime TEXT
    )""")

    # Create `open_positions` table
    sql.execute_query("""
    CREATE TABLE IF NOT EXISTS open_positions (
        executionTime TEXT PRIMARY KEY,
        instrumentId TEXT,
        quantity INTEGER,
        avg_price REAL,
        symbol TEXT
    );
    """)
    sql.commit()


def save_orders_to_db(sql, orders):
    """
    Saves the given list of orders to the `orders` table in the database.
    """
    if not orders:
        logging.warning("No orders to save to the database.")
        return

    for order in orders:
        logging.debug(f"Saving order to database: {order}")  # Debugging log
        query = """
        INSERT INTO orders (
            order_id, symbol, quantity, description, putCall, date, strike, price, instruction,
            complexOrderStrategy, orderStrategyType, legId, instrumentId, executionTime
        ) VALUES (
            NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
        params = (
            order['symbol'], order['quantity'], order['description'], order['putCall'],
            order['date'], order['strike'], order['price'], order['instruction'],
            order['complexOrderStrategy'], order['orderStrategyType'],
            order['legId'], order['instrumentId'], order['executionTime']
        )
        try:
            sql.execute_query(query, params)
        except Exception as e:
            logging.error(f"Error saving order to database: {e}")

    sql.commit()  # Commit changes to ensure data is saved
    logging.info(f"Successfully saved {len(orders)} orders to the database.")


def populate_open_positions(sql, orders):
    """
    Populates the `open_positions` table with BUY_TO_OPEN and SELL_TO_OPEN orders.
    """
    for order in orders:
        if order['instruction'] in ["BUY_TO_OPEN", "SELL_TO_OPEN"]:
            sql.execute_query(
                "INSERT INTO open_positions VALUES (?, ?, ?, ?, ?)",
                (order['executionTime'], order['instrumentId'], order['quantity'], order['price'], order['symbol'])
            )
    sql.commit()


def process_closing_orders(sql, orders):
    """
    Processes closing orders, updating `open_positions` and tracking closed orders.
    Returns a list of closed orders.
    """
    closed_orders = []

    for order in orders:
        if order['instruction'] in ["BUY_TO_OPEN", "SELL_TO_OPEN"]:
            continue

        # Find matching open positions
        matches = sql.get_data(
            query="SELECT * FROM open_positions WHERE instrumentId = ? AND quantity > 0 ORDER BY executionTime ASC",
            params=(order['instrumentId'],)
        )

        if matches:
            closing_quantity = order['quantity']

            # Iterate through matching open positions
            for match in matches:
                execution_time = match[0]
                open_id = match[1]
                open_quantity = match[2]
                open_avg_price = match[3]

                if closing_quantity <= 0:
                    break

                processed_quantity = min(open_quantity, closing_quantity)
                closing_quantity -= processed_quantity
                partial_close = open_quantity > processed_quantity

                # Add to closed orders
                closed_orders.append({
                    "symbol": order["symbol"],
                    "quantity": processed_quantity,
                    "description": order["description"],
                    "putCall": order["putCall"],
                    "date": order["date"],
                    "strike": order["strike"],
                    "price": order["price"],
                    "instruction": order["instruction"],
                    "complexOrderStrategy": order["complexOrderStrategy"],
                    "orderStrategyType": order["orderStrategyType"],
                    "legId": order["legId"],
                    "instrumentId": order["instrumentId"],
                    "executionTime": execution_time,
                    "open_quantity": open_quantity,
                    "open_price": open_avg_price,
                    "partial_close": partial_close
                })

                # Update or delete open positions
                if partial_close:
                    sql.execute_query(
                        "UPDATE open_positions SET quantity = quantity - ? WHERE instrumentId = ? AND executionTime = ?",
                        params=(processed_quantity, open_id, execution_time)
                    )
                else:
                    sql.execute_query(
                        "DELETE FROM open_positions WHERE instrumentId = ? AND executionTime = ?",
                        params=(open_id, execution_time)
                    )

            if closing_quantity > 0:
                logging.warning(f"Remaining closing quantity of {closing_quantity} could not be fully matched.")
        else:
            logging.info(f"No matching open positions found for instrumentId: {order['instrumentId']}")

    sql.commit()
    return closed_orders


def loop(client, sql, interval=LOOP_FREQUENCY):
    """
    Continuously runs loop_work at the specified interval.

    Args:
        client: schwab client to use
        sql: SQL database to use
        interval: time in seconds to wait between loop iterations (default: 5)

    Note: This function will run indefinitely until the program is terminated.
    """
    while True:
        error = loop_work(client, sql)
        if error:
            break
        time.sleep(interval)


def loop_work(client, sql):
    """
    Retrieves account positions from the client, processes them, and updates the database.

    Args:
        client: The Schwab client to retrieve account positions from.
        sql: The SQL database instance to update with order data.

    Workflow:
        1. Retrieves account positions with applied filter.
        2. Sorts and structures the data into orders.
        3. Saves orders to the database and populates open positions.
        4. Processes closing orders and logs the results of closed orders.
        5. Sends new and closed orders to the webhook.
    """
    try:
        # Fetch orders from Schwab
        response = client.get_account_positions(FILTER, TIME_DELTA)
        orders = [bot.sort_data_schwab(position) for position in response]

        logging.debug(f"Orders fetched: {orders}")

        # Fetch existing execution times from the database
        existing_order_rows = sql.get_data("SELECT executionTime FROM orders")
        existing_order_executionTime = [row[0] for row in existing_order_rows]  # Extract execution times
        logging.debug(f"Existing order execution times: {existing_order_executionTime}")

        # Filter new orders
        new_orders = [order for order in orders if order.get('executionTime') not in existing_order_executionTime]
        logging.debug(f"New orders: {new_orders}")

        if new_orders:
            # Save new orders to the database
            save_orders_to_db(sql, new_orders)

            # Populate open positions
            populate_open_positions(sql, new_orders)

            # Process closing orders
            closed_orders = process_closing_orders(sql, new_orders)
            logging.info(f"Closed Orders: {closed_orders}")

            # Send orders to webhook
            for order in new_orders:
                # Check if the order is a closing order
                if order['instruction'] in ["SELL_TO_CLOSE", "BUY_TO_CLOSE"]:
                    # Match the closing order with its corresponding closed position
                    matching_closing_orders = [
                        closed_order for closed_order in closed_orders
                        if closed_order['instrumentId'] == order['instrumentId']
                    ]
                    # Send the matched closing data to the webhook
                    for closed_order in matching_closing_orders:
                        send_to_webhook(closed_order)
                else:
                    # Send new order directly to the webhook
                    send_to_webhook(order)

    except Exception as e:
        logging.error(f"Error in loop_work: {e}")
        return e


def main():
    # Initialize logging
    logging.basicConfig(level=logging.INFO)
    

    # Initialize database
    sql = bot.SQLDatabase(DATABASE_PATH)
    sql.connect()
    initialize_database(sql)

    # Initialize Schwab client
    client = bot.Schwab_client(
        bot.util.get_secret("SCHWAB_APP_KEY", "config/.env"),
        bot.util.get_secret("SCHWAB_APP_SECRET", "config/.env")
    )

    # Start the main loop
    loop(client, sql)
    


if __name__ == "__main__":
    main()


