#include "stateful_cases.h"
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

class TFT_eSPI {
 public:
  int32_t _xDatum = 0, _yDatum = 0, _xWidth = 8, _yHeight = 8;
  int32_t _vpX = 0, _vpY = 0, _vpW = 8, _vpH = 8;
  bool _vpDatum = false, _vpOoB = false, inTransaction = false;
  bool lockTransaction = false, _swapBytes = false;
  uint8_t textfont = 1;
  void* gfxFont = nullptr;
  std::vector<uint16_t> fb = std::vector<uint16_t>(64, 0);
  int32_t wx = 0, wy = 0, ww = 0;
  int32_t width() { return 8; }
  int32_t height() { return 8; }
  void begin_tft_write() {}
  void end_tft_write() {}
  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1) {
    wx = x0; wy = y0; ww = x1 - x0 + 1; (void)y1;
  }
  void pushBlock(uint32_t color, int32_t count) {
    for (int32_t i = 0; i < count; ++i)
      fb[(wy + i / ww) * 8 + wx + i % ww] = static_cast<uint16_t>(color);
  }
  void setViewport(int32_t, int32_t, int32_t, int32_t, bool);
  void drawFastHLine(int32_t, int32_t, int32_t, uint32_t);
  void fillRect(int32_t, int32_t, int32_t, int32_t, uint32_t);
  void setSwapBytes(bool);
  void setTextFont(uint8_t);
};
// FUNCTIONS UNDER TEST

void run_stateful_case(uint32_t seed, const std::vector<stateful::Operation>& operations) {
  TFT_eSPI actual;
  std::vector<uint16_t> expected(64, 0);
  int left = 0, top = 0, right = 8, bottom = 8;
  bool valid = true, swap = false;
  uint8_t font = 1;
  for (size_t index = 0; index < operations.size(); ++index) {
    const auto& op = operations[index];
    if (op.kind == stateful::Kind::Viewport) {
      actual.setViewport(op.x, op.y, op.w, op.h, false);
      left = std::max(0, op.x);
      top = std::max(0, op.y);
      right = std::min(8, op.x + op.w);
      bottom = std::min(8, op.y + op.h);
      valid = right > left && bottom > top;
    } else if (op.kind == stateful::Kind::Rect ||
               op.kind == stateful::Kind::HLine) {
      const int h = op.kind == stateful::Kind::HLine ? 1 : op.h;
      if (op.kind == stateful::Kind::HLine)
        actual.drawFastHLine(op.x, op.y, op.w, op.value);
      else
        actual.fillRect(op.x, op.y, op.w, op.h, op.value);
      if (valid && op.w > 0 && h > 0)
        for (int y = std::max({0, top, op.y}); y < std::min({8, bottom, op.y + h}); ++y)
          for (int x = std::max({0, left, op.x}); x < std::min({8, right, op.x + op.w}); ++x)
            expected[y * 8 + x] = op.value;
    } else if (op.kind == stateful::Kind::Swap) {
      swap = op.value & 1;
      actual.setSwapBytes(swap);
    } else {
      font = 1 + op.value % 8;
      actual.setTextFont(font);
    }
    if (actual.fb != expected || actual._swapBytes != swap ||
        actual.textfont != font || actual._vpOoB == valid) {
      std::fprintf(stderr, "stateful seed=%u failed at operation=%zu kind=%d\n",
                   seed, index, static_cast<int>(op.kind));
      std::abort();
    }
  }
}

int main() {
  const auto first = stateful::generate(123, 80);
  assert(first == stateful::generate(123, 80));
  assert(first != stateful::generate(124, 80));
  for (uint32_t seed : {1U, 2U, 123U, 456U})
    run_stateful_case(seed, stateful::generate(seed, 80));
  auto failing = first;
  const stateful::Operation marker = {stateful::Kind::Rect, 0, 0, 1, 1, 0xdead};
  failing.push_back(marker);
  const auto injected_failure = [marker](const std::vector<stateful::Operation>& ops) {
    return std::find(ops.begin(), ops.end(), marker) != ops.end();
  };
  const auto reduced = stateful::shrink(failing, injected_failure);
  assert(reduced.size() == 1 && reduced[0] == marker);
  assert(injected_failure(reduced));
}
