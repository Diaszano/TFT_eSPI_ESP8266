#include "native/Scenes.h"
#include "ValidationVisualScenes.h"

#include <cassert>
#include <cstdint>
#include <string>
#include <vector>

static uint16_t expected_visible(uint16_t color) {
  return color;
}

static uint16_t pixel(const simulator::RenderResult& frame, int x, int y) {
  return frame.pixels[static_cast<std::size_t>(y) * 240 + x];
}

static bool has_non_black(const simulator::RenderResult& frame, int x0, int y0, int x1, int y1) {
  for (int y = y0; y < y1; ++y)
    for (int x = x0; x < x1; ++x)
      if (pixel(frame, x, y) != expected_visible(TFT_BLACK)) return true;
  return false;
}

int main() {
  simulator::SceneRegistry registry;
  for (uint8_t i = 0; i < 4; ++i) {
    const auto info = registry.lookup(std::string("s") + char('1' + i));
    assert(info.shared_visual_case == i);
    assert(std::string(info.name) == validation_visual_case_name(i));
    assert(std::string(info.reason) == "VISUAL_REVIEW_REQUIRED");
    assert(info.status == simulator::SceneStatus::Rendered);
    for (uint8_t rotation = 0; rotation < 4; ++rotation) {
      const auto rendered = simulator::render_production_scene(info.id, 0, rotation);
      assert(rendered.status == simulator::SceneStatus::Rendered);
      assert(rendered.reason == "VISUAL_REVIEW_REQUIRED");
      assert(rendered.pixels.size() == 240u * 240u);
    }
  }

  const auto s1 = simulator::render_production_scene("s1", 0, 0);
  assert(s1.status == simulator::SceneStatus::Rendered);
  for (int y = 0; y < 228; ++y) {
    for (int x = 0; x < 240; ++x) {
      uint16_t expected = TFT_BLACK;
      if (y == 24) expected = TFT_RED;
      if (y == 215) expected = TFT_GREEN;
      if (x == 24) expected = TFT_BLUE;
      if (x == 215) expected = TFT_YELLOW;
      if (x < 16 && y < 16) expected = TFT_CYAN;
      if (x >= 224 && y >= 224) expected = TFT_MAGENTA;
      if (y == ((x + 20) * 239 + 139) / 279) expected = TFT_WHITE;
      assert(pixel(s1, x, y) == expected_visible(expected));
    }
  }
  assert(pixel(s1, 215, 239) == expected_visible(TFT_YELLOW));
  assert(pixel(s1, 239, 239) == expected_visible(TFT_MAGENTA));
  assert(has_non_black(s1, 2, 228, 176, 236));
  const auto s1_repeat = simulator::render_production_scene("s1", 0, 0);
  assert(s1_repeat.pixels == s1.pixels);

  const auto s2 = simulator::render_production_scene("s2", 0, 0);
  assert(s2.status == simulator::SceneStatus::Rendered);
  for (int y = 0; y < 228; ++y) {
    for (int x = 0; x < 240; ++x) {
      uint16_t expected = TFT_BLACK;
      if (x >= 0 && x < 13 && y >= 40 && y < 56) {
        const int sx = x + 3;
        const int sy = y - 40;
        expected = ((sx + sy) & 1) ? TFT_RED : TFT_GREEN;
      } else if (x >= 220 && x < 236 && y >= 60 && y < 76) {
        const int sx = x - 220;
        const int sy = y - 60;
        expected = ((sx + sy) & 1) ? TFT_RED : TFT_GREEN;
      }
      assert(pixel(s2, x, y) == expected_visible(expected));
    }
  }
  assert(has_non_black(s2, 2, 228, 176, 236));
  const auto s2_repeat = simulator::render_production_scene("s2", 0, 0);
  assert(s2_repeat.pixels == s2.pixels);

  const auto s3 = simulator::render_production_scene("s3", 0, 0);
  assert(s3.status == simulator::SceneStatus::Rendered);
  assert(pixel(s3, 8, 44) == expected_visible(TFT_RED));
  assert(pixel(s3, 48, 44) == expected_visible(TFT_GREEN));
  assert(pixel(s3, 8, 84) == expected_visible(TFT_BLUE));
  assert(pixel(s3, 48, 84) == expected_visible(TFT_YELLOW));
  assert(pixel(s3, 35, 71) == expected_visible(TFT_CYAN));
  assert(pixel(s3, 120, 71) == expected_visible(TFT_CYAN));
  assert(pixel(s3, 205, 71) == expected_visible(TFT_CYAN));
  assert(pixel(s3, 35, 44) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 137, 54) == expected_visible(TFT_WHITE));
  assert(pixel(s3, 229, 71) == expected_visible(TFT_WHITE));
  assert(pixel(s3, 120, 51) == expected_visible(TFT_RED));
  assert(pixel(s3, 140, 71) == expected_visible(TFT_GREEN));
  assert(pixel(s3, 120, 91) == expected_visible(TFT_YELLOW));
  assert(pixel(s3, 100, 71) == expected_visible(TFT_BLUE));
  assert(pixel(s3, 225, 51) == expected_visible(TFT_RED));
  assert(pixel(s3, 225, 91) == expected_visible(TFT_GREEN));
  assert(pixel(s3, 185, 51) == expected_visible(TFT_BLUE));
  assert(pixel(s3, 185, 91) == expected_visible(TFT_YELLOW));
  assert(pixel(s3, 133, 53) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 227, 67) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 74, 71) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 166, 71) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 120, 25) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 120, 117) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 172, 71) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 238, 71) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 205, 38) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 205, 104) == expected_visible(TFT_BLACK));
  for (int y = 0; y < 64; ++y)
    for (int x = 0; x < 64; ++x) {
      uint16_t expected = TFT_MAGENTA;
      if (x >= 3 && x < 28 && y >= 3 && y < 28) expected = TFT_RED;
      if (x >= 36 && x < 61 && y >= 3 && y < 28) expected = TFT_GREEN;
      if (x >= 3 && x < 28 && y >= 36 && y < 61) expected = TFT_BLUE;
      if (x >= 36 && x < 61 && y >= 36 && y < 61) expected = TFT_YELLOW;
      if (x == 0 || x == 63 || y == 0 || y == 63 || (x == 32 && y >= 8 && y <= 24) ||
          (x + y == 40 && x >= 24 && x <= 32) || (x - y == 24 && x >= 32 && x <= 40) ||
          (y == 32 && x >= 29 && x <= 35) || (x == 32 && y >= 29 && y <= 35))
        expected = TFT_WHITE;
      if (x >= 30 && x < 35 && y >= 30 && y < 35) expected = TFT_CYAN;
      if (expected == TFT_MAGENTA) expected = TFT_BLACK;
      assert(pixel(s3, x + 3, y + 39) == expected_visible(expected));
    }
  for (int y = 0; y < 13; ++y)
    for (int x = 0; x < 10; ++x) {
      const int source_x = x + 3;
      const uint16_t expected = y == 0 || y == 12 || source_x == 12
                                    ? TFT_CYAN
                                    : (((source_x + y) & 1) ? TFT_WHITE : TFT_BLACK);
      assert(pixel(s3, x, y + 146) == expected_visible(expected));
    }
  assert(pixel(s3, 0, 146) == expected_visible(TFT_CYAN));
  assert(pixel(s3, 0, 147) == expected_visible(TFT_BLACK));
  assert(pixel(s3, 1, 147) == expected_visible(TFT_WHITE));
  assert(pixel(s3, 10, 147) == expected_visible(TFT_BLACK));
  assert(has_non_black(s3, 6, 25, 98, 117));
  const auto s3_repeat = simulator::render_production_scene("s3", 0, 0);
  assert(s3_repeat.pixels == s3.pixels);

  const auto s4 = simulator::render_production_scene("s4", 0, 0);
  assert(s4.status == simulator::SceneStatus::Rendered);
  assert(pixel(s4, 8, 122) == expected_visible(TFT_DARKGREY));
  assert(pixel(s4, 7, 122) == expected_visible(TFT_BLACK));
  assert(pixel(s4, 8, 18) == expected_visible(TFT_WHITE));
  assert(pixel(s4, 8, 48) == expected_visible(TFT_RED));
  assert(pixel(s4, 16, 48) == expected_visible(TFT_BLUE));
  assert(pixel(s4, 12, 53) == expected_visible(TFT_YELLOW));
  assert(pixel(s4, 11, 53) == expected_visible(TFT_RED));
  assert(pixel(s4, 148, 48) == expected_visible(TFT_BLUE));
  assert(pixel(s4, 148, 55) == expected_visible(TFT_BLUE));
  assert(pixel(s4, 13, 18) == expected_visible(TFT_BLUE));
  assert(pixel(s4, 10, 86) == expected_visible(TFT_BLUE));
  assert(pixel(s4, 10, 87) == expected_visible(TFT_WHITE));
  assert(has_non_black(s4, 8, 18, 80, 27));
  assert(has_non_black(s4, 8, 82, 112, 111));
  assert(has_non_black(s4, 222, 142, 240, 151));
  assert(pixel(s4, 221, 142) == expected_visible(TFT_BLACK));
  assert(has_non_black(s4, 0, 140, 30, 149));
  assert(has_non_black(s4, 190, 233, 240, 240));
  const auto s4_repeat = simulator::render_production_scene("s4", 0, 0);
  assert(s4_repeat.pixels == s4.pixels);
}
