#include "Arduino.h"
#include "SPI.h"

SPIClass SPI;

void pinMode(uint8_t, uint8_t) {
}
void digitalWrite(uint8_t, uint8_t) {
}
void delay(uint32_t) {
}
void delayMicroseconds(uint32_t) {
}
uint8_t digitalPinToBitMask(uint8_t pin) {
  return static_cast<uint8_t>(1u << (pin & 7));
}
