import logging
import requests
import sqlite3
import time

# Local imports
import Bot_App as bot

# Constants
# for report generation prevent multiple reports off one loop
ISREPORTGEN = False

#BOT CONFIG
OUTPUT_PATH = bot.util.get_secret("OUTPUT_PATH", "config/.env")

#SCHWAB CONFIG
BROKER = bot.util.get_secret("BROKER", "config/.env")
FILTER = "FILLED"

#DISCORD CONFIG
WEBHOOK_URL = bot.util.get_secret("WEBHOOK_URL", "config/.env")
WEBHOOK_EXTENSION = bot.util.get_secret("WEBHOOK_EXTENSION", "config/.env")
DISCORD_CHANNEL_ID = bot.util.get_secret("DISCORD_CHANNEL_ID", "config/.env")
MESSAGE_TEMPLATE_OPENING = bot.util.get_secret("MESSAGE_TEMPLATE_OPENING", "config/.env")
MESSAGE_TEMPLATE_CLOSING = bot.util.get_secret("MESSAGE_TEMPLATE_CLOSING", "config/.env")

#DATABASE CONFIG
DATABASE_PATH = bot.util.get_secret("DATABASE_PATH", "config/.env")

#LOOP CONFIG
LOOP_FREQUENCY = int(bot.util.get_secret("LOOP_FREQUENCY", "config/.env", 60))
TIME_DELTA = int(bot.util.get_secret("TIME_DELTA", "config/.env", 168))
LOOP_TYPE = bot.util.get_secret("LOOP_TYPE", "config/.env")

DAY_OF_WEEK = int(bot.util.get_secret("DAY_OF_WEEK", "config/.env", 4))
HOUR_OF_DAY = int(bot.util.get_secret("HOUR_OF_DAY", "config/.env", 16))

#DEBUG CONFIG
DROP_TABLES = bool(bot.util.get_secret("DROP_TABLES", "config/.env"))


