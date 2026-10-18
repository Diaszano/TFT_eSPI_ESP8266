#include "native/Scenes.h"

#include "tests/host/validation_oracle.h"
#include "SimulatorTransport.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

static std::vector<uint16_t> expected_edge() {
  std::vector<uint16_t> expected(240u * 240u, TFT_BLACK);
  paint_rect_reference(expected, 240, 240, {-10, 5, 20, 10}, TFT_RED);
  paint_rect_reference(expected, 240, 240, {230, 20, 20, 10}, TFT_GREEN);
  paint_rect_reference(expected, 240, 240, {240, 40, 1, 1}, TFT_BLUE);
  paint_rect_reference(expected, 240, 240, {50, -10, 10, 20}, TFT_YELLOW);
  paint_rect_reference(expected, 240, 240, {70, 230, 10, 20}, TFT_CYAN);
  paint_rect_reference(expected, 240, 240, {-1, -1, 2, 2}, TFT_RED);
  paint_rect_reference(expected, 240, 240, {239, -1, 2, 2}, TFT_GREEN);
  paint_rect_reference(expected, 240, 240, {-1, 239, 2, 2}, TFT_BLUE);
  paint_rect_reference(expected, 240, 240, {239, 239, 2, 2}, TFT_WHITE);
  paint_rect_reference(expected, 240, 240, {-5, 70, 20, 1}, TFT_WHITE);
  paint_rect_reference(expected, 240, 240, {90, -5, 1, 20}, TFT_BLUE);
  return expected;
}

static uint16_t image_pixel(int x, int y, uint32_t seed) {
  const uint16_t r = static_cast<uint16_t>((x * 3 + seed) & 31);
  const uint16_t g = static_cast<uint16_t>((y * 4 + seed) & 63);
  const uint16_t b = static_cast<uint16_t>((x + y + seed) & 31);
  return static_cast<uint16_t>((r << 11) | (g << 5) | b);
}

static void paint_image(std::vector<uint16_t>& frame, int left, int top, uint32_t seed) {
  for (int y = 0; y < 16; ++y)
    for (int x = 0; x < 16; ++x) {
      const int dx = left + x, dy = top + y;
      if (dx >= 0 && dx < 240 && dy >= 0 && dy < 240)
        frame[static_cast<std::size_t>(dy) * 240 + dx] = image_pixel(x, y, seed);
    }
}

int main() {
  auto solid = simulator::render_production_scene("solid_rgb565", 7, 0);
  assert(solid.status == simulator::SceneStatus::Rendered);
  assert(solid.pixels.size() == 240u * 240u);
  std::vector<uint16_t> expected_solid(240u * 240u, TFT_BLACK);
  const uint16_t colors[] = {TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE};
  for (int x = 0; x < 240; ++x)
    for (int y = 0; y < 240; ++y)
      expected_solid[static_cast<std::size_t>(y) * 240 + x] = colors[x / 60];
  assert(solid.pixels == expected_solid);

  const auto expected_edges = expected_edge();
  for (uint8_t rotation = 0; rotation < 4; ++rotation) {
    auto edge = simulator::render_production_scene("edge_rect", 7, rotation);
    assert(edge.status == simulator::SceneStatus::Rendered);
    std::vector<uint16_t> expected(240u * 240u, TFT_BLACK);
    for (int y = 0; y < 240; ++y)
      for (int x = 0; x < 240; ++x) {
        const int screen_x = (rotation == 2 || rotation == 3) ? 239 - x : x;
        const int screen_y = (rotation == 1 || rotation == 2) ? 239 - y : y;
        expected[static_cast<std::size_t>(screen_y) * 240 + screen_x] =
            expected_edges[static_cast<std::size_t>(y) * 240 + x];
      }
    if (edge.pixels != expected) {
      for (std::size_t i = 0; i < expected.size(); ++i)
        if (edge.pixels[i] != expected[i]) {
          std::fprintf(stderr, "edge rotation=%u x=%zu y=%zu expected=%04X actual=%04X\n", rotation,
                       i % 240, i / 240, expected[i], edge.pixels[i]);
          break;
        }
    }
    assert(edge.pixels == expected);
  }

  std::vector<uint16_t> expected_image(240u * 240u, TFT_BLACK);
  paint_image(expected_image, -3, 40, 11);
  paint_image(expected_image, 230, 60, 11);
  paint_image(expected_image, 40, -3, 11);
  paint_image(expected_image, 60, 230, 11);
  auto image = simulator::render_production_scene("image_crop16", 11, 0);
  assert(image.status == simulator::SceneStatus::Rendered);
  assert(image.pixels == expected_image);

  auto sprites = simulator::render_production_scene("sprite_depths", 1, 0);
  assert(sprites.status == simulator::SceneStatus::Rendered);
  std::vector<uint16_t> expected_sprites(240u * 240u, TFT_BLACK);
  for (int depth = 0; depth < 4; ++depth)
    for (int y = 0; y < 11; ++y)
      for (int x = 0; x < 13; ++x)
        if ((x + y) & 1)
          expected_sprites[static_cast<std::size_t>(150 + y) * 240 + 10 + depth * 30 + x] =
              TFT_WHITE;
  if (sprites.pixels != expected_sprites) {
    for (std::size_t i = 0; i < expected_sprites.size(); ++i)
      if (sprites.pixels[i] != expected_sprites[i]) {
        std::fprintf(stderr, "sprite mismatch x=%zu y=%zu expected=%04X actual=%04X\n", i % 240,
                     i / 240, expected_sprites[i], sprites.pixels[i]);
        break;
      }
  }
  assert(sprites.pixels == expected_sprites);

  auto text = simulator::render_production_scene("text_edges", 1, 0);
  assert(text.status == simulator::SceneStatus::Skip);
  assert(text.reason == "NO_INDEPENDENT_FONT_GOLDEN");
  assert(!simulator::host_spi().trace().events().empty());

  for (uint8_t rotation = 0; rotation < 4; ++rotation) {
    auto rotated = simulator::render_production_scene("rotation_0_3", 1, rotation);
    assert(rotated.status == simulator::SceneStatus::Rendered);
    assert(rotated.pixels.size() == 240u * 240u);
    std::vector<uint16_t> expected(240u * 240u, TFT_BLACK);
    const uint16_t pattern[4][4] = {{TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE},
                                    {0x1234, 0x5678, 0x9ABC, 0xDEF0},
                                    {0x1357, 0x2468, 0x369C, 0xABCD},
                                    {0x0F0F, 0xF0F0, 0x55AA, 0xAA55}};
    for (int y = 0; y < 4; ++y)
      for (int x = 0; x < 4; ++x) {
        const int screen_x[] = {20 + x, 20 + x, 219 - x, 219 - x};
        const int screen_y[] = {30 + y, 209 - y, 209 - y, 30 + y};
        expected[static_cast<std::size_t>(screen_y[rotation]) * 240 + screen_x[rotation]] =
            pattern[y][x];
      }
    if (rotated.pixels != expected) {
      for (std::size_t i = 0; i < expected.size(); ++i)
        if (rotated.pixels[i] != expected[i]) {
          std::fprintf(stderr, "rotation=%u x=%zu y=%zu expected=%04X actual=%04X\n", rotation,
                       i % 240, i / 240, expected[i], rotated.pixels[i]);
          break;
        }
    }
    assert(rotated.pixels == expected);
  }
}
