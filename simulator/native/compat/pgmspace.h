#pragma once

#include <cstdint>
#include <cstddef>

#define PROGMEM
inline uint8_t pgm_read_byte(const void* p) {
  return *static_cast<const uint8_t*>(p);
}
inline uint16_t pgm_read_word(const void* p) {
  return *static_cast<const uint16_t*>(p);
}
inline uintptr_t pgm_read_dword(const void* p) {
  return *static_cast<const uintptr_t*>(p);
}
