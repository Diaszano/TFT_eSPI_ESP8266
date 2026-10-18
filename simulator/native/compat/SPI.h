#pragma once

#include <cstdint>
#include <SimulatorTransport.h>

constexpr uint32_t SPILMISO = 0;
constexpr uint32_t SPILMOSI = 17;
constexpr uint32_t SPIBUSY = 1;
constexpr uint32_t SPIUMOSI = 1;
constexpr uint32_t SPIUSSE = 2;
constexpr uint32_t SPIUCSSETUP = 4;
constexpr uint32_t SPIUCSHOLD = 8;
constexpr uint32_t SPIUDUPLEX = 16;
constexpr uint8_t TFT_SPI_MODE = 3;

class SPIClass {
 public:
  void begin() {}
  void setHwCs(uint8_t) {}
  void setBitOrder(uint8_t) {}
  void setDataMode(uint8_t) {}
  void setFrequency(uint32_t) {}
  uint8_t transfer(uint8_t) {
    simulator::host_spi().unsupported_read();
    return 0;
  }
};

extern SPIClass SPI;
