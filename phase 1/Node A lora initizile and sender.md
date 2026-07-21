#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <U8g2lib.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE);

#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26

#define LORA_FREQ 433E6

int counter = 0;

void setup() {

  Serial.begin(115200);

  Wire.begin(21,22);

  display.begin();

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {

    while (1);

  }

}

void loop() {

  String msg = "Hello #" + String(counter);

  LoRa.beginPacket();
  LoRa.print(msg);
  LoRa.endPacket();

  Serial.println("TX -> " + msg);

  display.clearBuffer();

  display.setFont(u8g2_font_ncenB08_tr);

  display.drawStr(10,15,"NODE A");
  display.drawStr(10,35,"Sending");

  display.setCursor(10,55);
  display.print(msg);

  display.sendBuffer();

  counter++;

  delay(2000);

}