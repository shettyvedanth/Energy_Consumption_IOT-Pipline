#http://52.90.139.142:8086
import json
import time
import os
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 🟢 NEW EC2 IP
INFLUX_URL = "http://52.90.139.142:8086"
INFLUX_TOKEN = "FoM718mNxcQDh9KuySYDomNmvbqEB1S1l7AUHIz-s6aTDGzro0n9vg2xJYtlwhE8hy0SKn7Cdd_RDtUoI00kxw=="
INFLUX_ORG, INFLUX_BUCKET = "cittagent", "hlt200_data"

AWS_ENDPOINT = "a3uf3gzgaja1f2-ats.iot.us-east-1.amazonaws.com"

# 🟢 FIXED: Use absolute paths for certificates
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH = os.path.join(SCRIPT_DIR, "certs", "E1-cert.pem")
KEY_PATH = os.path.join(SCRIPT_DIR, "certs", "E1-private.key")
ROOT_PATH = os.path.join(SCRIPT_DIR, "certs", "root.pem")

# Verify certificates exist
for cert_file, cert_name in [(CERT_PATH, "Certificate"), (KEY_PATH, "Private Key"), (ROOT_PATH, "Root CA")]:
    if not os.path.exists(cert_file):
        print(f"❌ ERROR: {cert_name} not found at: {cert_file}")
        print(f"📂 Current directory: {os.getcwd()}")
        print(f"📂 Script directory: {SCRIPT_DIR}")
        exit(1)
    else:
        print(f"✅ Found {cert_name}: {cert_file}")

# Initialize InfluxDB client
try:
    db_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = db_client.write_api(write_options=SYNCHRONOUS)
    print(f"✅ Connected to InfluxDB at {INFLUX_URL}")
except Exception as e:
    print(f"❌ Failed to connect to InfluxDB: {e}")
    exit(1)

def on_message_received(topic, payload, **kwargs):
    try:
        data = json.loads(payload.decode('utf-8'))
        
        # 🟢 CRITICAL FIX: Write 'machine_state' instead of 'state'
        point = Point("compressor_readings") \
            .tag("machine_id", data.get('machine_id', 'E1')) \
            .field("machine_state", data.get('machine_state', 'OFF')) \
            .field("power_kw", float(data.get('actual_kw', 0.0))) \
            .field("pressure", float(data.get('pressure', 0.0))) \
            .field("temp_inlet", float(data.get('temp_inlet', 25.0))) \
            .field("temp_discharge", float(data.get('temp_discharge', 80.0))) \
            .time(data.get('timestamp'))

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print(f"✅ Saved | State: {data.get('machine_state')} | Power: {data.get('actual_kw')} kW | Pressure: {data.get('pressure')} bar")
    
    except Exception as e:
        print(f"❌ Ingestion Error: {e}")

# Setup AWS IoT connection
print("\n🔌 Setting up AWS IoT connection...")
event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

try:
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=AWS_ENDPOINT,
        cert_filepath=CERT_PATH,
        pri_key_filepath=KEY_PATH,
        ca_filepath=ROOT_PATH,
        client_id="P2_Final_Sync",
        client_bootstrap=client_bootstrap,
        clean_session=False,
        keep_alive_secs=30
    )
    
    print(f"📡 Connecting to AWS IoT at {AWS_ENDPOINT}...")
    connect_future = mqtt_connection.connect()
    connect_future.result(timeout=10)
    print("✅ Connected to AWS IoT Core!")
    
    print("📡 Subscribing to topic: hlt200/live")
    subscribe_future, _ = mqtt_connection.subscribe(
        topic="hlt200/live",
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received
    )
    subscribe_future.result(timeout=10)
    print("✅ Subscribed! Listening for messages...")
    
    # Keep the script running
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Shutting down...")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
    print("✅ Disconnected cleanly")

except Exception as e:
    print(f"\n❌ Connection Error: {e}")
    print("\n🔍 Troubleshooting Tips:")
    print("1. Verify certificates are in the 'certs' folder")
    print("2. Check AWS IoT endpoint is correct")
    print("3. Ensure your AWS Thing 'E1' exists")
    print("4. Verify your AWS policy allows iot:Connect and iot:Subscribe")
    exit(1)



    