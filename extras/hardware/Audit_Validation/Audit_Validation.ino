#include <ESP8266WiFi.h>
#include <TFT_eSPI.h>
#if __has_include("secrets.h")
#include "secrets.h"
#else
#define WIFI_SSID     ""
#define WIFI_PASSWORD ""
#endif

TFT_eSPI tft;
TFT_eSprite sprite(&tft);
uint32_t sample = 0;

void setup() {
  Serial.begin(115200);
  tft.init();
  tft.setTextFont(1);
  tft.fillScreen(TFT_BLACK);
  sprite.setColorDepth(16);
  if (WIFI_SSID[0]) WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("sample,draw_us,heap_before,heap_allocated,heap_after,max_block,wifi");
}

void loop() {
  const uint32_t before = ESP.getFreeHeap();
  if (!sprite.createSprite(32, 32)) {
    Serial.println("FAIL allocation");
    delay(1000);
    return;
  }
  const uint32_t allocated = ESP.getFreeHeap();
  const uint32_t start = micros();
  for (uint16_t frame = 0; frame < 100; ++frame) {
    sprite.fillSprite(frame & 1 ? TFT_RED : TFT_BLUE);
    sprite.drawRect(0, 0, 32, 32, TFT_WHITE);
    sprite.pushSprite((frame * 3) % (tft.width() - 31), (frame * 5) % (tft.height() - 31));
    yield();
  }
  const uint32_t elapsed = micros() - start;
  sprite.deleteSprite();
  Serial.printf("%lu,%lu,%lu,%lu,%lu,%lu,%d\n", static_cast<unsigned long>(sample++),
                static_cast<unsigned long>(elapsed), static_cast<unsigned long>(before),
                static_cast<unsigned long>(allocated),
                static_cast<unsigned long>(ESP.getFreeHeap()),
                static_cast<unsigned long>(ESP.getMaxFreeBlockSize()), WiFi.status());
  delay(1000);
}
