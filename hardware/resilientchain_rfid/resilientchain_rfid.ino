/*
 * ResilientChain AI — ESP32 RFID Scanner Firmware
 * Version: 2.0.0
 * Hardware: ESP32-WROOM-32 + RC522 RFID Reader
 * Protocol: MQTT over TLS (HiveMQ Cloud)
 * Package format: PK{n}G{group}{origin}{dest}
 *
 * Wiring:
 *   RC522 SDA  → GPIO 5
 *   RC522 SCK  → GPIO 18
 *   RC522 MOSI → GPIO 23
 *   RC522 MISO → GPIO 19
 *   RC522 RST  → GPIO 4
 *   RC522 VCC  → 3.3V (NOT 5V!)
 *   RC522 GND  → GND
 */

#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ═══════════════════════════════════════════════════════════════
// CONFIG SECTION — FILL IN YOUR VALUES
// ═══════════════════════════════════════════════════════════════

// WiFi credentials
const char* WIFI_SSID     = "Gupta g";
const char* WIFI_PASSWORD = "jitendragupta";

// HiveMQ Cloud broker
const char* MQTT_HOST      = "07415e1eeddc4f73b6eecadca7232cc9.s1.eu.hivemq.cloud";
const int   MQTT_PORT      = 8883;
const char* MQTT_USER      = "janya";
const char* MQTT_PASS      = "Janya@11";
const char* MQTT_TOPIC    = "resilientchain/rfid/scan";
const char* MQTT_CLIENT_ID = "ESP32_RC_RFID_001";

// Hub assignment for this physical device
// Valid: BEN_H1, BEN_H4, HYD_H1, MUM_H1, VIZ_H1, COC_H1
const char* DEVICE_HUB_ID = "BEN_H1";

// GPIO pin assignments
#define RC522_SS_PIN   5
#define RC522_RST_PIN  4
#define LED_GREEN      2
#define LED_RED        15
#define BUZZER_PIN     13

// Deduplication window (30 seconds — matches backend cooldown)
#define SCAN_COOLDOWN_MS 30000UL

// ═══════════════════════════════════════════════════════════════
// HiveMQ Cloud Root CA Certificate (ISRG Root X1, valid until 2038)
// ═══════════════════════════════════════════════════════════════
const char* HIVEMQ_CA_CERT = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)EOF";

// ═══════════════════════════════════════════════════════════════
// PACKAGE ID MAPPING TABLE
// Maps RFID card UIDs to package IDs for the demo.
// After Phase 5, tap each card and copy its UID from Serial Monitor.
// ═══════════════════════════════════════════════════════════════
struct CardMapping {
  const char* uid;
  const char* package_id;
};

const CardMapping CARD_MAP[] = {
  { "A1B2C3D4",   "PK1G001BENMUM" },
  { "E5F6A7B8",   "PK2G001HYDVIZ" },
  { "C9D0E1F2",   "PK3G001COCCHE" },
  { "12345678",   "PK4G002MUMBEN" },
  { "AABBCCDD",   "PK5G002VIZBEN" },
};
const int CARD_MAP_SIZE = sizeof(CARD_MAP) / sizeof(CARD_MAP[0]);

// ═══════════════════════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════════════════════
MFRC522 rfid(RC522_SS_PIN, RC522_RST_PIN);
WiFiClientSecure wifiClient;
PubSubClient mqtt(wifiClient);

struct LastScan {
  String uid;
  unsigned long timestamp;
};
LastScan lastScan = {"", 0};

bool mqttConnected = false;
int scanCount = 0;

// ─── UID bytes → hex string ───────────────────────────────────
String uidToHex(byte* uid, byte len) {
  String result = "";
  for (byte i = 0; i < len; i++) {
    if (uid[i] < 0x10) result += "0";
    result += String(uid[i], HEX);
  }
  result.toUpperCase();
  return result;
}

// ─── Look up package ID from UID ──────────────────────────────
String getPackageId(const String& uid) {
  for (int i = 0; i < CARD_MAP_SIZE; i++) {
    if (uid.equalsIgnoreCase(CARD_MAP[i].uid)) {
      return String(CARD_MAP[i].package_id);
    }
  }
  // Auto-generate for unknown cards
  const char* cities[] = {"BEN","HYD","MUM","VIZ","COC","CHE"};
  uint32_t hash = 0;
  for (unsigned int c = 0; c < uid.length(); c++) hash = hash * 31 + uid[c];
  int pkgNum   = (hash % 9) + 1;
  String grpNum = String((hash / 9) % 99 + 1);
  while (grpNum.length() < 3) grpNum = "0" + grpNum;
  String origin = cities[hash % 6];
  String dest   = cities[(hash / 6 + 1) % 6];
  if (dest == origin) dest = cities[(hash / 36 + 2) % 6];
  return "PK" + String(pkgNum) + "G" + grpNum + origin + dest;
}

// ─── Feedback: LEDs + Buzzer ──────────────────────────────────
void feedbackSuccess() {
  digitalWrite(LED_GREEN, HIGH);
  if (BUZZER_PIN >= 0) {
    tone(BUZZER_PIN, 1200, 100);
    delay(120);
    tone(BUZZER_PIN, 1600, 100);
  }
  delay(400);
  digitalWrite(LED_GREEN, LOW);
}

