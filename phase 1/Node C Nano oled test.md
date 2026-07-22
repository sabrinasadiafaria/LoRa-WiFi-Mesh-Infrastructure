#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C // Default I2C address for 0.96" OLED

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setup() {
  Serial.begin(115200);
  while (!Serial);

  Serial.println(F("Arduino Nano OLED Test"));

  // Hardware I2C on Arduino Nano: SDA = A4, SCL = A5
  Wire.begin();

  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("OLED initialization failed! Check A4(SDA) and A5(SCL) wiring."));
    while (true);
  }

  Serial.println(F("OLED Working!"));

  display.clearDisplay();

  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(15, 5);
  display.println(F("NODE C"));

  display.setTextSize(1);
  display.setCursor(10, 30);
  display.println(F("Arduino Nano OLED"));

  display.setCursor(15, 48);
  display.println(F("Status : OK"));

  display.display();
}

void loop() {
  static int counter = 0;
  Serial.print(F("Nano Uptime: "));
  Serial.println(counter++);
  delay(1000);
}
