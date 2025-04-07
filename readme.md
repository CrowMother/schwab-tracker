# Schwab Order to Discord Notifier

This Python application creates a semi-real-time pipeline that fetches Charles Schwab order data using a third-party API and posts new trade events to a Discord channel via webhook.

## Features

- Stores all Schwab orders in a local SQLite database

- Deduplicates orders using a unique hash (based on entry time, instruction, and symbol)

- Formats Discord messages dynamically, including multi-leg orders

- Calculates percentage gain/loss on closing trades by referencing previous opening orders

- Detects and labels:

   - New position (Opening 🟢)

  - Full closes (Closing 🔴)

  - Partial closes (Partially Closing 🟠)

  - Position sizing up (Scaling Up 🟢)

## How It Works

- Fetches all orders from Schwab within the last N hours

- Stores new orders into the database

- Checks which orders haven't been posted to Discord

- Formats and sends a message to a Discord webhook

- Marks orders as posted to prevent duplicates

## File Overview

- schwab_pipeline_post_discord.py — Main processing logic: data retrieval, formatting, and posting

- orders.db — SQLite database storing all order metadata and raw JSON

## Setup Instructions

1. Requirements

- Python 3.8+

- Packages:

- requests

- Install via pip:
``` bash
pip install requests
```
2. Configure Discord Webhook

- Update the following line in the code with your actual webhook:

- DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID"

3. Run the Script

- You can run the main function manually or via a scheduler like cron:

- python schwab_pipeline_post_discord.py

## Customization

- You can customize the Discord message format in the format_discord_message function.

- The database logic assumes the Schwab API returns a consistent JSON structure.

## License

- MIT

## Credits

Created by DevNest.

