from flask import Flask, render_template, request, send_file, redirect
from datetime import datetime
import io
import xlsxwriter
import plotly.graph_objs as go
from constants import SQL, CPU_THRESHOLD, MEM_THRESHOLD, DB_PATH, PAGE_SIZE
from utils import fetch_query
import logging
import sqlite3
import os
import math

app = Flask(__name__)

@app.route("/")
def home():
    return redirect("/dashboard")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    try:
        logging.info("starting dashboard route")
        customers = [row[0] for row in fetch_query(SQL["distinct_customers"])]
        print(f"Available customers: {customers}")
        selected_customer = request.form.get("customer", "")
        logging.info(f"Selected customer: {selected_customer}")
        selected_sid = request.form.get("sid", "")
        logging.info(f"Selected SID: {selected_sid}")
        selected_host = request.form.get("host", "")
    
        report_type = request.form.get("report_type", "day")
        date = request.form.get("date", datetime.now().strftime("%Y-%m-%d"))
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        graph_html = ""

        sids = [row[0] for row in fetch_query(SQL["distinct_sids"], (selected_customer,))] if selected_customer else []
        hosts = [row[0] for row in fetch_query(SQL["distinct_hosts"], (selected_customer, selected_sid))] if selected_sid else []
        
        logging.info(f"Selected customer: {selected_customer}, SID: {selected_sid}, Host: {selected_host}, Report type: {report_type}, Date: {date}, Start date: {start_date}, End date: {end_date}")
        

        if request.method == "POST":
            if report_type == "day":
                data = fetch_query(SQL["daily_usage"], (selected_customer, selected_sid, selected_host, date))
            elif report_type == "custom":
                data = fetch_query(SQL["custom_usage"], (selected_customer, selected_sid, selected_host, start_date, end_date))
            else:
                data = []

            if data:
                timestamps = [datetime.fromisoformat(row[0]) for row in data]
                cpus, mems = zip(*[(row[1], row[2]) for row in data])
                fig = go.Figure([
                    go.Scatter(x=timestamps, y=cpus, mode='lines+markers', name="CPU %"),
                    go.Scatter(x=timestamps, y=mems, mode='lines+markers', name="Memory %")
                ])
                fig.update_layout(title="System Usage", xaxis_title="Time", yaxis_title="%", template="plotly_white")
                graph_html = fig.to_html(
                    full_html=False,
                    config={
                        "modeBarButtonsToAdd": [ "zoom", "pan", "lasso2d", "hoverClosestCartesian"],
                        "displayModeBar": False,
                    }
                )

        return render_template("dashboard.html", customers=customers, sids=sids, hosts=hosts,
                               selected_customer=selected_customer, selected_sid=selected_sid,
                               selected_host=selected_host, report_type=report_type, date=date,
                               start_date=start_date, end_date=end_date, graph=graph_html)
    except Exception as e:
        logging.exception("Error in dashboard route")
        return "An error occurred while loading the dashboard."



@app.route("/download_dashboard", methods=["POST"])
def download_dashboard():
    customer = request.form["customer"]
    date = request.form["date"]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT customer, sid, timestamp, host, cpu, memory FROM system_usage
        WHERE customer=? AND DATE(timestamp)=DATE(?) ORDER BY timestamp ASC
    """, (customer, date))

    print(f"Downloading report for customer: {customer}, date: {date}")
    records = cursor.fetchall()
    conn.close()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Daily Report")
    sheet.write_row(0, 0, ["Customer", "SID", "Date", "Host", "CPU (%)", "Memory (%)"])
    for i, row in enumerate(records):
        sheet.write_row(i + 1, 0, row)
    workbook.close()
    output.seek(0)
    return send_file(output, download_name=f"{customer}_Daily_Report.xlsx", as_attachment=True)

@app.route("/download_monthly", methods=["POST"])
def download_monthly():
    customer = request.form["customer"]
    date = request.form["date"][:7]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT customer, sid, DATE(timestamp), host,
               ROUND(AVG(cpu), 2), ROUND(AVG(memory), 2)
        FROM system_usage
        WHERE customer=? AND strftime('%Y-%m', timestamp)=?
        GROUP BY customer, sid, DATE(timestamp), host
    """, (customer, date))
    records = cursor.fetchall()
    conn.close()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Monthly Report")
    sheet.write_row(0, 0, ["Customer", "SID", "Date", "Host", "Avg CPU (%)", "Avg Memory (%)"])
    for i, row in enumerate(records):
        sheet.write_row(i + 1, 0, row)
    workbook.close()
    output.seek(0)
    return send_file(output, download_name=f"{customer}_Monthly_Report.xlsx", as_attachment=True)

