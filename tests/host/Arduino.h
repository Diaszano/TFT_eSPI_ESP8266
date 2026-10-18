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
#endif
