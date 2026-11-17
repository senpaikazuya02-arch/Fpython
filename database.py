"""database.py - SQLite database functions for PesoWise Student Budget Tracker."""
import sqlite3
from pathlib import Path

from functions import CATEGORY_RENAMES

# The database file is created in the same folder as this Python file.
DB_FILE = Path(__file__).with_name("pesowise.db")


def connect():
    """Open a connection to the PesoWise database."""
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the tables if they do not exist yet."""
    with connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                category TEXT PRIMARY KEY,
                amount REAL NOT NULL
            )
        """)
        # Old records from the general version get the new student category names.
        for old_name, new_name in CATEGORY_RENAMES.items():
            connection.execute("UPDATE transactions SET category = ? WHERE category = ?",
                               (new_name, old_name))
            connection.execute("UPDATE OR IGNORE budgets SET category = ? WHERE category = ?",
                               (new_name, old_name))


def get_transactions(ttype=None, category=None, month=None, keyword=None):
    """Get transactions, with optional filters. Newest records appear first."""
    query = "SELECT * FROM transactions WHERE 1 = 1"
    values = []

    if ttype:
        query += " AND type = ?"
        values.append(ttype)
    if category:
        query += " AND category = ?"
        values.append(category)
    if month:
        query += " AND date LIKE ?"
        values.append(month + "%")
    if keyword:
        query += " AND (description LIKE ? OR category LIKE ?)"
        values.extend(["%" + keyword + "%", "%" + keyword + "%"])

    query += " ORDER BY date DESC, id DESC"
    with connect() as connection:
        rows = connection.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def get_transaction(transaction_id):
    """Get one transaction using its ID."""
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    return dict(row) if row else None


def is_duplicate(record, ignore_id=None):
    """Check if the same transaction is already saved."""
    query = """SELECT id FROM transactions
               WHERE date = ? AND type = ? AND category = ?
               AND description = ? AND amount = ?"""
    values = [record["date"], record["type"], record["category"],
              record["description"], record["amount"]]
    if ignore_id is not None:
        query += " AND id != ?"
        values.append(ignore_id)

    with connect() as connection:
        row = connection.execute(query, values).fetchone()
    return row is not None


def add_transaction(record):
    """Save a new transaction and return its new ID."""
    with connect() as connection:
        cursor = connection.execute("""
            INSERT INTO transactions (date, type, category, description, amount)
            VALUES (?, ?, ?, ?, ?)
        """, (record["date"], record["type"], record["category"],
              record["description"], record["amount"]))
        return cursor.lastrowid


def update_transaction(transaction_id, record):
    """Update a saved transaction. Return True if a row was changed."""
    with connect() as connection:
        cursor = connection.execute("""
            UPDATE transactions
            SET date = ?, type = ?, category = ?, description = ?, amount = ?
            WHERE id = ?
        """, (record["date"], record["type"], record["category"],
              record["description"], record["amount"], transaction_id))
        return cursor.rowcount > 0


def delete_transaction(transaction_id):
    """Delete one transaction. Return True if a row was deleted."""
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM transactions WHERE id = ?", (transaction_id,)
        )
        return cursor.rowcount > 0


def get_budgets():
    """Return budgets as a dictionary: category -> amount."""
    with connect() as connection:
        rows = connection.execute(
            "SELECT category, amount FROM budgets ORDER BY category"
        ).fetchall()
    return {row["category"]: row["amount"] for row in rows}


def set_budget(category, amount):
    """Add a budget or replace the existing limit for a category."""
    with connect() as connection:
        connection.execute("""
            INSERT INTO budgets (category, amount) VALUES (?, ?)
            ON CONFLICT(category) DO UPDATE SET amount = excluded.amount
        """, (category, amount))


def remove_budget(category):
    """Remove a category budget. Return True if one was removed."""
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM budgets WHERE category = ?", (category,)
        )
        return cursor.rowcount > 0


def clear_all():
    """Delete all transactions and budgets."""
    with connect() as connection:
        connection.execute("DELETE FROM transactions")
        connection.execute("DELETE FROM budgets")
        connection.execute("DELETE FROM sqlite_sequence WHERE name = 'transactions'")