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

SEND_TO_URL = bool(bot.util.get_secret("SEND_TO_URL", "config/.env"))

OUTPUT_PATH = bot.util.get_secret("OUTPUT_PATH", "config/.env")

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
            logging.error("Error occurred in loop_work, exiting loop")
            break
        logging.info("Loop iteration completed, sleeping for {} seconds".format(interval))
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

        logging.debug(f"Orders fetched: {len(orders)}")

        # Fetch existing execution times from the database
        existing_order_rows = sql.get_data("SELECT executionTime FROM orders")
        existing_order_executionTime = [row[0] for row in existing_order_rows]  # Extract execution times

        # Filter new orders
        new_orders = [order for order in orders if order.get('executionTime') not in existing_order_executionTime]
        logging.debug(f"New orders: {len(new_orders)}")

        if not new_orders:
            return None
        
        # Save new orders to the database
        bot.schwab.save_orders_to_db(sql, new_orders)

        # Populate open positions
        bot.schwab.populate_open_positions(sql, new_orders)

        # Process closing orders
        closed_orders = bot.schwab.process_closing_orders(sql, new_orders)
        logging.info(f"Closed Orders: {len(closed_orders)}")

        #debugging option to send orders to webhook or prevent sending
        if OUTPUT_PATH == "DISCORD":
            send_to_discord_webhook(MESSAGE_TEMPLATE_OPENING, new_orders, closed_orders)
            
        elif OUTPUT_PATH == "GSHEET":
            send_to_gsheet(new_orders, closed_orders)

    except Exception as e:
        logging.error(f"Error in loop_work: {e}")
        return e

def send_to_gsheet(orders, closed_orders):

    #connect to google sheets
    #look into the following lines of code -------------------------------------------
    gsheet_client = bot.gsheet.connect_gsheets_account(bot.util.get_secret("GSHEETS_CREDENTIALS", "config/.env"))
    gsheet = bot.gsheet.connect_to_sheet(gsheet_client, bot.util.get_secret("GSHEETS_SHEET_ID", "config/.env"))


    # Send the closed order to the GSheet
    for order in orders:
            if order['instruction'] in ["SELL_TO_CLOSE", "BUY_TO_CLOSE"]:
                # Check if the order is a closing order
                matching_closing_orders = match_orders(order, closed_orders)
                # for each closing order add it to the gsheet
                for closed_order in matching_closing_orders:
                    row_data = bot.gsheet.format_data(closed_order)
                    bot.gsheet.write_row_at_next_empty_row(gsheet, row_data)


    pass


def match_orders(order, closed_orders):
        # Match the closing order with its corresponding closed position
        matching_closing_orders = [
            closed_order for closed_order in closed_orders
            if closed_order['instrumentId'] == order['instrumentId']
                ]
        return matching_closing_orders

def send_to_discord_webhook(message, new_orders, closed_orders):
    # Send orders to webhook

    # -------------look into refactoring this section of code-------------
    try:
        for order in new_orders:
            if order['instruction'] in ["SELL_TO_CLOSE", "BUY_TO_CLOSE"]:
                # Check if the order is a closing order
                matching_closing_orders = match_orders(order, closed_orders)
                # Send the matched closing data to the webhook
                for closed_order in matching_closing_orders:
                    message = bot.webhook.format_webhook(closed_order, DISCORD_CHANNEL_ID, MESSAGE_TEMPLATE_OPENING, MESSAGE_TEMPLATE_CLOSING)
                    bot.webhook.send_to_discord_webhook(message, WEBHOOK_URL)
            else:
                # Send new order directly to the webhook
                message = bot.webhook.format_webhook(order, DISCORD_CHANNEL_ID, MESSAGE_TEMPLATE_OPENING, MESSAGE_TEMPLATE_CLOSING)
                bot.webhook.send_to_discord_webhook(message, WEBHOOK_URL)

    # ^^^^^^^^^^^^^look into refactoring this section of code^^^^^^^^^^^^^^

    except Exception as e:
        logging.error(f"Error sending data to discord webhook: {str(e)}")


def main():
    # Initialize logging
    logging.basicConfig(level=logging.INFO)
    

    # Initialize database
    sql = bot.SQLDatabase(DATABASE_PATH)
    sql.connect()
    bot.schwab.initialize_database(sql, DROP_TABLES)

    # Initialize Schwab client
    client = bot.Schwab_client(
        bot.util.get_secret("SCHWAB_APP_KEY", "config/.env"),
        bot.util.get_secret("SCHWAB_APP_SECRET", "config/.env")
    )

    # Start the main loop
    loop(client, sql)
    


if __name__ == "__main__":
    main()


