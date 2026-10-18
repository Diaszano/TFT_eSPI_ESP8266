#include "native/Scenes.h"

#include <cerrno>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

namespace {
bool parse_number(const char* text, unsigned long max_value, unsigned long* value) {
  if (!text || !*text || *text == '-') return false;
  errno = 0;
  char* end = nullptr;
  const unsigned long parsed = std::strtoul(text, &end, 10);
  if (errno || *end || parsed > max_value) return false;
  *value = parsed;
  return true;
}

void usage() {
  std::cerr << "Usage: simulator_runner (--list-scenes | --scene ID [--seed UINT32]"
               " [--rotation 0..3] [--rgb565-stdout])\n";
}
}  // namespace

int main(int argc, char** argv) {
  std::string scene;
  bool has_scene = false, has_seed = false, has_rotation = false;
  bool rgb565_stdout = false, list_scenes = false;
  unsigned long seed = 0, rotation = 0;
  for (int i = 1; i < argc; ++i) {
    const std::string option(argv[i]);
    if (option == "--list-scenes" && !list_scenes) {
      list_scenes = true;
    } else if (option == "--scene" && !has_scene && i + 1 < argc) {
      scene = argv[++i];
      has_scene = true;
    } else if (option == "--seed" && !has_seed && i + 1 < argc) {
      if (!parse_number(argv[++i], std::numeric_limits<uint32_t>::max(), &seed)) {
        usage();
        return 2;
      }
      has_seed = true;
    } else if (option == "--rotation" && !has_rotation && i + 1 < argc) {
      if (!parse_number(argv[++i], 3, &rotation)) {
        usage();
        return 2;
      }
      has_rotation = true;
    } else if (option == "--rgb565-stdout" && !rgb565_stdout) {
      rgb565_stdout = true;
    } else {
      usage();
      return 2;
    }
  }
  if (list_scenes) {
    if (has_scene || has_seed || has_rotation || rgb565_stdout) {
      usage();
      return 2;
    }
    const simulator::SceneRegistry registry;
    for (std::size_t i = 0; i < registry.size(); ++i) std::cout << registry.at(i).id << '\n';
    return 0;
  }
  if (!has_scene) {
    usage();
    return 2;
  }

  const simulator::RenderResult result = simulator::render_production_scene(
      scene, static_cast<uint32_t>(seed), static_cast<uint8_t>(rotation));
  if (result.status == simulator::SceneStatus::Rendered) {
    if (rgb565_stdout) {
      for (uint16_t pixel : result.pixels) {
        std::cout.put(static_cast<char>(pixel & 0xFF));
        std::cout.put(static_cast<char>(pixel >> 8));
      }
      return 0;
    }
    std::cout << "RENDERED scene=" << scene << " seed=" << result.seed
              << " rotation=" << static_cast<unsigned>(result.rotation) << '\n';
    return 0;
  }
  if (result.status == simulator::SceneStatus::Failed) {
    std::cerr << "FAILED scene=" << scene << " reason=" << result.reason << '\n';
    return 1;
  }
  std::cerr << (result.status == simulator::SceneStatus::Skip ? "SKIP" : "UNSUPPORTED")
            << " scene=" << scene << " reason=" << result.reason << '\n';
  return result.status == simulator::SceneStatus::Skip ? 3 : 2;
}
