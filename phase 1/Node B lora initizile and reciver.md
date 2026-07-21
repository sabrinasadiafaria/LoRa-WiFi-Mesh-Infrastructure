#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

#define LORA_SCK   12
#define LORA_MISO  13
#define LORA_MOSI  11
#define LORA_SS    10
#define LORA_RST   14
#define LORA_DIO0  15

#define LORA_FREQ 433E6

void setup() {

  Serial.begin(115200);

  Wire.begin(8,9);

  display.begin(SSD1306_SWITCHCAPVCC,0x3C);

  SPI.begin(LORA_SCK,LORA_MISO,LORA_MOSI,LORA_SS);

  LoRa.setPins(LORA_SS,LORA_RST,LORA_DIO0);

  if(!LoRa.begin(LORA_FREQ)){

    while(1);

  }

}

void loop() {

  int packetSize = LoRa.parsePacket();

  if(packetSize){

    String msg="";

    while(LoRa.available()){

      msg+=(char)LoRa.read();

    }

    int rssi=LoRa.packetRssi();

    Serial.print("RX: ");
    Serial.print(msg);
    Serial.print(" RSSI: ");
    Serial.println(rssi);

    display.clearDisplay();

    display.setTextColor(SSD1306_WHITE);

    display.setTextSize(1);

    display.setCursor(0,0);
    display.println("NODE B");

    display.setCursor(0,18);
    display.print("RX:");

    display.setCursor(25,18);
    display.println(msg);

    display.setCursor(0,40);
    display.print("RSSI:");

    display.setCursor(40,40);
    display.println(rssi);

    display.display();

  }

}