#include "core/SpiTrace.h"

namespace simulator {

SpiTraceError::SpiTraceError(SpiTraceErrorCode code, const char* message)
    : std::runtime_error(message), code_(code) {
}

SpiTrace::SpiTrace(std::size_t max_bytes, std::size_t max_events)
    : max_bytes_(max_bytes), max_events_(max_events) {
}

void SpiTrace::append(SpiEventKind kind, int dc, const uint8_t* bytes, std::size_t size) {
  if (size && !bytes) throw SpiTraceError(SpiTraceErrorCode::InvalidData, "null SPI data");
  if (size > max_bytes_ - byte_count_)
    throw SpiTraceError(SpiTraceErrorCode::ByteLimit, "SPI trace byte limit exceeded");
  if (events_.size() >= max_events_)
    throw SpiTraceError(SpiTraceErrorCode::EventLimit, "SPI trace event limit exceeded");
  SpiEvent event{kind, dc, std::vector<uint8_t>()};
  if (size) event.bytes.assign(bytes, bytes + size);
  events_.push_back(event);
  byte_count_ += size;
}

void SpiTrace::begin() {
  if (in_transaction_)
    throw SpiTraceError(SpiTraceErrorCode::InvalidTransaction, "nested SPI transaction");
  append(SpiEventKind::Begin, -1, nullptr, 0);
  in_transaction_ = true;
}

void SpiTrace::command(uint8_t value) {
  append(SpiEventKind::Command, 0, &value, 1);
}

void SpiTrace::data(const uint8_t* bytes, std::size_t size) {
  append(SpiEventKind::Data, 1, bytes, size);
}

void SpiTrace::end() {
  if (!in_transaction_)
    throw SpiTraceError(SpiTraceErrorCode::InvalidTransaction, "SPI end without begin");
  append(SpiEventKind::End, -1, nullptr, 0);
  in_transaction_ = false;
}

void SpiTrace::clear() noexcept {
  events_.clear();
  byte_count_ = 0;
  in_transaction_ = false;
}

}  // namespace simulator
