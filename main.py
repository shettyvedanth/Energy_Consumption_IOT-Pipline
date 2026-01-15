import subprocess
import time
import sys
import os

def run_service(command, name):
    """Starts a service and keeps it running."""
    print(f"🚀 Starting {name}...")
    # Using Popen to run in background
    return subprocess.Popen(command)

if __name__ == "__main__":
    # UPDATED: Paths fixed to match your 'AWS' folder structure
    services = [
        {"name": "Simulator", "cmd": [sys.executable, "p1_device_simulator.py"]},
        {"name": "Ingestion", "cmd": [sys.executable, "p2_device_ingestion.py"]},
        {"name": "API", "cmd": ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]},
        {"name": "Dashboard", "cmd": ["streamlit", "run", "dashboard.py", "--server.port", "8501"]}
    ]

    processes = []

    try:
        # Launch all services
        for service in services:
            p = run_service(service["cmd"], service["name"])
            processes.append(p)
            time.sleep(2)  # Short delay to allow startup

        print("\n✅ All HLT200 services are running. Press Ctrl+C to stop.\n")
        
        # Keep main thread alive while child processes run
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down all services...")
        for p in processes:
            p.terminate()
        print("✅ Clean shutdown complete.")
