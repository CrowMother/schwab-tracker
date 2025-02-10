

# Readme.md

## Overview
This application tracks positions from a Schwab account and sends updates via a webhook. It uses two main libraries: `pairing.py` for order matching and `sql_control.py` for database operations.

## Dependencies
- Python 3.8 or higher
- Bot_App library (assuming it's installed)
- requests library
- logging module

## Components
### Pairing.py
Contains functions to:
- Match orders based on symbol, description, and instruction type.
- Specifically checks for matching opening orders when processing closing instructions.

### SQL Control
Handles database operations including:
- Connecting to a MySQL/MariaDB instance
- Creating tables if they don't exist
- Inserting new records
- Querying existing data

## Workflow
1. Creates a Schwab client using credentials from environment variables.
2. Fetches account positions filtered by "FILLED".
3. Processes each position into a structured order dictionary.
4. Checks if the order already exists in the database:
   - If it does, skips further processing.
   - If it doesn't, continues to insert new data.
5. For closing orders:
   - Uses `pairing.py` to find and match corresponding opening orders.
6. Sends each processed order to a webhook URL (configured via environment variables).
7. Maintains database connectivity throughout the process.

## Notes
- SQL injection: The current implementation uses string formatting for SQL queries, which is **not recommended** in production. Consider using parameterized queries instead.
- Database connection: Assumes a MySQL/MariaDB instance with proper credentials setup.
- Environment variables: Ensure you have `WEBHOOK_URL`, `SCHWAB_APP_KEY`, and `SCHWAB_APP_SECRET` configured before running.

## How to Run
1. Clone the repository or copy all files into your directory.
2. Create a `.env` file in the config folder with:
```
WEBHOOK_URL=your_webhook_url
SCHWAB_APP_KEY=your_schwab_app_key
SCHWAB_APP_SECRET=your_schwab_app_secret
```
3. Run the script from the terminal:
```bash
python main.py
```

For detailed setup instructions or troubleshooting, refer to the Bot_App documentation and ensure all dependencies are properly configured.