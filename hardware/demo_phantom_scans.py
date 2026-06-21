"""
demo_phantom_scans.py
Run this on your laptop during demo to simulate hardware scans
even if the ESP32 isn't working. Publishes directly to MQTT.

Usage:
    python demo_phantom_scans.py

Requires: paho-mqtt (pip install paho-mqtt)
"""
import paho.mqtt.client as mqtt
import ssl
import json
import time

MQTT_HOST  = "07415e1eeddc4f73b6eecadca7232cc9.s1.eu.hivemq.cloud"
MQTT_PORT  = 8883
MQTT_USER  = "janya"
MQTT_PASS  = "Janya@11"
MQTT_TOPIC = "resilientchain/rfid/scan"

DEMO_SCANS = [
    {"tag_id": "A1B2C3D4", "package_id": "PK1G001BENMUM", "hub_id": "BEN_H1", "delay_s": 0},
    {"tag_id": "E5F6A7B8", "package_id": "PK2G001HYDVIZ", "hub_id": "HYD_H1", "delay_s": 15},
    {"tag_id": "C9D0E1F2", "package_id": "PK3G001COCCHE", "hub_id": "COC_H1", "delay_s": 30},
]

def run_demo():
    client = mqtt.Client("demo_phantom_001")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    tls = ssl.create_default_context()
    client.tls_set_context(tls)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    print("Demo phantom scans started. Press Ctrl+C to stop.")
    start = time.time()
    sent  = [False] * len(DEMO_SCANS)

    while True:
        elapsed = time.time() - start
        for i, scan in enumerate(DEMO_SCANS):
            if not sent[i] and elapsed >= scan["delay_s"]:
                payload = json.dumps({
                    "tag_id": scan["tag_id"],
                    "package_id": scan["package_id"],
                    "hub_id": scan["hub_id"],
                    "device": "PHANTOM_DEMO",
                    "rssi": -55
                })
                client.publish(MQTT_TOPIC, payload)
                print(f"[{elapsed:.0f}s] Published: {scan['package_id']} at {scan['hub_id']}")
                sent[i] = True
        if all(sent):
            print("All demo scans sent.")
            break
        time.sleep(0.5)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    run_demo()
