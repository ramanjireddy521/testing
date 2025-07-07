


from flask import Flask, jsonify, render_template, request, send_file, redirect
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
@app.route("/report")
def landing():
    return render_template("landing.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    try:
        logging.info("starting dashboard route")
        customers = [row[0] for row in fetch_query(SQL["distinct_customer_dashboard"])]
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
                print(f"Daily data for {selected_host}: {data}")
                logging.info(f"Daily data for {selected_host}: {data}")
            elif report_type == "custom":
                data = fetch_query(SQL["custom_usage"], (selected_customer, selected_sid, selected_host, start_date, end_date))
                print(f"Custom data for {selected_host}: {data}")
                logging.info(f"Custom data for {selected_host}: {data}")
            else:
                data = []

            if data:
                timestamps = [datetime.fromisoformat(row[0]) for row in data]
                cpus, mems = zip(*[(row[1], row[2]) for row in data])
                fig = go.Figure([
                    go.Scatter(x=timestamps, y=cpus, mode='lines+markers', name="CPU %"),
                    go.Scatter(x=timestamps, y=mems, mode='lines+markers', name="Memory %")
                ])
                print(f"Rendering graph for {selected_host}")
                logging.info(f"Rendering graph for {selected_host}")
                
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
    logging.info(f"Downloading report for customer: {customer}, date: {date}")
    records = cursor.fetchall()
    conn.close()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Daily Report")
    sheet.write_row(0, 0, ["Customer", "SID", "Date", "Host", "CPU (%)", "Memory (%)"])
    for i, row in enumerate(records):
        sheet.write_row(i + 1, 0, row)
    logging.info(f"Writing {len(records)} records to the report")
    print(f"Writing {len(records)} records to the report")
    workbook.close()
    output.seek(0)
    return send_file(output, download_name=f"{customer}_Daily_Report.xlsx", as_attachment=True)


@app.route("/download_monthly", methods=["POST"])
def download_monthly():
    customer = request.form["customer"]
    date = request.form["date"][:7]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(SQL["download_monthly"], (customer, date))
   
    print(f"Downloading monthly report for customer: {customer}, date: {date}")
    logging.info(f"Downloading monthly report for customer: {customer}, date: {date}")
    
    records = cursor.fetchall()
    conn.close()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Monthly Report")
    sheet.write_row(0, 0, ["Customer", "SID", "Date", "Host", "Avg CPU (%)", "Avg Memory (%)"])
    for i, row in enumerate(records):
        sheet.write_row(i + 1, 0, row)
    logging.info(f"Writing {len(records)} records to the monthly report")
    print(f"Writing {len(records)} records to the monthly report")
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
    cursor.execute(SQL["download_monthly"], (customer, start_date, end_date))
    
    print(f"Downloading custom report for customer: {customer}, from {start_date} to {end_date}")
    logging.info(f"Downloading CPU & memory custom report for customer: {customer}, from {start_date} to {end_date}")
    records = cursor.fetchall()
    conn.close()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Custom Report")
    sheet.write_row(0, 0, ["Customer", "SID", "Date", "Host", "CPU (%)", "Memory (%)"])
    for i, row in enumerate(records):
        sheet.write_row(i + 1, 0, row)
    logging.info(f"Writing {len(records)} records to the custom report")
    print(f"Writing {len(records)} records to the custom report")
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
    print(f"Total anomalies: {total_records}, Total pages: {total_pages}")
    logging.info(f"Total anomalies: {total_records}, Total pages: {total_pages}")
    
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
    print(f"Fetched {len(records)} records for anomalies")
    logging.info(f"Fetched {len(records)} records for anomalies")
    anomalies = [r for r in records if r[4] >= CPU_THRESHOLD or r[5] >= MEM_THRESHOLD]

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Anomalies")
    sheet.write_row(0, 0, ["Timestamp", "Customer", "SID", "Host", "CPU (%)", "Memory (%)"])
    for i, row in enumerate(anomalies):
        sheet.write_row(i + 1, 0, row)
    logging.info(f"Writing {len(anomalies)} anomalies to the report")
    print(f"Writing {len(anomalies)} anomalies to the report")
    workbook.close()
    output.seek(0)

    return send_file(output, download_name="anomaly_report.xlsx", as_attachment=True)

@app.route("/get_sids")
def get_sids():
    customer = request.args.get("customer", "")
    print(" Selecetd Customer " + customer)
    if not customer:
        return json.dumps([])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT sid FROM system_usage WHERE customer=?", (customer,))
    sids = [row[0] for row in cursor.fetchall()]
    print(f"Fetched SIDs for customer {customer}: {sids}")
    logging.info(f"Fetched SIDs for customer {customer}: {sids}")
    conn.close()
    print(f"Returning SIDs: {sids}")
    logging.info(f"Returning SIDs: {sids}")
    return json.dumps(sids)


@app.route("/get_backup_sids")
def get_backup_sids():
    customer = request.args.get("customer", "")
    print(" Selecetd Customer " + customer)
    if not customer:
        return json.dumps([])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT SYSTEM_ID FROM backup_dashboard WHERE customer=?", (customer,))
    sids = [row[0] for row in cursor.fetchall()]
    print(f"Fetched SIDs for customer {customer}: {sids}")
    logging.info(f"Fetched SIDs for customer {customer}: {sids}")
    conn.close()
    return jsonify(sids)


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


@app.route('/get_customers')
def get_customers():
    logging.info("starting dashboard route")
    customers = [row[0] for row in fetch_query(SQL["distinct_customer_backup"])]
    print(f"Available customers for backup_dashboard: {customers}")
    return jsonify(customers)


@app.route("/backup_dashboard")
def backup():
    page = int(request.args.get("page", 1))  # Default to page 1
    offset = (page - 1) * PAGE_SIZE

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Count total anomalies
    cursor.execute(SQL["SQL_BACKUP_STATUS_COUNT"])
    total_records = cursor.fetchone()[0]
    total_pages = math.ceil(total_records  / PAGE_SIZE)

    # Fetch paginated backup
    cursor.execute(SQL["SQL_SELECT_BACKUP_STATUS"], (PAGE_SIZE, offset))
    backup_status = cursor.fetchall()
    conn.close()
    print(f"Fetched {len(backup_status)} records for backup status")
    logging.info(f"Fetched {len(backup_status)} records for backup status") 
    return render_template("backup_dashboard.html", 
                           backup_status=backup_status,
                           current_page=page,
                           total_pages=total_pages)


@app.route("/download_backup")
def download_backup():
    

    customer = request.args.get("customer")
    sid = request.args.get("sid")  # Optional
    date = request.args.get("date")  # Optional single-day
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    print(f"Download request for customer: {customer}, SID: {sid}, date: {date}, start_date: {start_date}, end_date: {end_date}")
    logging.info(f"Download request for customer: {customer}, SID: {sid}, date: {date}, start_date: {start_date}, end_date: {end_date}")

    if not customer:
        return "Customer is required", 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build WHERE clause
    conditions = ["CUSTOMER = ?"]
    params = [customer]

    if sid:
        conditions.append("SYSTEM_ID = ?")
        params.append(sid)

    # Apply date filter regardless of SID
    if date:
        conditions.append("DATE(SYS_START_TIME) = DATE(?)")
        params.append(date)
    elif start_date and end_date:
        conditions.append("DATE(SYS_START_TIME) BETWEEN DATE(?) AND DATE(?)")
        params.extend([start_date, end_date])

    where_clause = " AND ".join(conditions)
    print(f"Where clause: {where_clause}, Params: {params}")
    logging.info(f"Where clause: {where_clause}, Params: {params}")

    # Fetch data
    cursor.execute(f"""
        SELECT CUSTOMER, SYSTEM_ID, HOST, Database_type,
               strftime('%Y-%m-%d %H:%M:%S', SYS_START_TIME) AS SYS_START_TIME,
               ENTRY_TYPE_NAME, STATE_NAME
        FROM backup_dashboard
        WHERE {where_clause}
        ORDER BY SYS_START_TIME DESC
    """, params)
    records = cursor.fetchall()
    print(f"Fetched {len(records)} rows for export")
    conn.close()

    # Prepare Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Backup Status")

    headers = ["Customer", "SID", "Host", "Database_type", "Date", "Entry Type", "Status"]
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    for row_num, row in enumerate(records, start=1):
        for col_num, cell in enumerate(row):
            worksheet.write(row_num, col_num, cell)

    workbook.close()
    output.seek(0)

    filename = f"{customer}_Backup_Status_Report.xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



@app.route("/get_backup_status")
def get_backup_status():
    import sqlite3
    import math
    from flask import request, jsonify

    customer = request.args.get("customer")
    sids = request.args.getlist("sid")  # Handles sid=FS1&sid=FQ1
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 10))
    offset = (page - 1) * page_size

    date = request.args.get("date")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not customer:
        return jsonify({"error": "Customer is required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # -- Build WHERE clause dynamically
    conditions = ["CUSTOMER = ?"]
    params = [customer]

    # Remove empty/blank SIDs before filtering
    sids = [sid.strip() for sid in sids if sid.strip()]
    if sids:
        placeholders = ','.join(['?'] * len(sids))
        conditions.append(f"SYSTEM_ID IN ({placeholders})")
        params.extend(sids)

    if date:
        conditions.append("DATE(SYS_START_TIME) = DATE(?)")
        params.append(date)
    elif start_date and end_date:
        conditions.append("DATE(SYS_START_TIME) BETWEEN DATE(?) AND DATE(?)")
        params.extend([start_date, end_date])

    where_clause = " AND ".join(conditions)

    # -- Count records
    count_query = f"SELECT COUNT(*) FROM backup_dashboard WHERE {where_clause}"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()[0]
    total_pages = max(1, math.ceil(total_records / page_size))

    # -- Fetch paginated records
    data_query = f"""
        SELECT CUSTOMER, SYSTEM_ID, HOST, Database_type,
               strftime('%Y-%m-%d %H:%M:%S', SYS_START_TIME) AS SYS_START_TIME,
               ENTRY_TYPE_NAME, STATE_NAME
        FROM backup_dashboard
        WHERE {where_clause}
        ORDER BY SYS_START_TIME DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_query, params + [page_size, offset])
    rows = cursor.fetchall()
    conn.close()

    return jsonify({
        "records": [
            {
                "CUSTOMER": row[0],
                "SYSTEM_ID": row[1],
                "HOST": row[2],
                "Database_type": row[3],
                "SYS_START_TIME": row[4],
                "ENTRY_TYPE_NAME": row[5],
                "STATE_NAME": row[6],
            } for row in rows
        ],
        "total_pages": total_pages,
        "total_records": total_records
    })


######### file system routes#########
@app.route("/filesystem", methods=["GET", "POST"])
def filesystem():
    try:
        logging.info("starting filesystem route")
        customers = [row[0] for row in fetch_query(SQL["distinct_customer_filesystem"])]
        print(f"Available filesystem customers: {customers}")
        selected_customer = request.form.get("customer", "")
        logging.info(f"Selected customer: {selected_customer}")

        selected_sid = request.form.get("sid", "")
        logging.info(f"Selected SID: {selected_sid}")
        print(f"Selected SID: {selected_sid}")

        selected_host = request.form.get("host", "")
        print(f"Selected Host: {selected_host}")

        report_type = request.form.get("report_type", "day")
        date = request.form.get("date", datetime.now().strftime("%Y-%m-%d"))
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        graph_html = ""

        sids = [row[0] for row in fetch_query(SQL["distinct_sids_app_filesystem"], (selected_customer,))] if selected_customer else []
        hosts = [row[0] for row in fetch_query(SQL["distinct_hosts_app_filesystem"], (selected_customer, selected_sid))] if selected_sid else []
        
        logging.info(f"Selected customer: {selected_customer}, SID: {selected_sid}, Host: {selected_host}, Report type: {report_type}, Date: {date}, Start date: {start_date}, End date: {end_date}")
        
        if request.method == "POST":
            graph_html = ""
            data = []  # Always define it

            host_lower = selected_host.lower()
            is_app_host = "ap" in host_lower
            is_db_host = "db" in host_lower
            is_unknown_host = not (is_app_host or is_db_host)

            # Fetch data based on host type and report type
            if is_db_host:
                if report_type == "day":
                    print(f"Fetching daily data for DB host: {date}")
                    data = fetch_query(SQL["daily_db_file_system"], (selected_customer, selected_sid, selected_host, date))
                    print(f"DB host: Daily data for {selected_host}: {data}")
                elif report_type == "custom":
                    data = fetch_query(SQL["custom_db_file_usage"], (selected_customer, selected_sid, selected_host, start_date, end_date))
                    print(f"DB host: Custom data for {selected_host}: {data}")

            else:
                if report_type == "day":
                    data = fetch_query(SQL["daily_app_file_system"], (selected_customer, selected_sid, selected_host, date))
                    print(f"App host: Daily data for {selected_host}: {data}")
                elif report_type == "custom":
                    data = fetch_query(SQL["custom_app_file_usage"], (selected_customer, selected_sid, selected_host, start_date, end_date))
                    print(f"App host: Custom data for {selected_host}: {data}")


            # Only build graph if there's data
                
            if data:
                try:
                    # ── filter header / non-numeric rows ───────────────
                    clean_rows = []
                    for row in data:
                        try:
                            f1 = float(row[1])
                            f2 = float(row[2])
                            f3 = float(row[3])
                            clean_rows.append((row[0], f1, f2, f3))
                        except (ValueError, TypeError):
                            continue  # skip bad row

                    if not clean_rows:
                        graph_html = "<p style='color:red;'>No valid numeric data to plot.</p>"
                    else:
                        # Extract values
                        timestamps = [datetime.fromisoformat(r[0]) for r in clean_rows]
                        fs1_vals   = [r[1] for r in clean_rows]
                        fs2_vals   = [r[2] for r in clean_rows]
                        fs3_vals   = [r[3] for r in clean_rows]

                        if is_db_host:
                            labels = ["/hana/data (used %)", "/hana/backup (used %)", "/hana/logs (used %)"]
                            print("Rendering graph for DB Host")
                        else:
                            labels = ["/usr/sap (used %)", "/sapmnt (used %)", "/usr/sap/trans (used %)"]
                            print("Rendering graph for App Host")

                        print("###### -> " + labels[0])
                        logging.info("###### -> " + labels[0])

                        fig = go.Figure([
                            go.Scatter(x=timestamps, y=fs1_vals, mode='lines+markers', name=labels[0]),
                            go.Scatter(x=timestamps, y=fs2_vals, mode='lines+markers', name=labels[1]),
                            go.Scatter(x=timestamps, y=fs3_vals, mode='lines+markers', name=labels[2])
                        ])
                        fig.update_layout(
                            title="File System Usage",
                            xaxis_title="Time",
                            yaxis_title="Usage (%)",
                            template="plotly_white"
                        )
                        graph_html = fig.to_html(
                            full_html=False,
                            config={
                                "modeBarButtonsToAdd": ["zoom", "pan", "lasso2d", "hoverClosestCartesian"],
                                "displayModeBar": False,
                            }
                        )
                except Exception as e:
                    logging.error(f"Error processing graph data: {e}")
                    graph_html = "<p style='color:red;'>Error generating graph.</p>"

            
    except Exception as e:
        logging.exception("Error in /filesystem route")
        return "An error occurred while loading the filesystem."
    return render_template("filesystem.html", customers=customers, sids=sids, hosts=hosts,
                               selected_customer=selected_customer, selected_sid=selected_sid,
                               selected_host=selected_host, report_type=report_type, date=date,
                               start_date=start_date, end_date=end_date, graph=graph_html)



@app.route("/download_filesystem", methods=["POST"])
def download_filesystem():
    customer = request.form["customer"]
    day      = request.form["date"]                       # YYYY-MM-DD
    host_raw = request.form.get("host", "").strip().lower()
    is_db_host = "db" in host_raw

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Download request -> customer={customer}, day={day}, is_db_host={is_db_host}")

    # ------------------------------------------------------------------ #
    #  DB hosts  (contains 'db')                                          #
    # ------------------------------------------------------------------ #
    if is_db_host:
        headers = [
            "Customer", "SID", "Timestamp", "Host",
            "/hana/data (used GB)", "/hana/data (available GB)", "/hana/data (used %)",
            "/hana/backup (used GB)", "/hana/backup (available GB)", "/hana/backup (used %)",
            "/hana/log (used GB)", "/hana/log (available GB)", "/hana/log (used %)"
        ]

        cursor.execute("""
            SELECT customer,
                   sid,
                   timestamp,
                   host,
                   hana_data_used,
                   hana_data_available,
                   "hana_data_used_percent",
                   hana_backup_used,
                   hana_backup_available,
                   "hana_backup_used_percent",
                   hana_log_used,
                   hana_log_available,
                   "hana_log_used_percent"
            FROM   file_system_usage
            WHERE  customer = ?
              
              AND  DATE(timestamp)  AND DATE(?)
              AND  LOWER(host) LIKE '%db%'
            ORDER BY timestamp ASC
        """, (customer,  day))

    # ------------------------------------------------------------------ #
    #  APP / non-DB hosts                                                 #
    # ------------------------------------------------------------------ #
    else:
        headers = ["Customer", "SID", "Timestamp", "Host",
                   "/usr/sap (used GB)","/usr/sap (avilable GB)", "/usr/sap (used %)",
                   "/sapmnt (used GB)", "/sapmnt (available GB)", "/sapmnt (used %)",
                   "/usr/sap/trans (used GB)", "/usr/sap/trans (available GB)", "/usr/sap/trans (used %)"]

        cursor.execute("""
            SELECT customer,
                   sid,
                   timestamp,
                   host,
                   USR_SAP_USED,
                   USR_SAP_AVAILABLE,
                   "USR_SAP_used_percent",
                   sapmnt_used,
                   sapmnt_available,
                   "sapmnt_used_percent",
                   USR_SAP_TRANS_USED,
                   USR_SAP_TRANS_AVAILABLE,
                   "USR_SAP_TRANS_used_percent"
    
            FROM   file_system_usage
            WHERE  customer = ?
              AND  strftime('%Y-%m-%d', timestamp) = ?
              AND  lower(host) NOT LIKE '%db%'
            ORDER  BY timestamp ASC
        """, (customer, day))

    records = cursor.fetchall()
    conn.close()

    # --------------------------- Excel build ----------------------------
    output   = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    sheet    = workbook.add_worksheet("Daily Report")

    sheet.write_row(0, 0, headers)
    for idx, row in enumerate(records, start=1):
        sheet.write_row(idx, 0, row)

    workbook.close()
    output.seek(0)

    filename = f"{customer}_File_System_Daily_Report.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)



@app.route("/download_monthly_filesystem", methods=["POST"])
def download_monthly_filesystem():
    customer    = request.form["customer"]
    sid_param   = request.form["sid"].strip().upper()
    year_month  = request.form["date"][:7]               # YYYY-MM
    host_param  = request.form.get("host", "").lower()    # "db" | "app" | real host

    is_db_host  = "db" in host_param
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if is_db_host:
    # ------------ DB branch: average numeric columns -----------------
        headers = [
            "Customer", "SID", "Timestamp", "Host",
            "/hana/data (Avg used GB)", "/hana/data (Avg available GB)", "/hana/data (Avg used %)",
            "/hana/backup (Avg used GB)", "/hana/backup (Avg available GB)", "/hana/backup (used %)",
            "/hana/log (Avg used GB)", "/hana/log (Avg available GB)", "/hana/log (Avg used %)"
        ]

        cursor.execute(
            """
            SELECT customer,
                   sid,
                   host,
                   ROUND(AVG(hana_data_used),          2),
                   ROUND(AVG(hana_data_available),     2),
                   ROUND(AVG("hana_data_used_percent"),     2),
                   ROUND(AVG(hana_backup_used),        2),
                   ROUND(AVG(hana_backup_available),   2),
                   ROUND(AVG("hana_backup_used_percent"),   2),
                   ROUND(AVG(hana_log_used),           2),
                   ROUND(AVG(hana_log_available),      2),
                   ROUND(AVG("hana_log_used_percent"),      2)
            FROM   file_system_usage
            WHERE  customer = ?
              AND  sid      = ?
              AND  strftime('%Y-%m', timestamp) = ?
              AND  lower(host) LIKE '%db%'
            GROUP  BY customer, sid, host
            ORDER  BY host
            """,
            (customer, sid_param, year_month)
        )
    else:
        # ------------ APP / non-DB branch --------------------------------
        headers = ["Customer", "SID", "Timestamp", "Host",
                   "/usr/sap (Avg used GB)","/usr/sap (Avg avilable GB)", "/usr/sap (Avg used %)",
                   "/sapmnt (Avg used GB)", "/sapmnt (Avg available GB)", "/sapmnt (Avg used %)",
                   "/usr/sap/trans (Avg used GB)", "/usr/sap/trans (Avg available GB)", "/usr/sap/trans (Avg used %)"]

        cursor.execute(
            """
            SELECT customer,
                   sid,
                   host,
                   ROUND(AVG(usr_sap_used),            2),
                   ROUND(AVG(usr_sap_available),        2),
                   ROUND(AVG("usr_sap_used_percent"),        2),
                   ROUND(AVG(sapmnt_used),             2),
                   ROUND(AVG(sapmnt_available),         2),
                   ROUND(AVG("sapmnt_used_percent"),         2),
                   ROUND(AVG(usr_sap_trans_used),      2),
                   ROUND(AVG(usr_sap_trans_available),  2),
                   ROUND(AVG("usr_sap_trans_used_percent"),  2)
            FROM   file_system_usage
            WHERE  customer = ?
              AND  sid      = ?
              AND  strftime('%Y-%m', timestamp) = ?
              AND  lower(host) NOT LIKE '%db%'
            GROUP  BY customer, sid, host
            ORDER  BY host
            """,
            (customer, sid_param, year_month)
        )

    rows = cursor.fetchall()
    conn.close()

    # --------------------------- build Excel ----------------------------
    output   = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    sheet    = workbook.add_worksheet("Monthly Report")

    sheet.write_row(0, 0, headers)
    for i, row in enumerate(rows, start=1):
        sheet.write_row(i, 0, row)

    workbook.close()
    output.seek(0)

    fname = f"{customer}_{sid_param}_{year_month}_filesystem_monthly.xlsx"
    return send_file(output, download_name=fname, as_attachment=True)



@app.route("/download_custom_filesystem", methods=["POST"])
def download_custom_filesystem():
    customer    = request.form["customer"]
    sid         = request.form["sid"]
    host        = request.form["host"].strip().lower()
    start_date  = request.form["start_date"]
    end_date    = request.form["end_date"]

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if "db" in host.lower():
        # DB host: fetch full DB-related columns
        header = [
            "Customer", "SID", "Timestamp", "Host",
            "/hana/data (used GB)", "/hana/data (available GB)", "/hana/data (used %)",
            "/hana/backup (used GB)", "/hana/backup (available GB)", "/hana/backup (used %)",
            "/hana/log (used GB)", "/hana/log (available GB)", "/hana/log (used %)"
        ]

        cursor.execute("""
            SELECT customer,
                   sid,
                   timestamp,
                   host,
                   hana_data_used,
                   hana_data_available,
                   "hana_data_used_percent",
                   hana_backup_used,
                   hana_backup_available,
                   "hana_backup_used_percent",
                   hana_log_used,
                   hana_log_available,
                   "hana_log_used_percent"
            FROM   file_system_usage
            WHERE  customer = ?
              AND  sid = ?
              AND  DATE(timestamp) BETWEEN DATE(?) AND DATE(?)
              AND  LOWER(host) LIKE '%db%'
            ORDER BY timestamp ASC
        """, (customer, sid, start_date, end_date))

    else:
        # Non-DB host: fallback to APP file system table
        header = ["Customer", "SID", "Timestamp", "Host",
                   "/usr/sap (used GB)","/usr/sap (avilable GB)", "/usr/sap (used %)",
                   "/sapmnt (used GB)", "/sapmnt (available GB)", "/sapmnt (used %)",
                   "/usr/sap/trans (used GB)", "/usr/sap/trans (available GB)", "/usr/sap/trans (used %)"]
        cursor.execute("""
            SELECT customer,
                   sid,
                   timestamp,
                   host,
                   USR_SAP_USED,
                   USR_SAP_AVAILABLE,
                   "USR_SAP_used_percent",
                   sapmnt_used,
                   sapmnt_available,
                   "sapmnt_used_percent",
                   USR_SAP_TRANS_USED,
                   USR_SAP_TRANS_AVAILABLE,
                   "USR_SAP_TRANS_used_percent"
    
            FROM   file_system_usage
            WHERE  customer = ?
              AND  sid = ?
              AND  DATE(timestamp) BETWEEN DATE(?) AND DATE(?)
              AND  LOWER(host) NOT LIKE '%db%'
            ORDER BY timestamp ASC
        """, (customer, sid, start_date, end_date))

    records = cursor.fetchall()
    conn.close()

    # Build Excel
    output   = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet    = workbook.add_worksheet("Custom Report")

    sheet.write_row(0, 0, header)
    for i, row in enumerate(records, start=1):
        sheet.write_row(i, 0, row)

    workbook.close()
    output.seek(0)

    filename = f"{customer}_custom_File_System_Report.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)





@app.route("/get_filesystem_sids")
def get_filesystem_sids():
    customer = request.args.get("customer", "")
    print(" Selecetd Customer " + customer)
    if not customer:
        return json.dumps([])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(SQL["distinct_sids_app_filesystem"])
    sids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(sids)



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)



