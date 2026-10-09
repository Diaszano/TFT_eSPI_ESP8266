#include <Arduino.h>
#include <FS.h>
#include <TFT_eSPI.h>
#include <cassert>
#include <cstring>
#include <initializer_list>
#include <new>

static const char* fontPath = "/plan01-regression.vlw";
static const char* fontName = "plan01-regression";
static bool writeFont() {
  if (SPIFFS.exists(fontPath)) return false;
  fs::File file = SPIFFS.open(fontPath, "w");
  if (!file) return false;
  const uint32_t words[] = {1, 11, 4, 0, 2, 0, 65, 2, 2, 3, 2, 0, 0};
  for (uint32_t word : words) {
    const uint8_t bytes[] = {uint8_t(word >> 24), uint8_t(word >> 16), uint8_t(word >> 8),
                             uint8_t(word)};
    if (file.write(bytes, sizeof(bytes)) != sizeof(bytes)) {
      file.close();
      SPIFFS.remove(fontPath);
      return false;
    }
  }
  const uint8_t pixels[] = {255, 255, 255, 255};
  bool result = file.write(pixels, sizeof(pixels)) == sizeof(pixels);
  file.close();
  if (!result) SPIFFS.remove(fontPath);
  return result;
}
static void failFont(TFT_eSPI& display) {
  display.loadFont(fontName);
  assert(display.fontLoaded);
  display.fontFile.close();
}
static void checkFontState(TFT_eSPI& display) {
  assert(!display.fontLoaded && !display.gUnicode && !display.gWidth && !display.gxAdvance);
  assert(!display.fontFile);
}
void setup() {
  Serial.begin(115200);
  alignas(TFT_eSPI) unsigned char storage[sizeof(TFT_eSPI)];
  std::memset(storage, 0xA5, sizeof(storage));
  TFT_eSPI* display = new (storage) TFT_eSPI;
  assert(display->fontHeight(1) == 8 && display->textWidth("A", 1) == 6);
  display->init();
  display->fillScreen(TFT_BLACK);
  assert(display->drawString("A", 0, 0, 1) == 6);
  TFT_eSPI* dynamic = new (std::nothrow) TFT_eSPI;
  assert(dynamic);
  assert(dynamic->fontHeight(1) == 8 && dynamic->textWidth("A", 1) == 6);
  dynamic->init();
  assert(dynamic->drawString("B", 10, 0, 1) == 6);
  delete dynamic;
  uint16_t pixels[17];
  for (unsigned i = 0; i < 17; ++i)
    pixels[i] = i % 3 == 0 ? TFT_RED : i % 3 == 1 ? TFT_GREEN : TFT_BLUE;
  display->setSwapBytes(true);
  for (int length : {1, 2, 3, 15, 16, 17}) display->pushImage(0, 10 + length, length, 1, pixels);
  TFT_eSprite sprite(display);
  sprite.setColorDepth(1);
  assert(sprite.createSprite(16, 8));
  for (uint8_t rotation = 0; rotation < 4; ++rotation) {
    sprite.setRotation(rotation);
    for (int y = 0; y < sprite.height(); ++y)
      for (int x = 0; x < sprite.width(); ++x) sprite.drawPixel(x, y, ((x + 3 * y) % 5) == 0);
    for (int y = 0; y < sprite.height(); ++y)
      for (int x = 0; x < sprite.width(); ++x) {
        bool expected = ((x + 3 * y) % 5) == 0;
        assert(sprite.readPixelValue(x, y) == expected);
        assert(sprite.readPixel(x, y) == (expected ? TFT_WHITE : TFT_BLACK));
      }
    sprite.pushSprite(40 + rotation * 20, 40);
  }
  sprite.deleteSprite();
  if (!SPIFFS.setConfig(SPIFFSConfig(false)) || !SPIFFS.begin() || !writeFont()) {
    Serial.println("FAIL firmware-memory: filesystem unavailable or fixture path already exists");
    display->~TFT_eSPI();
    return;
  }
  failFont(*display);
  assert(display->drawString("AA", 0, 60, 1) == 0);
  checkFontState(*display);
  failFont(*display);
  display->showFont(0);
  checkFontState(*display);
  failFont(*display);
  assert(display->write(uint8_t('A')) == 1);
  checkFontState(*display);
  for (bool created : {false, true}) {
    if (created) assert(sprite.createSprite(16, 8));
    failFont(sprite);
    char text[] = "AA";
    sprite.printToSprite(text, 2);
    checkFontState(sprite);
    assert((sprite.getPointer() != nullptr) == created);
    failFont(sprite);
    assert(sprite.printToSprite(0, 0, uint16_t(0)) == 0);
    checkFontState(sprite);
    assert((sprite.getPointer() != nullptr) == created);
    sprite.deleteSprite();
  }
  display->loadFont(fontName);
  assert(display->fontLoaded);
  display->drawString("AA", 0, 80, 1);
  assert(display->fontLoaded);
  display->unloadFont();
  assert(SPIFFS.remove(fontPath));
  display->drawString("PASS firmware-memory", 0, 100, 1);
  display->~TFT_eSPI();
  Serial.println("PASS firmware-memory");
}
void loop() {
  delay(1000);
}
