// Node A GPS Raw NMEA Debugger Sketch
// Use this to check raw data coming from your GPS module over Serial2 (GPIO 16 RX, GPIO 17 TX)

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=================================");
  Serial.println("ESP32 GPS Hardware Serial2 Test");
  Serial.println("RX2 Pin = GPIO 16 (Connect to GPS TX)");
  Serial.println("TX2 Pin = GPIO 17 (Connect to GPS RX)");
  Serial.println("=================================\n");

  // Try standard 9600 baud first for Neo-6M / GT-U7
  Serial2.begin(9600, SERIAL_8N1, 16, 17);
}

void loop() {
  // Pass-through raw characters from GPS module to Serial Monitor
  while (Serial2.available() > 0) {
    char c = Serial2.read();
    Serial.print(c);
  }
}
