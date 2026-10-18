#ifndef VALIDATION_HOST_ARDUINO_H
#define VALIDATION_HOST_ARDUINO_H
#include "Print.h"
class HostSerial : public Print {
 public:
  std::string input;
  size_t position = 0;
  int available() const { return static_cast<int>(input.size() - position); }
  int read() { return static_cast<unsigned char>(input[position++]); }
};
extern HostSerial Serial;
inline uint32_t micros() {
  static uint32_t now = 0;
  now += 100;
  return now;
}
inline void yield() {}
struct HostESP {
  uint32_t getCycleCount() const { return 12345; }
  uint32_t getFreeHeap() const { return 50000; }
  uint32_t getMaxFreeBlockSize() const { return 40000; }
};
extern HostESP ESP;
#endif
