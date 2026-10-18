#include "SimulatorTransport.h"

namespace simulator {
namespace {
constexpr std::size_t index(SpiRegister::Id id) {
  return static_cast<std::size_t>(id);
}
}  // namespace

SimulatorTransport& host_spi() {
  static SimulatorTransport transport;
  return transport;
}

SimulatorTransport::SimulatorTransport() = default;

SpiRegister SimulatorTransport::reg(SpiRegister::Id id) {
  return SpiRegister(*this, id);
}

void SimulatorTransport::write(SpiRegister::Id id, uint32_t value) {
  if (id == SpiRegister::Id::Cmd) {
    registers_[index(id)] = value;
    transfer();
    registers_[index(id)] = 0;
    return;
  }
  registers_[index(id)] = value;
}

uint32_t SimulatorTransport::read(SpiRegister::Id id) const {
  if (id == SpiRegister::Id::Cmd) return 0;
  if (index(id) >= index(SpiRegister::Id::W0)) unsupported_read();
  return registers_[index(id)];
}

void SimulatorTransport::set_dc(bool data_mode) {
  data_mode_ = data_mode;
}

void SimulatorTransport::select(bool selected) {
  if (selected == selected_) return;
  if (selected)
    trace_.begin();
  else
    trace_.end();
  selected_ = selected;
}

void SimulatorTransport::unsupported_read() const {
  throw SpiTraceError(SpiTraceErrorCode::UnsupportedOperation,
                      "display readback is unsupported by the host transport");
}

void SimulatorTransport::unsupported_touch() const {
  throw SpiTraceError(SpiTraceErrorCode::UnsupportedOperation,
                      "touch SPI is outside the display simulator profile");
}

void SimulatorTransport::reset() {
  if (selected_) {
    trace_.clear();
    selected_ = false;
  } else {
    trace_.clear();
  }
  registers_.fill(0);
  data_mode_ = false;
}

void SimulatorTransport::transfer() {
  const uint32_t bits = ((registers_[index(SpiRegister::Id::U1)] >> 17) & 0x1FFu) + 1;
  if (bits % 8 != 0)
    throw SpiTraceError(SpiTraceErrorCode::UnsupportedOperation,
                        "non-byte-aligned SPI transfer is unsupported");
  const std::size_t count = (bits + 7) / 8;
  uint8_t bytes[64] = {};
  for (std::size_t n = 0; n < count; ++n) {
    const std::size_t word = n / 4;
    const unsigned shift = static_cast<unsigned>((n % 4) * 8);
    bytes[n] = static_cast<uint8_t>(registers_[index(SpiRegister::Id::W0) + word] >> shift);
  }
  if (data_mode_) {
    trace_.data(bytes, count);
  } else if (count == 1) {
    trace_.command(bytes[0]);
  } else {
    throw SpiTraceError(SpiTraceErrorCode::UnsupportedOperation,
                        "multi-byte command transfer is unsupported");
  }
}

SpiRegister SpiRegister::operator=(uint32_t value) {
  transport_->write(id_, value);
  return *this;
}

SpiRegister SpiRegister::operator|=(uint32_t value) {
  transport_->write(id_, transport_->read(id_) | value);
  return *this;
}

SpiRegister::operator uint32_t() const {
  return transport_->read(id_);
}

}  // namespace simulator
