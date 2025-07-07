# utils.py
import sqlite3
import logging
from constants import DB_PATH
import os
# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

# Setup logging
logging.basicConfig(
    filename="/opt/myapp/app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_db_connection():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        raise

def fetch_query(sql, params=()):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.exception(f"Error executing query: {sql} with params {params}")
        return []
