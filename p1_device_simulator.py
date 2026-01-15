import time
import json
import random
import numpy as np
from datetime import datetime
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder

# =======================================================
# ⚙️ CONFIGURATION
# =======================================================
# This is the endpoint you found in the settings
ENDPOINT = "a3uf3gzgaja1f2-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "E1"            # This must match your AWS Thing Name
TOPIC = "hlt200/live"       # The channel we are sending data to

# =======================================================
# 🔌 CONNECTION SETUP (The "Handshake")
# =======================================================
event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

# This tells Python where to find your "Security Badges"
mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath="certs/E1-cert.pem",
    pri_key_filepath="certs/E1-private.key",
    ca_filepath="certs/root.pem",
    client_id=CLIENT_ID,
    client_bootstrap=client_bootstrap,
    clean_session=False,
    keep_alive_secs=6
)

print(f"📡 Connecting {CLIENT_ID} to AWS IoT Core...")
connect_future = mqtt_connection.connect()
connect_future.result()
print("✅ Connected! Starting Data Stream...")

# =======================================================
# 🏭 PHYSICS SIMULATION (The "Brain")
# =======================================================
try:
    while True:
        # 1. GENERATE FAKE SENSOR DATA
        # We simulate a busy factory day (8 AM - 6 PM)
        hour = datetime.now().hour
        is_busy = 8 <= hour < 18 
        
        # Decide if machine is WORKING (Load) or IDLE (Unload)
        if is_busy and random.random() > 0.1:
            state = "LOAD"
            pressure = 7.0 + np.random.normal(0, 0.1)     # Pressure drops when working
            current = 22.0 + np.random.normal(0, 0.5)     # Current goes up
            pf = 0.85
        else:
            state = "UNLOAD"
            pressure = 7.2 + np.random.normal(0, 0.05)    # Pressure rises when idle
            current = 7.0 + np.random.normal(0, 0.2)      # Current drops
            pf = 0.60

        # Calculate Power (Physics Formula: P = V * I * PF * 1.732)
        voltage = 415 + np.random.normal(0, 2)
        power_kw = (1.732 * voltage * current * pf) / 1000
        
        # 2. PACK IT INTO A MESSAGE (JSON)
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "machine_id": CLIENT_ID,
            "machine_state": state,
            "pressure": round(pressure, 2),
            "actual_kw": round(power_kw, 2),
            "current": round(current, 1),
            "temp_discharge": round(85.0 + np.random.normal(0, 2) if state=="LOAD" else 60.0, 1),
            "temp_inlet": round(25.0 + np.random.normal(0, 0.5), 1),
            "power_factor": round(pf, 2)
        }

        # 3. SEND IT TO THE CLOUD
        mqtt_connection.publish(
            topic=TOPIC,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        
        print(f"📤 Sent: {state} | {payload['actual_kw']} kW | {payload['pressure']} bar")
        time.sleep(5) # Wait 5 seconds before next reading

except KeyboardInterrupt:
    print("\n🛑 Disconnecting...")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
    print("Disconnected.")