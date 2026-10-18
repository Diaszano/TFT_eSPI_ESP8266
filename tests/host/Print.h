#ifndef VALIDATION_HOST_PRINT_H
#define VALIDATION_HOST_PRINT_H
#include <cstddef>
#include <cstdint>
#include <string>
class Print {
 public:
  std::string bytes;
  virtual ~Print() = default;
  virtual size_t write(const uint8_t* data, size_t size) {
    bytes.append(reinterpret_cast<const char*>(data), size);
    return size;
  }
  void println(const char* line) { bytes += std::string(line) + "\n"; }
};
#endif
