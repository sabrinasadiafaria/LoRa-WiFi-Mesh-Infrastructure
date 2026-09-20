# Node A - OLED Test Code

Copy the code below into your Arduino IDE and upload it to Node A (ESP32) to test the OLED display.

```cpp
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1

// Adjust the I2C pins if your ESP32 board uses different ones (e.g., SDA 4, SCL 15 for Heltec)
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setup() {
  Serial.begin(115200);
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
    Serial.println(F("SSD1306 allocation failed"));
    for(;;); // Don't proceed, loop forever
  }
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 10);
  
  display.println("Node A - OLED Test");
  display.display();
  Serial.println("OLED Initialized.");
}

void loop() {
  // Test animation or counter
  static int counter = 0;
  display.clearDisplay();
  display.setCursor(0, 10);
  display.println("Node A - Active");
  display.print("Counter: ");
  display.println(counter);
  display.display();
  
  counter++;
  delay(1000);
}
```
