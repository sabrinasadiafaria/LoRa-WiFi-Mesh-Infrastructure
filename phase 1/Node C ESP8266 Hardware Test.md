// ESP8266 Basic Hardware & Serial Test

void setup() {
  // Test both built-in LED and Serial
  pinMode(LED_BUILTIN, OUTPUT);
  
  // Set Serial to 115200
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n=================================");
  Serial.println("ESP8266 HARDWARE TEST WORKING!");
  Serial.println("=================================");
}

void loop() {
  static int counter = 0;
  
  digitalWrite(LED_BUILTIN, LOW);  // Turn LED ON (Active LOW on ESP8266)
  delay(500);
  digitalWrite(LED_BUILTIN, HIGH); // Turn LED OFF
  delay(500);

  Serial.print("ESP8266 Alive! Counter: ");
  Serial.println(counter++);
}
