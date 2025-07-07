# constants.py
DB_PATH = "read.db"
CPU_THRESHOLD = 60.0
MEM_THRESHOLD = 70.0
PAGE_SIZE = 10  # Number of records per page

SQL = {
    "distinct_customers": "SELECT DISTINCT customer FROM system_usage",
    "distinct_sids": "SELECT DISTINCT sid FROM system_usage WHERE customer=?",
    "distinct_hosts": "SELECT DISTINCT host FROM system_usage WHERE customer=? AND sid=?",
    "daily_usage": """
        SELECT timestamp, cpu, memory FROM system_usage
        WHERE customer=? AND sid=? AND host=? AND DATE(timestamp)=DATE(?)
        ORDER BY timestamp ASC
    """,
    "custom_usage": """
        SELECT timestamp, cpu, memory FROM system_usage
        WHERE customer=? AND sid=? AND host=? AND DATE(timestamp) BETWEEN DATE(?) AND DATE(?)
        ORDER BY timestamp ASC
    """,
    "download_daily": """
        SELECT customer, sid, timestamp, host, cpu, memory FROM system_usage
        WHERE customer=? AND DATE(timestamp)=DATE(?)
        ORDER BY timestamp ASC
    """,
    "download_monthly": """
        SELECT customer, sid, DATE(timestamp), host,
               ROUND(AVG(cpu), 2), ROUND(AVG(memory), 2)
        FROM system_usage
        WHERE customer=? AND strftime('%Y-%m', timestamp)=?
        GROUP BY customer, sid, DATE(timestamp), host
    """,
    "download_custom": """
        SELECT customer, sid, timestamp, host, cpu, memory FROM system_usage
        WHERE customer=? AND DATE(timestamp) BETWEEN DATE(?) AND DATE(?)
        ORDER BY timestamp ASC
    """,
    "fetch_anomalies": """
        SELECT timestamp, customer, sid, host, cpu, memory
        FROM system_usage ORDER BY timestamp DESC LIMIT 1000
    """,
    
    "SQL_COUNT_ANOMALIES": """
    SELECT COUNT(*) FROM system_usage
    WHERE cpu >= ? OR memory >= ?
    """,

    "SQL_SELECT_ANOMALIES": """
    SELECT timestamp, customer, sid, host, cpu, memory 
    FROM system_usage
    WHERE cpu >= ? OR memory >= ?
    ORDER BY timestamp DESC
    LIMIT ? OFFSET ?
    """,
}