void feedbackDuplicate() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_RED, HIGH);
    delay(80);
    digitalWrite(LED_RED, LOW);
    delay(80);
  }
}

void feedbackError() {
  digitalWrite(LED_RED, HIGH);
  if (BUZZER_PIN >= 0) tone(BUZZER_PIN, 400, 500);
  delay(600);
  digitalWrite(LED_RED, LOW);
}

// ─── WiFi connect ─────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("\n[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    Serial.print(".");
    delay(500);
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[WiFi] RSSI: %d dBm\n", WiFi.RSSI());
  } else {
    Serial.println("\n[WiFi] FAILED — rebooting in 5s");
    delay(5000);
    ESP.restart();
  }
}

// ─── MQTT connect ─────────────────────────────────────────────
bool connectMQTT() {
  if (mqtt.connected()) return true;

  Serial.printf("[MQTT] Connecting to %s:%d ...\n", MQTT_HOST, MQTT_PORT);

  wifiClient.setCACert(HIVEMQ_CA_CERT);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  mqtt.setKeepAlive(60);

  String clientId = String(MQTT_CLIENT_ID) + "_" + String(random(0xffff), HEX);

  if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)) {
    Serial.println("[MQTT] Connected to HiveMQ Cloud");
    mqttConnected = true;
    String presence = "{\"device\":\"" + clientId + "\",\"hub\":\"" + DEVICE_HUB_ID + "\",\"status\":\"online\"}";
    mqtt.publish("resilientchain/device/presence", presence.c_str(), true);
    return true;
  } else {
    Serial.printf("[MQTT] FAILED — state: %d\n", mqtt.state());
    mqttConnected = false;
    return false;
  }
}

// ─── Publish RFID scan ────────────────────────────────────────
bool publishScan(const String& uid, const String& packageId) {
  if (!connectMQTT()) {
    Serial.println("[MQTT] Cannot publish — not connected");
    return false;
  }

  StaticJsonDocument<256> doc;
  doc["tag_id"]     = uid;
  doc["package_id"] = packageId;
  doc["hub_id"]     = DEVICE_HUB_ID;
  doc["scan_count"] = ++scanCount;
  doc["device"]     = MQTT_CLIENT_ID;
  doc["rssi"]       = WiFi.RSSI();

  char payload[256];
  serializeJson(doc, payload);

  Serial.printf("[RFID] Publishing: %s\n", payload);

  bool ok = mqtt.publish(MQTT_TOPIC, payload, false);
  if (ok) {
    Serial.printf("[MQTT] Published to %s\n", MQTT_TOPIC);
  } else {
    Serial.printf("[MQTT] Publish FAILED\n");
  }
  return ok;
}

// ─── Setup ────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED,   OUTPUT);
  if (BUZZER_PIN >= 0) pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED,   LOW);

  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_GREEN, HIGH); digitalWrite(LED_RED, HIGH);
    delay(150);
    digitalWrite(LED_GREEN, LOW);  digitalWrite(LED_RED, LOW);
    delay(150);
  }

  Serial.println("\n=== ResilientChain AI — ESP32 RFID v2.0 ===");
  Serial.printf("Device Hub: %s\n", DEVICE_HUB_ID);

  connectWiFi();

  SPI.begin();
  rfid.PCD_Init();
  delay(100);

  byte version = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.printf("[RC522] Firmware version: 0x%02X\n", version);
  if (version == 0x00 || version == 0xFF) {
    Serial.println("[RC522] ERROR — Reader not detected!");
    feedbackError();
  } else {
    Serial.printf("[RC522] Ready (version 0x%02X)\n", version);
    feedbackSuccess();
  }

  connectMQTT();

  Serial.println("\n[READY] Tap an RFID card to scan...\n");
}

// ─── Main loop ────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Lost — reconnecting...");
    connectWiFi();
  }
  if (!mqtt.connected()) {
    delay(1000);
    connectMQTT();
  }
  mqtt.loop();

  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial())   return;

  String uid = uidToHex(rfid.uid.uidByte, rfid.uid.size);
  Serial.printf("\n[RFID] Card detected — UID: %s\n", uid.c_str());

  // Deduplication
  unsigned long now = millis();
  if (uid == lastScan.uid && (now - lastScan.timestamp) < SCAN_COOLDOWN_MS) {
    unsigned long remaining = (SCAN_COOLDOWN_MS - (now - lastScan.timestamp)) / 1000;
    Serial.printf("[RFID] Duplicate — cooldown %lus remaining\n", remaining);
    feedbackDuplicate();
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  String packageId = getPackageId(uid);
  Serial.printf("[RFID] Package ID: %s\n", packageId.c_str());
  Serial.printf("[RFID] Hub: %s\n", DEVICE_HUB_ID);

  bool published = publishScan(uid, packageId);

  if (published) {
    feedbackSuccess();
    lastScan.uid       = uid;
    lastScan.timestamp = now;
    Serial.printf("[RFID] Scan logged: %s -> %s\n", uid.c_str(), packageId.c_str());
  } else {
    feedbackError();
    Serial.println("[RFID] Failed to publish scan");
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(200);
}
