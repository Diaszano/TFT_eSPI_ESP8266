// Compile-only probe of the primitives a small widget UI uses on ST7789 240x240.
#include <TFT_eSPI.h>

TFT_eSPI tft;
static const uint16_t icon[16 * 16] PROGMEM = {TFT_RED, TFT_GREEN, TFT_BLUE};
static uint32_t frame = 0;

void setup() {
  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLACK);
  tft.setSwapBytes(true);
}

void loop() {
  tft.fillRect(10, 10, 100, 40, frame & 1 ? TFT_NAVY : TFT_BLACK);
  tft.drawRect(8, 8, 104, 44, TFT_WHITE);
  tft.drawFastHLine(0, 120, 240, TFT_DARKGREY);
  tft.drawFastVLine(120, 60, 60, TFT_DARKGREY);
  tft.drawPixel(frame % 240, 200, TFT_YELLOW);
  tft.pushImage(200, 10, 16, 16, icon);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextPadding(tft.textWidth("0000", 4));
  tft.drawNumber(frame, 10, 130, 4);
  tft.drawString("Temperatura", 10, 170, 2);
  tft.drawString("ok", 10, 190, 1);
  tft.drawString(String(frame), 120, 190, 2);
  ++frame;
  yield();
}
