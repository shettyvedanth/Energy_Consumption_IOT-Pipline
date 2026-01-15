import time
from influxdb_client import InfluxDBClient

# --- CLOUD CONFIG ---
INFLUX_URL = "http://52.90.139.142:8086"
INFLUX_TOKEN = "FoM718mNxcQDh9KuySYDomNmvbqEB1S1l7AUHIz-s6aTDGzro0n9vg2xJYtlwhE8hy0SKn7Cdd_RDtUoI00kxw=="
INFLUX_ORG, INFLUX_BUCKET = "cittagent", "hlt200_data"

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()

class DigitalEnergySupervisor:
    def __init__(self):
        self.alerts = []
        self.thresholds = {"max_pressure": 7.0, "design_temp": 25.0, "idle_power": 4.0}

    def analyze_row(self, row):
        self.alerts = []
        # 🟢 FIXED: These keys now match what ingestion writes
        pwr = float(row.get('actual_kw', 0.0))
        prs = float(row.get('discharge_pressure_bar', 0.0))
        state = str(row.get('machine_state', 'UNKNOWN'))
        temp_in = float(row.get('inlet_temp_c', 25.0))
        
        # Over-Pressure Detection
        if prs > self.thresholds["max_pressure"]:
            waste = (prs - self.thresholds["max_pressure"]) * 0.5 * pwr
            self.alerts.append({
                "title": "System Over-Pressurization",
                "cost_impact": round(waste * 12.0, 2),
                "reason": f"Pressure is {prs} bar (Target: 7.0 bar)",
                "action": "Lower pressure setpoint to 7.0 bar."
            })

        # Hot Inlet Air Detection
        if temp_in > self.thresholds["design_temp"]:
            waste = pwr * 0.01 * (temp_in - self.thresholds["design_temp"])
            self.alerts.append({
                "title": "Hot Inlet Air Detected",
                "cost_impact": round(waste * 12.0, 2),
                "reason": f"Inlet is {temp_in}°C (Design: 25°C)",
                "action": "Relocate intake to a cooler zone."
            })

        # Idle Running Waste Detection
        if state == "UNLOAD" and pwr > self.thresholds["idle_power"]:
            self.alerts.append({
                "title": "Idle Running Waste",
                "cost_impact": round(pwr * 12.0, 2),
                "reason": f"Machine UNLOADED consuming {pwr} kW",
                "action": "Install an Automatic Start/Stop timer."
            })

# 🟢 Standalone monitoring loop (if you run this directly)
if __name__ == "__main__":
    print("🧠 Digital Supervisor Online... Connecting to 54.144.244.233")
    sup = DigitalEnergySupervisor()
    
    while True:
        try:
            # Query the latest data from EC2
            query = f'from(bucket:"{INFLUX_BUCKET}") |> range(start: -5m) |> filter(fn:(r)=>r._measurement=="compressor_readings") |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value") |> sort(columns:["_time"], desc:true) |> limit(n:1)'
            df = query_api.query_data_frame(query)
            
            if not df.empty:
                # 🟢 FIXED: Standardize field names for the Physics Engine
                df = df.rename(columns={
                    "power_kw": "actual_kw", 
                    "pressure": "discharge_pressure_bar", 
                    "machine_state": "machine_state",  # Now consistent
                    "temp_inlet": "inlet_temp_c"
                })
                row = df.iloc[0]
                sup.analyze_row(row)
                
                print(f"--- ⏱️ Analysis at {row['_time']} ---")
                print(f"State: {row['machine_state']} | Power: {row['actual_kw']} kW | Pressure: {row['discharge_pressure_bar']} bar")
                
                if sup.alerts:
                    for a in sup.alerts:
                        print(f"  🔴 {a['title']}: ₹{a['cost_impact']}/hr")
                else:
                    print("  ✅ System Optimized.")
            else:
                print("⏳ Waiting for data to arrive in EC2...")
            
            time.sleep(5)
        except Exception as e:
            print(f"❌ DB Error: {e}")
            time.sleep(5)