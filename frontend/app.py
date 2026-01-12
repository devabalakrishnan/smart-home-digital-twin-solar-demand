#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

// WiFi & HiveMQ Credentials
const char* ssid = "Airtel_deva_8753";
const char* password = "Air@86193";
const char* mqtt_user = "hivemq.client.1766925863216";
const char* mqtt_pass = "6<9SwUoy#0D8*dl:CNir";

// Pin Mapping for all 7 appliances
const int PINS[] = {2, 4, 5, 18, 19, 21, 22};
const char* APPS[] = {"fridge", "heater", "fans", "lights", "tv", "microwave", "washing"};

WiFiClientSecure espClient;
PubSubClient client(espClient);

void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) message += (char)payload[i];
  String top = String(topic);

  Serial.print("Incoming -> "); Serial.print(top); Serial.print(": "); Serial.println(message);

  for(int i = 0; i < 7; i++) {
    if(top.indexOf(APPS[i]) != -1) {
      digitalWrite(PINS[i], (message == "ON") ? HIGH : LOW);
      Serial.print("ACTION: "); Serial.print(APPS[i]); Serial.println(" updated.");
    }
  }
}

void setup() {
  Serial.begin(115200);
  for(int p : PINS) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  
  espClient.setInsecure();
  client.setServer("cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud", 8883);
  client.setCallback(callback);
  
  // INCREASE BUFFER to handle multiple messages in one loop
  client.setBufferSize(1024); 
}

void loop() {
  if (!client.connected()) {
    if (client.connect("ESP32_Final", mqtt_user, mqtt_pass)) {
      client.subscribe("home/appliances/+/command");
    }
  }
  client.loop();
}
