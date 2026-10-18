#include "native/Scenes.h"

#include <cassert>
#include <string>

int main() {
  simulator::SceneRegistry registry;
  assert(registry.contains("solid_rgb565"));
  assert(registry.contains("edge_rect"));
  assert(registry.contains("image_crop16"));
  assert(registry.contains("rotation_0_3"));
  assert(registry.contains("sprite_depths"));
  assert(registry.contains("text_edges"));
  assert(registry.lookup("solid_rgb565").status == simulator::SceneStatus::Rendered);
  assert(registry.lookup("text_edges").status == simulator::SceneStatus::Skip);
  assert(std::string(registry.lookup("text_edges").reason) == "NO_INDEPENDENT_FONT_GOLDEN");
  assert(!registry.contains("X_unbounded"));
  assert(registry.lookup("missing").status == simulator::SceneStatus::Unsupported);
  for (uint8_t i = 0; i < 4; ++i) {
    const auto info = registry.lookup(std::string("s") + char('1' + i));
    assert(info.shared_visual_case == i);
    assert(info.status == simulator::SceneStatus::Rendered);
  }
}
