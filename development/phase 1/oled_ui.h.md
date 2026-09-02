#ifndef OLED_UI_H
#define OLED_UI_H

#include <Arduino.h>
#include <Wire.h>
#include "config.h"

// ============================================================================
//  Phase 1 - Shared Core - OLED ABSTRACTION
//
//  One API for both display families, so node code never mentions U8g2 or
//  Adafruit again:
//      OLED_SH1106   -> 1.3" SH1106  via U8g2            (Node A)
//      OLED_SSD1306  -> 0.96" SSD1306 via Adafruit_GFX   (Node B, Node C)
//
//  5 text rows, 0..4. ASCII only - the bitmap fonts cannot render the emoji
//  the old phase 11 screens tried to draw, which is why those lines came out
//  as garbage boxes.
// ============================================================================

#if defined(OLED_SH1106)
  #include <U8g2lib.h>
  static U8G2_SH1106_128X64_NONAME_F_HW_I2C _oledDev(U8G2_R0, U8X8_PIN_NONE);
#elif defined(OLED_SSD1306)
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>
  static Adafruit_SSD1306 _oledDev(128, 64, &Wire, -1);
#else
  #error "Define OLED_SH1106 or OLED_SSD1306 in the main sketch"
#endif

#define OLED_ROWS      5
#define OLED_ROW_H    12

class OledUI {
public:

  bool begin() {
    Wire.begin(I2C_SDA, I2C_SCL);
#if defined(OLED_SH1106)
    _oledDev.begin();
    _oledDev.setFont(u8g2_font_6x12_tr);      // ~21 chars per line
    _ok = true;
#else
    _ok = _oledDev.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
    if (!_ok) _ok = _oledDev.begin(SSD1306_SWITCHCAPVCC, 0x3D);   // address fallback
    if (_ok) {
      _oledDev.setTextSize(1);
      _oledDev.setTextColor(SSD1306_WHITE);
    }
#endif
    return _ok;
  }

  bool ok() const { return _ok; }

  void clear() {
    if (!_ok) return;
#if defined(OLED_SH1106)
    _oledDev.clearBuffer();
#else
    _oledDev.clearDisplay();
#endif
  }

  void line(uint8_t row, const char *txt) {
    if (!_ok || row >= OLED_ROWS || !txt) return;
#if defined(OLED_SH1106)
    _oledDev.drawStr(0, 10 + row * OLED_ROW_H, txt);   // u8g2 y = baseline
#else
    _oledDev.setCursor(0, row * OLED_ROW_H);
    _oledDev.print(txt);
#endif
  }

  void show() {
    if (!_ok) return;
#if defined(OLED_SH1106)
    _oledDev.sendBuffer();
#else
    _oledDev.display();
#endif
  }

  // Convenience: clear, draw up to two lines, show.
  void banner(const char *l0, const char *l1 = NULL) {
    clear();
    line(0, l0);
    if (l1) line(1, l1);
    show();
  }

private:
  bool _ok = false;
};

#endif
