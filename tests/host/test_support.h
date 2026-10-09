#pragma once

#include <cstddef>
#include <cstdlib>

namespace host_test {
int allocation_number = 0;
int fail_at = 0;
int outstanding = 0;

void* tracked_malloc(size_t size) {
  if (++allocation_number == fail_at) return nullptr;
  void* ptr = std::malloc(size);
  if (ptr) ++outstanding;
  return ptr;
}

void* tracked_calloc(size_t count, size_t size) {
  if (++allocation_number == fail_at) return nullptr;
  void* ptr = std::calloc(count, size);
  if (ptr) ++outstanding;
  return ptr;
}

void tracked_free(void* ptr) {
  if (ptr) {
    --outstanding;
    std::free(ptr);
  }
}
}  // namespace host_test
