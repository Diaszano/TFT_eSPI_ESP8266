#include "native/Scenes.h"

#include "SimulatorTransport.h"
#include "ValidationVisualScenes.h"

#include <array>
#include <stdexcept>

namespace simulator {
namespace {
using Draw = void (*)(SceneContext&);

struct Entry {
  SceneInfo info;
  Draw draw;
};

void solid_rgb565(SceneContext& context) {
  TFT_eSPI& tft = context.tft;
  tft.fillScreen(TFT_BLACK);
  const uint16_t colors[] = {TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE};
  for (int i = 0; i < 4; ++i) tft.fillRect(i * 60, 0, 60, 240, colors[i]);
}

void edge_rect(SceneContext& context) {
  TFT_eSPI& tft = context.tft;
  tft.fillScreen(TFT_BLACK);
  tft.fillRect(-10, 5, 20, 10, TFT_RED);
  tft.fillRect(230, 20, 20, 10, TFT_GREEN);
  tft.fillRect(240, 40, 1, 1, TFT_BLUE);
  tft.fillRect(50, -10, 10, 20, TFT_YELLOW);
  tft.fillRect(70, 230, 10, 20, TFT_CYAN);
  tft.fillRect(-1, -1, 2, 2, TFT_RED);
  tft.fillRect(239, -1, 2, 2, TFT_GREEN);
  tft.fillRect(-1, 239, 2, 2, TFT_BLUE);
  tft.fillRect(239, 239, 2, 2, TFT_WHITE);
  tft.fillRect(100, 100, 0, 10, TFT_MAGENTA);
  tft.drawFastHLine(-5, 70, 20, TFT_WHITE);
  tft.drawFastVLine(90, -5, 20, TFT_BLUE);
}

uint16_t image_pixel(int x, int y, uint32_t seed) {
  return static_cast<uint16_t>((((x * 3 + seed) & 31) << 11) | (((y * 4 + seed) & 63) << 5) |
                               ((x + y + seed) & 31));
}

void image_crop16(SceneContext& context) {
  uint16_t image[16 * 16];
  for (int y = 0; y < 16; ++y)
    for (int x = 0; x < 16; ++x) image[y * 16 + x] = image_pixel(x, y, context.seed);
  context.tft.fillScreen(TFT_BLACK);
  context.tft.setSwapBytes(true);
  context.tft.pushImage(-3, 40, 16, 16, image);
  context.tft.pushImage(230, 60, 16, 16, image);
  context.tft.pushImage(40, -3, 16, 16, image);
  context.tft.pushImage(60, 230, 16, 16, image);
  context.tft.setSwapBytes(false);
}

void rotation_0_3(SceneContext& context) {
  TFT_eSPI& tft = context.tft;
  tft.setRotation(context.rotation);
  tft.fillScreen(TFT_BLACK);
  const uint16_t pattern[4][4] = {{TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE},
                                  {0x1234, 0x5678, 0x9ABC, 0xDEF0},
                                  {0x1357, 0x2468, 0x369C, 0xABCD},
                                  {0x0F0F, 0xF0F0, 0x55AA, 0xAA55}};
  for (int y = 0; y < 4; ++y)
    for (int x = 0; x < 4; ++x) tft.drawPixel(20 + x, 30 + y, pattern[y][x]);
}

bool sprite_depth(TFT_eSPI& tft, uint8_t depth, int x) {
  TFT_eSprite sprite(&tft);
  sprite.setColorDepth(depth);
  if (!sprite.createSprite(13, 11)) return false;
  if (depth == 1) sprite.setBitmapColor(TFT_WHITE, TFT_BLACK);
  if (depth == 4) {
    sprite.setPaletteColor(0, TFT_BLACK);
    sprite.setPaletteColor(15, TFT_WHITE);
  }
  for (int y = 0; y < 11; ++y)
    for (int px = 0; px < 13; ++px)
      sprite.drawPixel(px, y, ((px + y) & 1) ? (depth == 1 ? 1 : TFT_WHITE) : TFT_BLACK);
  sprite.pushSprite(x, 150);
  sprite.deleteSprite();
  return true;
}

void sprite_depths(SceneContext& context) {
  context.tft.fillScreen(TFT_BLACK);
  const uint8_t depths[] = {1, 4, 8, 16};
  for (uint8_t i = 0; i < 4; ++i)
    if (!sprite_depth(context.tft, depths[i], 10 + i * 30))
      throw std::runtime_error("SKIP: sprite allocation failed");
}

void text_edges(SceneContext& context) {
  TFT_eSPI& tft = context.tft;
  tft.fillScreen(TFT_BLACK);
  for (int16_t y = 0; y < tft.height(); y += 12) tft.drawFastHLine(0, y, tft.width(), TFT_BLUE);
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("font 1 edge", 220, 12);
  tft.setTextFont(2);
  tft.setTextColor(TFT_YELLOW);
  tft.drawString("transparent", 220, 80);
  tft.setTextFont(4);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.drawString("EDGE", 220, 190);
}

void shared_visual(SceneContext& context) {
  if (!draw_validation_visual_case(context.shared_visual_case, context.tft))
    throw std::runtime_error("FAIL: shared visual sprite allocation failed");
}

const std::array<Entry, 10>& entries() {
  static const std::array<Entry, 10> all = {{
      {{"solid_rgb565", "solid_rgb565", SceneStatus::Rendered, "", -1}, solid_rgb565},
      {{"edge_rect", "edge_rect", SceneStatus::Rendered, "", -1}, edge_rect},
      {{"image_crop16", "image_crop16", SceneStatus::Rendered, "", -1}, image_crop16},
      {{"rotation_0_3", "rotation_0_3", SceneStatus::Rendered, "", -1}, rotation_0_3},
      {{"sprite_depths", "sprite_depths", SceneStatus::Rendered, "", -1}, sprite_depths},
      {{"text_edges", "text_edges", SceneStatus::Skip, "NO_INDEPENDENT_FONT_GOLDEN", -1},
       text_edges},
      {{"s1", "edge_clipping", SceneStatus::Rendered, "VISUAL_REVIEW_REQUIRED", 0}, shared_visual},
      {{"s2", "image_source_clipping", SceneStatus::Rendered, "VISUAL_REVIEW_REQUIRED", 1},
       shared_visual},
      {{"s3", "sprite_crop_and_rotation", SceneStatus::Rendered, "VISUAL_REVIEW_REQUIRED", 2},
       shared_visual},
      {{"s4", "text_opaque_transparent_edges", SceneStatus::Rendered, "VISUAL_REVIEW_REQUIRED", 3},
       shared_visual},
  }};
  return all;
}

const Entry* find(const std::string& id) {
  for (const Entry& entry : entries())
    if (id == entry.info.id) return &entry;
  return nullptr;
}
}  // namespace

bool SceneRegistry::contains(const std::string& id) const {
  return find(id) != nullptr;
}

SceneInfo SceneRegistry::lookup(const std::string& id) const {
  const Entry* entry = find(id);
  return entry ? entry->info
               : SceneInfo{"", "unknown", SceneStatus::Unsupported, "unknown scene id", -1};
}

std::size_t SceneRegistry::size() const noexcept {
  return entries().size();
}

SceneInfo SceneRegistry::at(std::size_t index) const {
  if (index >= entries().size())
    return SceneInfo{"", "unknown", SceneStatus::Unsupported, "out of range", -1};
  return entries()[index].info;
}

SceneStatus run_scene(const std::string& id, SceneContext& context) {
  const Entry* entry = find(id);
  if (!entry) return SceneStatus::Unsupported;
  if (context.rotation > 3) return SceneStatus::Unsupported;
  if (entry->info.shared_visual_case >= 0)
    context.shared_visual_case = static_cast<uint8_t>(entry->info.shared_visual_case);
  try {
    entry->draw(context);
  } catch (const std::runtime_error& error) {
    if (std::string(error.what()).find("SKIP:") == 0) return SceneStatus::Skip;
    if (std::string(error.what()).find("FAIL:") == 0) return SceneStatus::Failed;
    throw;
  }
  return entry->info.status;
}

RenderResult render_production_scene(const std::string& id, uint32_t seed, uint8_t rotation) {
  SceneRegistry registry;
  const SceneInfo info = registry.lookup(id);
  if (info.status == SceneStatus::Unsupported)
    return {SceneStatus::Unsupported, info.reason, seed, rotation, {}};
  if (rotation > 3) return {SceneStatus::Unsupported, "rotation must be 0..3", seed, rotation, {}};

  host_spi().reset();
  TFT_eSPI tft;
  tft.init();
  const SpiTrace init_trace = host_spi().trace();
  host_spi().reset();
  tft.setRotation(rotation);
  SceneContext context{tft, seed, rotation, 0};
  const SceneStatus status = run_scene(id, context);
  if (status != SceneStatus::Rendered)
    return {status,
            status == SceneStatus::Failed ? "shared visual sprite allocation failed" : info.reason,
            seed,
            rotation,
            {}};
  const SpiTrace scene_trace = host_spi().trace();

  St7789VirtualController controller(Profile::nodemcu_st7789_240x240());
  controller.replay(init_trace);
  controller.apply(scene_trace);
  std::vector<uint16_t> pixels(240u * 240u);
  for (uint16_t y = 0; y < 240; ++y)
    for (uint16_t x = 0; x < 240; ++x)
      pixels[static_cast<std::size_t>(y) * 240 + x] = controller.visible_pixel(x, y);
  return {SceneStatus::Rendered, info.reason, seed, rotation, std::move(pixels)};
}

}  // namespace simulator
