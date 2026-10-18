#ifndef VALIDATION_HOST_ARDUINO_H
#define VALIDATION_HOST_ARDUINO_H
#include "Print.h"
class HostSerial : public Print {
 public:
  std::string input;
  size_t position = 0;
  mutable unsigned available_calls = 0;
  unsigned suppress_until = 0;
  int available() const {
    if (++available_calls <= suppress_until) return 0;
    return static_cast<int>(input.size() - position);
  }
  int read() { return static_cast<unsigned char>(input[position++]); }
};
extern HostSerial Serial;
inline uint32_t micros() {
  static uint32_t now = 0;
  now += 100;
  return now;
}
inline uint32_t& host_millis_value() {
  static uint32_t value = 0;
  return value;
}
inline uint32_t& host_yield_step_value() {
  static uint32_t value = 0;
  return value;
}
inline uint32_t millis() { return host_millis_value(); }
inline void yield() { host_millis_value() += host_yield_step_value(); }
struct HostESP {
  uint32_t getCycleCount() const { return 12345; }
  uint32_t free_heap = 50000;
  uint32_t largest_block = 40000;
  uint32_t getFreeHeap() const { return free_heap; }
  uint32_t getMaxFreeBlockSize() const { return largest_block; }
};
extern HostESP ESP;
#endif
