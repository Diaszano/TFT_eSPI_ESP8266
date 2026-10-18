#pragma once

#include "core/SpiTrace.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace simulator {

class SimulatorTransport;

class SpiRegister {
 public:
  enum class Id {
    U,
    U1,
    Cmd,
    W0,
    W1,
    W2,
    W3,
    W4,
    W5,
    W6,
    W7,
    W8,
    W9,
    W10,
    W11,
    W12,
    W13,
    W14,
    W15
  };
  SpiRegister(SimulatorTransport& transport, Id id) : transport_(&transport), id_(id) {}
  SpiRegister operator=(uint32_t value);
  SpiRegister operator|=(uint32_t value);
  operator uint32_t() const;

 private:
  SimulatorTransport* transport_;
  Id id_;
};

class SimulatorTransport {
 public:
  SimulatorTransport();
  SpiRegister reg(SpiRegister::Id id);
  void write(SpiRegister::Id id, uint32_t value);
  uint32_t read(SpiRegister::Id id) const;
  void set_dc(bool data_mode);
  void select(bool selected);
  void unsupported_read() const;
  void unsupported_touch() const;
  void reset();
  SpiTrace& trace() noexcept { return trace_; }
  const SpiTrace& trace() const noexcept { return trace_; }

 private:
  void transfer();
  std::array<uint32_t, 19> registers_{};
  SpiTrace trace_{4 * 1024 * 1024, 100000};
  bool data_mode_ = false;
  bool selected_ = false;
};

SimulatorTransport& host_spi();

}  // namespace simulator
