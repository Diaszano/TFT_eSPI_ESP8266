#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>

struct FileState {
  std::vector<uint8_t> data;
  size_t position = 0;
  bool exists = true;
  bool failSeek = false;
  bool shortPixels = false;
  size_t largestRead = 0;
};
std::shared_ptr<FileState> activeFile;

namespace fs {
class File {
 public:
  explicit File(std::shared_ptr<FileState> state = nullptr) : state_(state) {}
  explicit operator bool() const { return state_ && state_->exists; }
  size_t size() const { return state_->data.size(); }
  bool seek(uint32_t position) {
    if (state_->failSeek || position > size()) return false;
    state_->position = position;
    return true;
  }
  int read(uint8_t* output, size_t count) {
    state_->largestRead = std::max(state_->largestRead, count);
    const size_t available = size() - state_->position;
    size_t received = std::min(count, available);
    if (state_->shortPixels && state_->position >= 54 && received) --received;
    if (received) std::memcpy(output, state_->data.data() + state_->position, received);
    state_->position += received;
    return int(received);
  }
  int read() {
    uint8_t byte;
    return read(&byte, 1) == 1 ? byte : -1;
  }
  void close() {}

 private:
  std::shared_ptr<FileState> state_;
};
}  // namespace fs
struct Filesystem {
  fs::File open(const char*, const char*) { return fs::File(activeFile); }
} LittleFS;
struct SerialPort {
  int errors = 0;
  template <class T>
  void print(const T&) {}
  template <class T>
  void println(const T&) {
    ++errors;
  }
} Serial;
struct Display {
  bool swap = false;
  std::vector<uint16_t> screen = std::vector<uint16_t>(240 * 240, 0);
  size_t pushes = 0;
  int32_t width() const { return 240; }
  int32_t height() const { return 240; }
  bool getSwapBytes() const { return swap; }
  void setSwapBytes(bool value) { swap = value; }
  void pushImage(int32_t x, int32_t y, int32_t width, int32_t height, uint16_t* pixels) {
    assert(swap);
    assert(x >= 0 && y >= 0 && x + width <= 240 && y + height <= 240);
    assert(width <= 32 && height == 1);
    ++pushes;
    for (int32_t index = 0; index < width; ++index) screen[y * 240 + x + index] = pixels[index];
  }
} tft;
uint32_t millis() {
  return 0;
}

// FUNCTIONS UNDER TEST

void put16(std::vector<uint8_t>& data, size_t index, uint16_t value) {
  data[index] = uint8_t(value);
  data[index + 1] = uint8_t(value >> 8);
}
void put32(std::vector<uint8_t>& data, size_t index, uint32_t value) {
  for (unsigned byte = 0; byte < 4; ++byte) data[index + byte] = uint8_t(value >> (8 * byte));
}
std::vector<uint8_t> bitmap(uint32_t width = 3, uint32_t height = 2) {
  const size_t stride = (size_t(width) * 3 + 3) & ~size_t(3);
  std::vector<uint8_t> data(54 + stride * height, 0);
  put16(data, 0, 0x4D42);
  put32(data, 2, data.size());
  put32(data, 10, 54);
  put32(data, 14, 40);
  put32(data, 18, width);
  put32(data, 22, height);
  put16(data, 26, 1);
  put16(data, 28, 24);
  for (uint32_t row = 0; row < height; ++row) {
    for (uint32_t col = 0; col < width; ++col) {
      uint8_t* pixel = data.data() + 54 + row * stride + col * 3;
      pixel[2] = row == height - 1 ? 255 : 0;
      pixel[1] = row == height - 1 ? 0 : 255;
    }
  }
  return data;
}
void reset(const std::vector<uint8_t>& data, bool swap = false) {
  activeFile = std::make_shared<FileState>();
  activeFile->data = data;
  tft = Display();
  tft.swap = swap;
  Serial.errors = 0;
}
void rejected(const std::vector<uint8_t>& data) {
  for (bool swap : {false, true}) {
    reset(data, swap);
    drawBmp("/image.bmp", 0, 0);
    assert(tft.pushes == 0);
    assert(tft.swap == swap);
    assert(Serial.errors > 0);
  }
}
int main() {
  for (bool swap : {false, true}) {
    reset(bitmap(), swap);
    drawBmp("/image.bmp", 0, 0);
    assert(tft.screen[0] == 0xF800 && tft.screen[2] == 0xF800);
    assert(tft.screen[240] == 0x07E0 && tft.screen[242] == 0x07E0);
    assert(tft.screen[3] == 0 && tft.swap == swap && Serial.errors == 0);
    assert(activeFile->largestRead <= 96);
  }
  reset(bitmap(4096, 2));
  drawBmp("/wide.bmp", -4094, -1);
  assert(tft.screen[0] == 0x07E0 && tft.screen[1] == 0x07E0 && tft.screen[2] == 0);
  assert(activeFile->largestRead <= 96 && !tft.swap);
  reset(bitmap(257, 1));
  drawBmp("/wide.bmp", 0, 0);
  assert(tft.screen[239] == 0xF800 && tft.pushes == 8 && activeFile->largestRead <= 96);
  reset(bitmap());
  drawBmp("/offscreen.bmp", -10, -10);
  assert(tft.pushes == 0 && !tft.swap);
  reset(bitmap());
  activeFile->exists = false;
  drawBmp("/missing.bmp", 0, 0);
  assert(Serial.errors == 1 && tft.pushes == 0);
  for (size_t length : {size_t(0), size_t(53), size_t(54), size_t(60)}) {
    auto data = bitmap();
    data.resize(length);
    rejected(data);
  }
  for (size_t field : {size_t(18), size_t(22)}) {
    for (uint32_t value : {0U, 0xFFFFFFFFU, 0x7FFFFFFFU}) {
      auto data = bitmap();
      put32(data, field, value);
      rejected(data);
    }
  }
  for (size_t field : {size_t(2), size_t(10), size_t(14), size_t(34)}) {
    auto data = bitmap();
    put32(data, field, 0xFFFFFFFFU);
    rejected(data);
  }
  for (size_t field : {size_t(26), size_t(28)}) {
    auto data = bitmap();
    put16(data, field, 8);
    rejected(data);
  }
  auto compressed = bitmap();
  put32(compressed, 30, 1);
  rejected(compressed);
  auto signature = bitmap();
  signature[0] = 0;
  rejected(signature);
  auto overlapping = bitmap();
  put32(overlapping, 10, 53);
  rejected(overlapping);
  for (bool swap : {false, true}) {
    reset(bitmap(), swap);
    activeFile->failSeek = true;
    drawBmp("/seek.bmp", 0, 0);
    assert(tft.pushes == 0 && tft.swap == swap && Serial.errors == 1);
    reset(bitmap(), swap);
    activeFile->shortPixels = true;
    drawBmp("/short.bmp", 0, 0);
    assert(tft.pushes == 0 && tft.swap == swap && Serial.errors == 1);
  }
}
