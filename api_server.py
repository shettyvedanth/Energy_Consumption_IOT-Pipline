import smtplib
import time
import requests
import pandas as pd
from email.mime.text import MIMEText
from fastapi import FastAPI
from influxdb_client import InfluxDBClient
from digital_supervisor import DigitalEnergySupervisor

app = FastAPI(title="HLT200 Final Sync API")

# --- CLOUD CONFIG ---
INFLUX_URL = "http://52.90.139.142:8086"
INFLUX_TOKEN = "FoM718mNxcQDh9KuySYDomNmvbqEB1S1l7AUHIz-s6aTDGzro0n9vg2xJYtlwhE8hy0SKn7Cdd_RDtUoI00kxw=="
INFLUX_ORG, INFLUX_BUCKET = "cittagent", "hlt200_data"
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()

# --- NOTIFICATIONS ---
SENDER_EMAIL = "vedanth.jshetty21@gmail.com"
SENDER_PASSWORD = "cyqdmiwjcsqkyocl"
RECEIVER_EMAILS = ["vedanth.shetty@cittagent.com", "manash.ray@cittagent.com"]
TELEGRAM_TOKEN = "8226923778:AAEbwZ0hHsM-tgWNiWySrCjNWmhLbWP4j2o"
TELEGRAM_CHAT_ID = "945537471"

last_sent = {}
COOLDOWN = 900

def send_alerts(a):
    title = a['title']
    msg = (f"HLT200 INDUSTRIAL ALERT\n"
           f"------------------------------------\n"
           f"Issue: {title}\n"
           f"Money Burn: ₹ {a['cost_impact']:.2f} / hour\n\n"
           f"Reason: {a['reason']}\n"
           f"Action: {a['action']}\n\n"
           f"------------------------------------\n"
           f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Telegram
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass
    
    # Email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            for rec in RECEIVER_EMAILS:
                m = MIMEText(msg)
                m['Subject'] = f"🔴 ALERT: {title}"
                m['To'] = rec
                server.sendmail(SENDER_EMAIL, rec, m.as_string())
    except:
        pass

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/live/analysis")
def get_analysis():
    try:
        query = f'''
        from(bucket:"{INFLUX_BUCKET}")
        |> range(start: -15m)
        |> filter(fn:(r) => r._measurement == "compressor_readings")
        |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        |> sort(columns:["_time"], desc:true)
        |> limit(n:1)
        '''
        
        result = query_api.query_data_frame(query)
        
        # Handle case where InfluxDB returns a list of DataFrames
        if isinstance(result, list):
            if len(result) == 0:
                return {"status": "Waiting for data"}
            df = result[0]
        else:
            df = result
        
        if df is None or df.empty:
            return {"status": "Waiting for data"}
        
        # Rename columns to match supervisor expectations
        df = df.rename(columns={
            "power_kw": "actual_kw",
            "machine_state": "machine_state",
            "pressure": "discharge_pressure_bar",
            "temp_inlet": "inlet_temp_c",
            "_time": "timestamp"
        })
        
        # Get the first row as a dictionary
        row = df.iloc[0].to_dict()
        
        # Initialize supervisor
        supervisor = DigitalEnergySupervisor()
        supervisor.analyze_row(row)
        
        # Send alerts if cooldown period has passed
        for a in supervisor.alerts:
            if time.time() - last_sent.get(a['title'], 0) > COOLDOWN:
                send_alerts(a)
                last_sent[a['title']] = time.time()
        
        return {
            "timestamp": str(row.get('timestamp', '')),
            "machine_state": str(row.get('machine_state', 'UNKNOWN')),
            "actual_kw": float(row.get('actual_kw', 0.0)),
            "discharge_pressure_bar": float(row.get('discharge_pressure_bar', 0.0)),
            "money_burn_rate_hr": round(sum([a['cost_impact'] for a in supervisor.alerts]), 2),
            "active_alerts": supervisor.alerts
        }
    
    except Exception as e:
        print(f"❌ Error in get_analysis: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/stats/accumulated")
def get_stats():
    try:
        query = f'''
        from(bucket:"{INFLUX_BUCKET}")
        |> range(start: -24h)
        |> filter(fn:(r) => r._measurement == "compressor_readings")
        |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        '''
        
        result = query_api.query_data_frame(query)
        
        # Handle case where InfluxDB returns a list
        if isinstance(result, list):
            if len(result) == 0:
                return {"total_loss_today": 0.0}
            df = result[0]
        else:
            df = result
        
        if df is None or df.empty:
            return {"total_loss_today": 0.0}
        
        # Rename columns
        df = df.rename(columns={
            "power_kw": "actual_kw",
            "machine_state": "machine_state",
            "pressure": "discharge_pressure_bar",
            "temp_inlet": "inlet_temp_c",
            "_time": "timestamp"
        })
        
        # Sort by timestamp
        df = df.sort_values("timestamp")
        
        # Calculate time differences
        df['diff'] = df['timestamp'].diff().dt.total_seconds().fillna(5.0)
        
        # Initialize accumulator
        total = 0.0
        supervisor = DigitalEnergySupervisor()
        
        # Iterate through each row
        for _, r in df.iterrows():
            row_dict = r.to_dict()
            supervisor.alerts = []
            supervisor.analyze_row(row_dict)
            
            # Accumulate losses
            row_loss = sum([a['cost_impact'] for a in supervisor.alerts])
            total += (row_loss * row_dict.get('diff', 5.0)) / 3600.0
        
        return {"total_loss_today": round(total, 2)}
    
    except Exception as e:
        print(f"❌ Error in get_stats: {e}")
        return {"total_loss_today": 0.0}

@app.get("/live/history")
def get_history():
    try:
        query = f'''
        from(bucket:"{INFLUX_BUCKET}")
        |> range(start:-30m)
        |> filter(fn:(r) => r._measurement == "compressor_readings")
        |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        '''
        
        result = query_api.query_data_frame(query)
        
        # Handle list return
        if isinstance(result, list):
            if len(result) == 0:
                return []
            df = result[0]
        else:
            df = result
        
        if df is None or df.empty:
            return []
        
        # Rename columns
        df = df.rename(columns={
            "power_kw": "actual_kw",
            "pressure": "discharge_pressure_bar"
        })
        
        # Replace NaN values with 0
        df = df.fillna(0)
        
        # Convert to records
        return df.to_dict(orient="records")
    
    except Exception as e:
        print(f"❌ Error in get_history: {e}")
        return []