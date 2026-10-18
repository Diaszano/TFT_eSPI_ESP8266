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
  void print(const char* s) { bytes += s; }
  void print(char c) { bytes += c; }
  void print(int val) { bytes += std::to_string(val); }
  void print(uint32_t val) { bytes += std::to_string(val); }
  void print(uint64_t val) { bytes += std::to_string(val); }
  void println(const char* line) { bytes += std::string(line) + "\n"; }
  void println(uint32_t val) { bytes += std::to_string(val) + "\n"; }
};
#endif
