import sqlite3
import json
from datetime import datetime
import logging
from Bot_App.core.order_utils import generate_order_id, parse_description_to_json

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


def store_orders(orders, db_path="orders.db"):
    """Persist orders to SQLite and track open positions."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        for order in orders:
            order_id = generate_order_id(order)
            full_json = json.dumps(order)
            symbol = None
            description = None
            instruction = None
            position_effect = None

            if "orderLegCollection" in order and order["orderLegCollection"]:
                first_leg = order["orderLegCollection"][0]
                instruction = first_leg.get("instruction")
                position_effect = first_leg.get("positionEffect")
                instrument = first_leg.get("instrument", {})
                symbol = instrument.get("symbol")
                description = instrument.get("description")

            try:
                from Bot_App.core.position_tracker import (
                    initialize_open_positions_table,
                )

                # At the start of the function (once per run)
                initialize_open_positions_table(db_path)

                description_data = parse_description_to_json(description)

                cursor.execute(
                    """
                    INSERT INTO schwab_orders (
                        id, entered_time, ticker, instruction, position_effect, order_status,
                        quantity, tag, full_json, posted_to_discord, posted_at,
                        description, description_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        order_id,
                        order.get("enteredTime"),
                        symbol,
                        instruction,
                        position_effect,
                        order.get("status"),
                        order.get("quantity"),
                        order.get("tag"),
                        full_json,
                        0,
                        None,
                        description,
                        description_data,
                    ),
                )

                # After INSERT INTO schwab_orders
                if position_effect == "OPENING":
                    open_id = generate_order_id(order)
                    entered_time = order.get("enteredTime")
                    price = order.get("price", 0)
                    cursor.execute(
                        """
                    INSERT OR IGNORE INTO open_positions (
                        id,
                        ticker,
                        description,
                        price,
                        quantity,
                        entered_time
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                        (
                            open_id,
                            symbol,
                            description,
                            price,
                            order.get("quantity"),
                            entered_time,
                        ),
                    )

            except sqlite3.IntegrityError:
                pass  # Duplicate order, skip

        conn.commit()


def get_unposted_orders(db_path="orders.db"):
    """Return orders that have not been sent to Discord."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
        SELECT id, full_json FROM schwab_orders
        WHERE posted_to_discord = FALSE
    """
        )
        orders = cursor.fetchall()
    return orders


def mark_as_posted(order_id, db_path="orders.db"):
    """Mark an order as posted to Discord."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
        UPDATE schwab_orders
        SET posted_to_discord = TRUE, posted_at = ?
        WHERE id = ?
    """,
            (datetime.utcnow().isoformat(), order_id),
        )
        conn.commit()


def mark_open_positions_closed(
    symbol,
    description,
    up_to_time,
    db_path="orders.db",
):
    """Flag open positions as closed up to ``up_to_time``."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
        UPDATE schwab_orders
        SET is_open_position = 0
        WHERE ticker = ? AND description = ?
        AND position_effect = 'OPENING'
        AND entered_time <= ?
        AND is_open_position = 1
    """,
            (symbol, description, up_to_time),
        )
        conn.commit()


def initialize_db(db_path="orders.db", drop_table=False):
    """Create required tables in the database."""
    import sqlite3
    import logging

    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        if drop_table:
            logging.info("Dropping table 'schwab_orders' if it exists.")
            cursor.execute("DROP TABLE IF EXISTS schwab_orders;")

        # Try adding column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE schwab_orders ADD COLUMN description_data TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schwab_orders (
            id TEXT PRIMARY KEY,
            entered_time TEXT,
            ticker TEXT,
            instruction TEXT,
            position_effect TEXT,
            order_status TEXT,
            quantity REAL,
            tag TEXT,
            full_json TEXT,
            posted_to_discord INTEGER DEFAULT 0,
            posted_at TEXT,
            description TEXT,
            description_data TEXT,
            is_open_position INTEGER DEFAULT 0
        );
        """
)

        conn.commit()
