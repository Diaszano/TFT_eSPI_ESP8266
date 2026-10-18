#pragma once

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace simulator {

enum class SpiTraceErrorCode {
  ByteLimit,
  EventLimit,
  InvalidTransaction,
  InvalidData,
  UnsupportedOperation
};

class SpiTraceError : public std::runtime_error {
 public:
  SpiTraceError(SpiTraceErrorCode code, const char* message);
  SpiTraceErrorCode code() const noexcept { return code_; }

 private:
  SpiTraceErrorCode code_;
};

enum class SpiEventKind { Begin, Command, Data, End };

struct SpiEvent {
  SpiEventKind kind;
  int dc;
  std::vector<uint8_t> bytes;
};

class SpiTrace {
 public:
  SpiTrace(std::size_t max_bytes, std::size_t max_events);

  void begin();
  void command(uint8_t value);
  void data(const uint8_t* bytes, std::size_t size);
  void end();
  void clear() noexcept;

  const std::vector<SpiEvent>& events() const noexcept { return events_; }
  std::size_t byte_count() const noexcept { return byte_count_; }

 private:
  void append(SpiEventKind kind, int dc, const uint8_t* bytes, std::size_t size);

  const std::size_t max_bytes_;
  const std::size_t max_events_;
  std::size_t byte_count_ = 0;
  bool in_transaction_ = false;
  std::vector<SpiEvent> events_;
};

}  // namespace simulator