def loop(client, sql, interval=LOOP_FREQUENCY):
    """
    Executes a continuous loop to process orders at specified intervals.

    Depending on the `LOOP_TYPE`, the function either runs `loop_work` on a 
    weekly schedule (every Friday at 4:00 PM EST) or at regular intervals 
    specified by `interval`.

    Args:
        client: The Schwab client to retrieve account positions from.
        sql: The SQL database instance to update with order data.
        interval (int, optional): The time interval in seconds for running `loop_work` 
                                  when `LOOP_TYPE` is "INTERVAL". Defaults to `LOOP_FREQUENCY`.

    Raises:
        ValueError: If `LOOP_TYPE` is neither "WEEKLY" nor "INTERVAL".

    Workflow:
        - If `LOOP_TYPE` is "WEEKLY", waits until the specified day and time to run `loop_work`.
        - If `LOOP_TYPE` is "INTERVAL", runs `loop_work` continuously with a sleep interval.
        - Logs errors and loop completion messages.
    """

    # Run loop_work on specified time of the week
    # Timer for running loop_work on a specified time of the week
    if LOOP_TYPE == "WEEKLY":
        global ISREPORTGEN
        while True:
            
            if bot.util.check_time_of_week(DAY_OF_WEEK, HOUR_OF_DAY):
                if not ISREPORTGEN:
                    logging.info("start to create reports")
                    error = loop_work(client, sql)
                    ISREPORTGEN = True
            else:
                ISREPORTGEN = False
            time.sleep(interval)
    
    # Run loop_work on specified time of each day
    elif LOOP_TYPE == "DAILY":
        while True:
            if bot.util.check_time_of_day(HOUR_OF_DAY):
                if not ISREPORTGEN:
                    logging.info("start to create reports")
                    error = loop_work(client, sql)
                    ISREPORTGEN = True
            else:
                ISREPORTGEN = False
            time.sleep(interval)
        
    elif LOOP_TYPE == "INTERVAL":
        # Simple Timer Loop
        while True:
            error = loop_work(client, sql)
            if error:
                break
            logging.info(f"Loop iteration completed, sleeping for {interval} seconds")
            time.sleep(interval)

    elif LOOP_TYPE == "DEBUG":
        error = loop_work(client, sql)
        if error:
            logging.error(f"Error occurred in loop_work, ERROR: {error}")
            return
    else:
        raise ValueError("Unknown loop type: {}".format(LOOP_TYPE))


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
        logging.debug(f"Passed client: {client} and sql: {sql}")
        # Fetch orders from Schwab
        orders = get_data(client)

        orders = process_data(orders)

        orders = format_orders(orders)
        logging.debug(f"Orders processed: {len(orders)}")

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
    try:
        #connect to google sheets
        #look into the following lines of code -------------------------------------------
        gsheet_client = bot.gsheet.connect_gsheets_account(bot.util.get_secret("GSHEETS_CREDENTIALS", "config/.env"))
        gsheet = bot.gsheet.connect_to_sheet(gsheet_client, bot.util.get_secret("GSHEETS_SHEET_ID", "config/.env"), bot.util.get_secret("GSHEETS_SHEET_NAME", "config/.env"))


        #insert header row
        bot.gsheet.copy_headers(gsheet, f"A{bot.gsheet.get_next_empty_row(gsheet, 2)}")
        week = bot.util.get_monday_of_current_week()
        logging.info(f"week: {week}")
        bot.gsheet.insert_data(gsheet, f"A{bot.gsheet.get_next_empty_row(gsheet, 2)}", [[week]])

        matching_closing_orders = []
        # Send the closed order to the GSheet
        for order in orders:
                if order['instruction'] in ["SELL_TO_CLOSE", "BUY_TO_CLOSE"]:
                    # Check if the order is a closing order
                    matching_closing_orders.append(match_orders(order, closed_orders))

        #IDs of the orders that have already been posted
        posted_IDs = []
        # for each closing order add it to the gsheet
        for closed_order in matching_closing_orders:
            row_data = bot.gsheet.format_data(closed_order[0])

            #create an ID for the order
            order_id = bot.gsheet.create_id(closed_order[0])
            
            #check if ID has already been posted
            if order_id not in posted_IDs:
                posted_IDs.append(order_id)
                bot.gsheet.write_row_at_next_empty_row(gsheet, row_data)
            else:
                logging.debug(f"Order with ID {order_id} already posted, skipping")

    except Exception as e:
        logging.error(f"Error sending data to google sheets: {str(e)}")


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
    
    try:
        # Initialize database
        sql = bot.SQLDatabase(DATABASE_PATH)
        sql.connect()
        bot.schwab.initialize_database(sql, DROP_TABLES)

        # Initialize Schwab client
        client = bot.Schwab_client(
            bot.util.get_secret("SCHWAB_APP_KEY", "config/.env"),
            bot.util.get_secret("SCHWAB_APP_SECRET", "config/.env")
        )

    except Exception as e:
        logging.error(f"Error in main: {e}")
        return

    # Start the main loop
    loop(client, sql)
    

def get_data(client):
    response = client.get_account_positions(FILTER, TIME_DELTA)

    orders = [bot.sort_schwab_data_dynamically(bot.get_keys(), position) for position in response]

    logging.debug(f"Orders fetched: {len(orders)}")
    return orders

def process_data(orders):
    #check each order if there is multiple legs in the order and split them up
        #add this to the order processing above
    for order in orders:
        if order['complexOrderStrategyType'] != 'NONE':
            #save the split orders returned
            split_orders = bot.schwab.split_complex_order_strategy(order)

            #check if split orders were returned
            if not split_orders:
                continue
            #replace the original order with the split orders
            orders.remove(order)
            orders.extend(split_orders)
        else:
            order = bot.schwab.flatten_data(order)

    return orders

def format_orders(orders):
    for order in orders:
        order = bot.schwab.split_description(order)

    return orders

if __name__ == "__main__":
    main()