@app.route("/download_custom", methods=["POST"])
def download_custom():
    customer = request.form["customer"]
    sid = request.form["sid"]
    host = request.form["host"]
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT customer, sid, timestamp, host, cpu, memory FROM system_usage
        WHERE customer=?  AND DATE(timestamp) BETWEEN DATE(?) AND DATE(?)
        ORDER BY timestamp ASC
    """, (customer,  start_date, end_date))
    print(f"Downloading custom report for customer: {customer}, from {start_date} to {end_date}")
    records = cursor.fetchall()
    conn.close()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Custom Report")
    sheet.write_row(0, 0, ["Customer", "SID", "Date", "Host", "CPU (%)", "Memory (%)"])
    for i, row in enumerate(records):
        sheet.write_row(i + 1, 0, row)
    workbook.close()
    output.seek(0)
    return send_file(output, download_name=f"{customer}_Custom_Report.xlsx", as_attachment=True)

@app.route("/anomaly")
def anomaly():
    page = int(request.args.get("page", 1))  # Default to page 1
    offset = (page - 1) * PAGE_SIZE

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Count total anomalies
    cursor.execute(SQL["SQL_COUNT_ANOMALIES"], (CPU_THRESHOLD, MEM_THRESHOLD))
    total_records = cursor.fetchone()[0]
    total_pages = math.ceil(total_records / PAGE_SIZE)

    # Fetch paginated anomalies
    cursor.execute(SQL["SQL_SELECT_ANOMALIES"], (CPU_THRESHOLD, MEM_THRESHOLD, PAGE_SIZE, offset))
    anomalies = cursor.fetchall()
    conn.close()

    return render_template("anomaly.html", 
                           anomalies=anomalies,
                           current_page=page,
                           total_pages=total_pages)



@app.route("/download_anomalies")
def download_anomalies():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, customer, sid, host, cpu, memory FROM system_usage ORDER BY timestamp DESC LIMIT 1000")
    records = cursor.fetchall()
    conn.close()

    anomalies = [r for r in records if r[4] >= CPU_THRESHOLD or r[5] >= MEM_THRESHOLD]

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Anomalies")
    sheet.write_row(0, 0, ["Timestamp", "Customer", "SID", "Host", "CPU (%)", "Memory (%)"])
    for i, row in enumerate(anomalies):
        sheet.write_row(i + 1, 0, row)
    workbook.close()
    output.seek(0)

    return send_file(output, download_name="anomaly_report.xlsx", as_attachment=True)

@app.route("/get_sids")
def get_sids():
    customer = request.args.get("customer", "")
    if not customer:
        return json.dumps([])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT sid FROM system_usage WHERE customer=?", (customer,))
    sids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return json.dumps(sids)

@app.route("/get_hosts")
def get_hosts():
    customer = request.args.get("customer", "")
    sid = request.args.get("sid", "")
    if not customer or not sid:
        return json.dumps([])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT host FROM system_usage WHERE customer=? AND sid=?", (customer, sid))
    hosts = [row[0] for row in cursor.fetchall()]
    conn.close()
    return json.dumps(hosts)

if __name__ == "__main__":
    app.run(debug=True)
