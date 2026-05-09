import paho.mqtt.client as mqtt

broker = "81611f39b7bb429d85be2c8c36ed6dcc.s1.eu.hivemq.cloud"
port = 8883
topic = "logistics/rfid/scan"

username = "janya"
password = "Janya@123"

def on_connect(client, userdata, flags, rc):
    print("Connected to HiveMQ:", rc)
    client.subscribe(topic)

def on_message(client, userdata, msg):
    data = msg.payload.decode()
    print("RFID scanned:", data)

client = mqtt.Client()
client.username_pw_set(username, password)
client.tls_set()

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, port)
client.loop_forever()