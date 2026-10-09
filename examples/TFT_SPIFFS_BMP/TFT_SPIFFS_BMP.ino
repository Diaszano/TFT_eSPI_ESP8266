// This sketch draws BMP images pulled from LittleFS onto the TFT. It is an
// an example from this library: https://github.com/Bodmer/TFT_eSPI

// Images in LittleFS must be put in the root folder (top level) to be found
// Use the LittleFS library example to verify LittleFS works!

// The example image used to test this sketch can be found in the sketch
// Data folder, press Ctrl+K to see this folder. Use the IDE "Tools" menu
// option to upload the sketches data folder to the LittleFS

//----------------------------------------------------------------------------------------------------

//====================================================================================
//                                  Libraries
//====================================================================================
// Call up the LittleFS FLASH filing system this is part of the ESP Core
#define FS_NO_GLOBALS
#include <FS.h>
#include <LittleFS.h>

// Call up the TFT library
#include <TFT_eSPI.h>  // Hardware-specific library for ESP8266

// Invoke TFT library
TFT_eSPI tft = TFT_eSPI();

//====================================================================================
//                                    Setup
//====================================================================================
void setup() {
  Serial.begin(115200);

  if (!LittleFS.begin()) {
    Serial.println("LittleFS initialisation failed!");
    while (1) yield();  // Stay here twiddling thumbs waiting
  }
  Serial.println("\r\nLittleFS initialised.");

  // Now initialise the TFT
  tft.begin();
  tft.setRotation(0);  // 0 & 2 Portrait. 1 & 3 landscape
  tft.fillScreen(TFT_BLACK);
}

//====================================================================================
//                                    Loop
//====================================================================================
void loop() {
  int x = random(tft.width() - 128);
  int y = random(tft.height() - 160);

  drawBmp("/parrot.bmp", x, y);

  delay(1000);
}
//====================================================================================

// Bodmer's BMP image rendering function
uint16_t bmpRead16(const uint8_t* data) {
  return uint16_t(data[0]) | (uint16_t(data[1]) << 8);
}

uint32_t bmpRead32(const uint8_t* data) {
  return uint32_t(data[0]) | (uint32_t(data[1]) << 8) | (uint32_t(data[2]) << 16) |
         (uint32_t(data[3]) << 24);
}

void drawBmp(const char* filename, int16_t x, int16_t y) {
  fs::File file = LittleFS.open(filename, "r");
  if (!file) {
    Serial.println("BMP file not found.");
    return;
  }

  uint8_t header[54];
  if (file.read(header, sizeof(header)) != sizeof(header) || bmpRead16(header) != 0x4D42) {
    Serial.println("Invalid BMP header.");
    return;
  }
  const uint32_t declaredSize = bmpRead32(header + 2);
  const uint32_t offset = bmpRead32(header + 10);
  const uint32_t dibSize = bmpRead32(header + 14);
  const uint32_t width = bmpRead32(header + 18);
  const uint32_t height = bmpRead32(header + 22);
  const uint32_t imageSize = bmpRead32(header + 34);
  if (dibSize < 40 || width == 0 || height == 0 || (width & 0x80000000U) ||
      (height & 0x80000000U) || bmpRead16(header + 26) != 1 || bmpRead16(header + 28) != 24 ||
      bmpRead32(header + 30) != 0) {
    Serial.println("BMP requires uncompressed 24-bit bottom-up pixels.");
    return;
  }
  const uint64_t stride = (uint64_t(width) * 3 + 3) & ~uint64_t(3);
  const uint64_t pixelBytes = stride * height;
  const uint64_t pixelEnd = uint64_t(offset) + pixelBytes;
  if (uint64_t(14) + dibSize > offset || pixelEnd > declaredSize || declaredSize > file.size() ||
      (imageSize != 0 && (imageSize < pixelBytes || uint64_t(offset) + imageSize > declaredSize))) {
    Serial.println("Invalid or truncated BMP pixel data.");
    return;
  }

  const int32_t left = x < 0 ? 0 : x;
  const int32_t top = y < 0 ? 0 : y;
  const int64_t imageRight = int64_t(x) + width;
  const int64_t imageBottom = int64_t(y) + height;
  const int32_t right = imageRight < tft.width() ? int32_t(imageRight) : tft.width();
  const int32_t bottom = imageBottom < tft.height() ? int32_t(imageBottom) : tft.height();
  if (left >= right || top >= bottom) return;

  uint8_t bytes[32 * 3];
  uint16_t pixels[32];
  const bool oldSwapBytes = tft.getSwapBytes();
  tft.setSwapBytes(true);
  bool failed = false;
  for (int32_t screenY = top; screenY < bottom && !failed; ++screenY) {
    const uint32_t sourceY = height - 1 - uint32_t(screenY - int32_t(y));
    const uint32_t sourceX = uint32_t(left - int32_t(x));
    const uint64_t rowOffset = uint64_t(offset) + stride * sourceY + uint64_t(sourceX) * 3;
    if (!file.seek(uint32_t(rowOffset))) {
      failed = true;
      break;
    }
    for (int32_t screenX = left; screenX < right; screenX += 32) {
      const uint32_t count = uint32_t(right - screenX) < 32 ? uint32_t(right - screenX) : 32;
      const int bytesToRead = int(count * 3);
      if (file.read(bytes, bytesToRead) != bytesToRead) {
        failed = true;
        break;
      }
      for (uint32_t index = 0; index < count; ++index) {
        const uint8_t* pixel = bytes + index * 3;
        pixels[index] = ((uint16_t(pixel[2]) & 0xF8) << 8) | ((uint16_t(pixel[1]) & 0xFC) << 3) |
                        (pixel[0] >> 3);
      }
      tft.pushImage(screenX, screenY, count, 1, pixels);
    }
  }
  tft.setSwapBytes(oldSwapBytes);
  if (failed) Serial.println("BMP seek or read failed.");
}
