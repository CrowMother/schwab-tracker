# Schwab Tracker

## Overview
This application tracks Schwab account positions and processes them using a structured workflow. It leverages `main.py` for order processing, database management, and webhook notifications.

## Dependencies
- Python 3.8 or higher  
- `Bot_App` library (assumed installed)  
- `requests` library  
- `logging` module  

## Components

### Main Processing (`main.py`)
Handles the core logic of fetching Schwab account positions, managing orders, and interacting with the database.

### Database Operations
Manages connections to a SQLite database for storing order history and tracking open positions.

## Workflow

1. **Initialization**  
   - Sets up logging.  
   - Initializes database connection.  
   - Creates tables if they don’t exist.  

2. **Schwab Client Setup**  
   - Uses environment variables for authentication credentials.  
   - Connects to Schwab API to fetch account positions.  

3. **Data Processing**  
   - Fetches account positions filtered by "FILLED".  
   - Converts raw data into structured order dictionaries.  
   - Filters out duplicate orders already stored in the database.  

4. **Database Operations**  
   - Stores new orders in the `orders` table.  
   - Maintains the `open_positions` table for tracking active trades.  
   - Processes closing orders and matches them with corresponding open positions.  

5. **Webhook Notifications**  
   - Sends structured messages to a webhook (e.g., Discord) when new or closed orders are processed.  

6. **Loop Execution**  
   - Runs at defined intervals (`LOOP_FREQUENCY`) to continuously fetch and process orders.  

## Configuration
- Uses environment variables stored in `config/.env` for sensitive information such as API keys and webhook URLs.  

## Running Terminals
None  

## Connected MCP Servers
None currently connected  
