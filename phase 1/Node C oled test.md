#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// On ESP8266 NodeMCU: SDA is D2 (GPIO 4), SCL is D1 (GPIO 5)
#define OLED_SDA 4 // D2
#define OLED_SCL 5 // D1

#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C // Try 0x3D if 0x3C doesn't work

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- ESP8266 OLED Test ---");

  // Initialize I2C with explicit SDA (D2) and SCL (D1) pins
  Wire.begin(OLED_SDA, OLED_SCL);

  // Try initializing display at address 0x3C
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println("OLED initialization failed at 0x3C! Retrying at 0x3D...");
    
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      Serial.println("OLED allocation failed at 0x3D as well. Check VCC/GND/SDA/SCL wiring!");
      while (true) {
        delay(500);
      }
    }
  }

  Serial.println("OLED Initialized Successfully!");

  display.clearDisplay();

  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(15, 5);
  display.println("NODE C");

  display.setTextSize(1);
  display.setCursor(15, 30);
  display.println("ESP8266 OLED");

  display.setCursor(15, 45);
  display.println("Status : WORKING");

  display.display();
}

void loop() {
  static int count = 0;
  Serial.print("OLED active... Uptime count: ");
  Serial.println(count++);
  delay(1000);
}
