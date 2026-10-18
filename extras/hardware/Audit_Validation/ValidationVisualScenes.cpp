#include "ValidationVisualScenes.h"

namespace {
const char* const kNames[VALIDATION_VISUAL_CASE_COUNT] = {"edge_clipping", "image_source_clipping",
                                                          "sprite_crop_and_rotation",
                                                          "text_opaque_transparent_edges"};

bool draw_sprite_rotations(TFT_eSPI& tft) {
  TFT_eSprite sprite(&tft);
  if (!sprite.createSprite(64, 64)) return false;

  sprite.fillSprite(TFT_MAGENTA);
  sprite.fillRect(3, 3, 25, 25, TFT_RED);
  sprite.fillRect(36, 3, 25, 25, TFT_GREEN);
  sprite.fillRect(3, 36, 25, 25, TFT_BLUE);
  sprite.fillRect(36, 36, 25, 25, TFT_YELLOW);
  sprite.drawRect(0, 0, 64, 64, TFT_WHITE);
  sprite.drawFastVLine(32, 8, 17, TFT_WHITE);
  sprite.drawLine(24, 16, 32, 8, TFT_WHITE);
  sprite.drawLine(40, 16, 32, 8, TFT_WHITE);
  sprite.drawFastHLine(29, 32, 7, TFT_WHITE);
  sprite.drawFastVLine(32, 29, 7, TFT_WHITE);
  sprite.fillRect(30, 30, 5, 5, TFT_CYAN);
  sprite.setPivot(32, 32);

  const int16_t centers[] = {35, 120, 205};
  const int16_t angles[] = {0, 45, 90};
  for (uint8_t i = 0; i < 3; ++i) {
    tft.setPivot(centers[i], 71);
    if (!sprite.pushRotated(angles[i], TFT_MAGENTA)) {
      tft.setPivot(120, 120);
      return false;
    }
    tft.setTextFont(1);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawString(i == 0 ? "0 deg" : (i == 1 ? "45 deg" : "90 deg"),
                   centers[i] - (i == 1 ? 15 : 12), 120);
  }
  tft.setPivot(120, 120);
  return true;
}

bool draw_sprite_clipping(TFT_eSPI& tft) {
  TFT_eSprite sprite(&tft);
  if (!sprite.createSprite(13, 13)) return false;
  sprite.fillSprite(TFT_BLACK);
  for (uint8_t y = 0; y < 13; ++y)
    for (uint8_t x = 0; x < 13; ++x)
      if ((x + y) & 1) sprite.drawPixel(x, y, TFT_WHITE);
  sprite.drawRect(0, 0, 13, 13, TFT_CYAN);
  sprite.pushSprite(-3, 146);
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("13x13 checker clipped left", 18, 149);
  return true;
}

void draw_text_scene(TFT_eSPI& tft) {
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLUE);
  tft.drawString("FONT 1 OPAQUE", 8, 14);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawString("Aa 123", 8, 26);

  for (int16_t x = 8; x < 152; x += 8)
    tft.fillRect(x, 48, 8, 20, ((x - 8) / 8) & 1 ? TFT_BLUE : TFT_RED);
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("FONT 2 TRANSPARENT", 8, 38);
  tft.setTextFont(2);
  tft.setTextColor(TFT_YELLOW);
  tft.drawString("TRANSPARENT", 12, 50);

  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("FONT 4 OPAQUE", 8, 74);
  tft.setTextFont(4);
  tft.setTextColor(TFT_WHITE, TFT_BLUE);
  tft.drawString("FONT 4", 8, 86);

  tft.drawFastHLine(8, 122, 224, TFT_DARKGREY);
  tft.setTextFont(1);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawString("LEFT EDGE", 4, 130);
  tft.drawString("RIGHT EDGE", 154, 130);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawString("LEFT", -4, 142);
  tft.drawString("RIGHT", 222, 142);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.drawString("BOTTOM", 190, 233);
}
}  // namespace

const char* validation_visual_case_name(uint8_t index) {
  return index < VALIDATION_VISUAL_CASE_COUNT ? kNames[index] : "unknown";
}

bool draw_validation_visual_case(uint8_t which, TFT_eSPI& tft) {
  if (which >= VALIDATION_VISUAL_CASE_COUNT) return false;
  tft.fillScreen(TFT_BLACK);
  if (which == 0) {
    tft.drawFastHLine(-16, 24, 272, TFT_RED);
    tft.drawFastHLine(-16, 215, 272, TFT_GREEN);
    tft.drawFastVLine(24, -16, 272, TFT_BLUE);
    tft.drawFastVLine(215, -16, 272, TFT_YELLOW);
    tft.fillRect(-8, -8, 24, 24, TFT_CYAN);
    tft.fillRect(224, 224, 24, 24, TFT_MAGENTA);
    tft.drawLine(-20, 0, 259, 239, TFT_WHITE);
  } else if (which == 1) {
    uint16_t image[16 * 16];
    for (uint8_t y = 0; y < 16; ++y)
      for (uint8_t x = 0; x < 16; ++x) image[y * 16 + x] = ((x + y) & 1) ? TFT_RED : TFT_GREEN;
    const bool swap = tft.getSwapBytes();
    tft.setSwapBytes(true);
    tft.pushImage(-3, 40, 16, 16, image);
    tft.pushImage(220, 60, 16, 16, image);
    tft.setSwapBytes(swap);
  } else if (which == 2) {
    if (!draw_sprite_rotations(tft) || !draw_sprite_clipping(tft)) return false;
  } else {
    draw_text_scene(tft);
  }
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Review pixels; N next, Q stop", 2, 228);
  return true;
}
