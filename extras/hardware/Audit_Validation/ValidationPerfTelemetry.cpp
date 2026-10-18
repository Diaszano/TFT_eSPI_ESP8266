#include "ValidationPerfTelemetry.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

namespace {
bool token(const char* value, size_t max_length) {
  if (!value || !*value) return false;
  size_t length = 0;
  for (; value[length]; ++length) {
    const char ch = value[length];
    if (length >= max_length || !((ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
                                  (ch >= '0' && ch <= '9') || ch == '_' || ch == '-'))
      return false;
  }
  return true;
}

bool formatted(int size, size_t capacity) {
  return size > 0 && static_cast<size_t>(size) < capacity;
}

void base64_samples(const uint32_t* values, uint8_t count, char* output) {
  static const char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  uint8_t bytes[64];
  for (uint8_t i = 0; i < count; ++i)
    for (uint8_t b = 0; b < 4; ++b) bytes[i * 4 + b] = static_cast<uint8_t>(values[i] >> (8 * b));
  const size_t length = count * 4;
  size_t position = 0;
  for (size_t i = 0; i < length; i += 3) {
    const uint32_t block = (static_cast<uint32_t>(bytes[i]) << 16) |
                           (i + 1 < length ? static_cast<uint32_t>(bytes[i + 1]) << 8 : 0) |
                           (i + 2 < length ? bytes[i + 2] : 0);
    output[position++] = alphabet[(block >> 18) & 63];
    output[position++] = alphabet[(block >> 12) & 63];
    output[position++] = i + 1 < length ? alphabet[(block >> 6) & 63] : '=';
    output[position++] = i + 2 < length ? alphabet[block & 63] : '=';
  }
  output[position] = '\0';
}
}  // namespace

uint32_t validation_perf_crc32(const char* bytes, size_t size) {
  uint32_t crc = 0xffffffffUL;
  for (size_t i = 0; i < size; ++i) {
    crc ^= static_cast<uint8_t>(bytes[i]);
    for (uint8_t bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320UL : 0);
  }
  return crc ^ 0xffffffffUL;
}

ValidationPerfEmitter::ValidationPerfEmitter(Print& output, const char* run_id)
    : output_(output), next_sequence_(0), valid_(token(run_id, 16)) {
  run_id_[0] = '\0';
  if (valid_) strcpy(run_id_, run_id);
}

bool ValidationPerfEmitter::emit(const char* kind, const char* fields) {
  if (!valid_ || next_sequence_ > UINT32_MAX) return false;
  char line[193];
  const int prefix = snprintf(line, sizeof(line), "PERF,1,%s,%" PRIu64 ",%s,%s", run_id_,
                              next_sequence_, kind, fields);
  if (!formatted(prefix, sizeof(line)) || prefix + 10 > 192) return false;
  const uint32_t crc = validation_perf_crc32(line, static_cast<size_t>(prefix));
  const int suffix = snprintf(line + prefix, sizeof(line) - prefix, ",%08" PRIx32 "\n", crc);
  if (!formatted(suffix, sizeof(line) - prefix)) return false;
  const size_t length = static_cast<size_t>(prefix + suffix);
  if (output_.write(reinterpret_cast<const uint8_t*>(line), length) != length) return false;
  ++next_sequence_;
  return true;
}

bool ValidationPerfEmitter::begin(const char* suite, uint32_t seed, uint32_t expected_count,
                                  const char* profile_id) {
  if (!token(suite, 32) || !token(profile_id, 32)) return false;
  char fields[130];
  const int size = snprintf(fields, sizeof(fields), "%s,%" PRIu32 ",%" PRIu32 ",%s", suite, seed,
                            expected_count, profile_id);
  return formatted(size, sizeof(fields)) && emit("BEGIN", fields);
}

bool ValidationPerfEmitter::samples(const char* suite, uint32_t batch_id, uint32_t chunk_index,
                                    const uint32_t* values, uint8_t count) {
  if (!token(suite, 32) || !values || !count || count > 16) return false;
  char encoded[89];
  base64_samples(values, count, encoded);
  char fields[160];
  const int size = snprintf(fields, sizeof(fields), "%s,%" PRIu32 ",%" PRIu32 ",%u,%s", suite,
                            batch_id, chunk_index, count, encoded);
  return formatted(size, sizeof(fields)) && emit("SAMPLES", fields);
}

bool ValidationPerfEmitter::mem(const char* suite, uint32_t checkpoint, uint32_t free_heap,
                                uint32_t largest_block, uint32_t min_heap, uint32_t failures) {
  if (!token(suite, 32) || largest_block > free_heap) return false;
  char fields[150];
  const int size = snprintf(fields, sizeof(fields),
                            "%s,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32, suite,
                            checkpoint, free_heap, largest_block, min_heap, failures);
  return formatted(size, sizeof(fields)) && emit("MEM", fields);
}

bool ValidationPerfEmitter::end(const char* suite, uint32_t observed_count, uint64_t elapsed_us,
                                const char* status) {
  if (!token(suite, 32) || !token(status, 16)) return false;
  char fields[130];
  const int size = snprintf(fields, sizeof(fields), "%s,%" PRIu32 ",%" PRIu64 ",%s", suite,
                            observed_count, elapsed_us, status);
  return formatted(size, sizeof(fields)) && emit("END", fields);
}

bool ValidationPerfEmitter::abort(const char* suite, uint32_t observed_count, const char* reason) {
  if (!token(suite, 32) || !token(reason, 32)) return false;
  char fields[130];
  const int size =
      snprintf(fields, sizeof(fields), "%s,%" PRIu32 ",%s", suite, observed_count, reason);
  return formatted(size, sizeof(fields)) && emit("ABORT", fields);
}
