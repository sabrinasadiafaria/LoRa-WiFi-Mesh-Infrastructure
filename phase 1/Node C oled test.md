#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// On ESP8266 NodeMCU: D2 = GPIO 4 (SDA), D1 = GPIO 5 (SCL)
#define OLED_SDA 4 // D2
#define OLED_SCL 5 // D1

#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setup() {
  // Using 9600 baud rate to avoid crystal frequency baud mismatch on ESP8266
  Serial.begin(9600);
  delay(2000);

  Serial.println("\n=================================");
  Serial.println("ESP8266 I2C Scanner & OLED Test");
  Serial.println("=================================");

  // Initialize I2C bus
  Wire.begin(OLED_SDA, OLED_SCL);

  // 1. Scan I2C Bus to find OLED Address
  Serial.println("Scanning I2C bus on SDA=D2 (GPIO4), SCL=D1 (GPIO5)...");
  byte count = 0;
  byte foundAddr = 0;

  for (byte address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    byte error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
      foundAddr = address;
      count++;
    }
  }

  if (count == 0) {
    Serial.println("No I2C devices found!");
    Serial.println("Check: VCC -> 3.3V/5V, GND -> GND, SDA -> D2, SCL -> D1");
  } else {
    Serial.print("Found ");
    Serial.print(count);
    Serial.println(" device(s). Initializing OLED...");

    // 2. Initialize OLED at found address
    if (display.begin(SSD1306_SWITCHCAPVCC, foundAddr)) {
      Serial.println("OLED Initialized Successfully!");

      display.clearDisplay();
      display.setTextSize(2);
      display.setTextColor(SSD1306_WHITE);
      display.setCursor(10, 10);
      display.println("NODE C");

      display.setTextSize(1);
      display.setCursor(10, 35);
      display.println("OLED IS WORKING!");

      display.setCursor(10, 50);
      display.print("I2C Addr: 0x");
      display.println(foundAddr, HEX);

      display.display();
    } else {
      Serial.println("OLED display.begin() failed!");
    }
  }
}

void loop() {
  static int counter = 0;
  Serial.print("ESP8266 Active... Counter: ");
  Serial.println(counter++);
  delay(1000);
}
