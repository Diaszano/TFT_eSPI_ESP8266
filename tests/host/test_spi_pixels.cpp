#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <vector>

static uint32_t registers[8], spi_length;
static std::vector<uint8_t> transmitted;
#define SPIBUSY 1
#define SPILMOSI 0
#define SPILMISO 16
#define SPI1U1 spi_length
#define SPI1W0 registers[0]
#define SPI1W1 registers[1]
#define SPI1W2 registers[2]
#define SPI1W3 registers[3]
#define SPI1W4 registers[4]
#define SPI1W5 registers[5]
#define SPI1W6 registers[6]
#define SPI1W7 registers[7]
// DAT8TO32 UNDER TEST
struct Command {
  operator uint32_t() const { return 0; }
  void operator|=(uint32_t) {
    const uint32_t bytes = ((spi_length & 0xFFFF) + 1) / 8;
    for (uint32_t i = 0; i < bytes; ++i)
      transmitted.push_back(static_cast<uint8_t>(registers[i / 4] >> ((i % 4) * 8)));
  }
} SPI1CMD;
class TFT_eSPI {
 public:
  void pushSwapBytePixels(const void* data_in, uint32_t len);
};
// FUNCTIONS UNDER TEST
int main() {
  for (uint32_t length : {0U, 1U, 2U, 3U, 15U, 16U, 17U, 31U, 32U, 33U}) {
    uint8_t* bytes = length ? static_cast<uint8_t*>(std::malloc(length * 2)) : nullptr;
    for (uint32_t i = 0; i < length * 2; ++i) bytes[i] = static_cast<uint8_t>(i * 23 + 7);
    transmitted.clear();
    TFT_eSPI display;
    display.pushSwapBytePixels(bytes, length);
    assert(transmitted.size() == length * 2);
    for (uint32_t i = 0; i < length; ++i) {
      assert(transmitted[i * 2] == bytes[i * 2 + 1]);
      assert(transmitted[i * 2 + 1] == bytes[i * 2]);
    }
    std::free(bytes);
  }
}
