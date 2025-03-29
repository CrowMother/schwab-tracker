import logging
import requests
import sqlite3
import time

# Local imports
import Bot_App as bot

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


def filter_new_orders(orders, existing_orders):
    """
    Filter out orders that already exist in the database by checking all relevant fields.
    
    Args:
        orders (list): A list of orders (dictionaries) to check.
        existing_orders (set): A set of tuples representing existing orders in the database.
    
    Returns:
        list: A list of new orders that do not exist in the database.
    """
    new_orders = []  # Initialize an empty list to store new orders

    for order in orders:
        # Extract relevant fields from the order
        order_symbol = order.get('underlyingSymbol')
        order_description = order.get('description')
        order_price = order.get('orderPrice')
        order_instrument_id = order.get('instrumentId')

        # Create a tuple representing the current order
        order_tuple = (order_symbol, order_description, order_price, order_instrument_id)

        # Check if the order exists in the database
        if order_tuple not in existing_orders:
            new_orders.append(order)  # Add new order to the list
    
    return new_orders  # Return only the new orders


def match_orders(order, closed_orders):
        # Match the closing order with its corresponding closed position
        matching_closing_orders = [
            closed_order for closed_order in closed_orders
            if closed_order['instrumentId'] == order['instrumentId']
                ]
        return matching_closing_orders

def format_variables_in_orders(orders):
    for order in orders:
        order = bot.schwab.split_description(order)

    return orders

def break_into_legs(orders):
    #break into legs
    try:
        orderLegs = []
        for order in orders:
            order = bot.schwab.extract_and_normailze_legs(order)
            for leg in order:
                orderLegs.append(leg)

        return orderLegs

    except Exception as e:
        logging.error(f"Error breaking into legs: {e}")