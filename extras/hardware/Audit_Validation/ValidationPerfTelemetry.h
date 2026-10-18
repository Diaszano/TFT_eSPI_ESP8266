#ifndef VALIDATION_PERF_TELEMETRY_H
#define VALIDATION_PERF_TELEMETRY_H

#include <Print.h>
#include <stddef.h>
#include <stdint.h>

uint32_t validation_perf_crc32(const char* bytes, size_t size);

class ValidationPerfEmitter {
 public:
  ValidationPerfEmitter(Print& output, const char* run_id);
  bool begin(const char* suite, uint32_t seed, uint32_t expected_count, const char* profile_id);
  bool samples(const char* suite, uint32_t batch_id, uint32_t chunk_index,
               const uint32_t* values, uint8_t count);
  bool mem(const char* suite, uint32_t checkpoint, uint32_t free_heap, uint32_t largest_block,
           uint32_t min_heap, uint32_t failures);
  bool end(const char* suite, uint32_t observed_count, uint64_t elapsed_us, const char* status);
  bool abort(const char* suite, uint32_t observed_count, const char* reason);

 private:
  bool emit(const char* kind, const char* fields);
  Print& output_;
  char run_id_[17];
  uint64_t next_sequence_;
  bool valid_;
};

#endif
