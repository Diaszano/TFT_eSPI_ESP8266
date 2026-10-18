#pragma once

#include "core/St7789VirtualController.h"

#include <TFT_eSPI.h>

#include <cstdint>
#include <string>
#include <vector>

namespace simulator {

enum class SceneStatus { Rendered, Skip, Unsupported, Failed };

struct SceneInfo {
  const char* id;
  const char* name;
  SceneStatus status;
  const char* reason;
  int8_t shared_visual_case;
};

struct SceneContext {
  TFT_eSPI& tft;
  uint32_t seed;
  uint8_t rotation;
  uint8_t shared_visual_case;
};

struct RenderResult {
  SceneStatus status;
  std::string reason;
  uint32_t seed;
  uint8_t rotation;
  std::vector<uint16_t> pixels;
};

class SceneRegistry {
 public:
  bool contains(const std::string& id) const;
  SceneInfo lookup(const std::string& id) const;
  std::size_t size() const noexcept;
  SceneInfo at(std::size_t index) const;
};

SceneStatus run_scene(const std::string& id, SceneContext& context);
RenderResult render_production_scene(const std::string& id, uint32_t seed, uint8_t rotation);

}  // namespace simulator
