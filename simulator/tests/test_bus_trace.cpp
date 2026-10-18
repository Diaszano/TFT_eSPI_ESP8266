#include "core/SpiTrace.h"

#include <cassert>
#include <cstdint>

int main() {
  simulator::SpiTrace trace(128, 8);
  trace.begin();
  trace.command(0x2A);
  const uint8_t range[] = {0, 0, 0, 1};
  trace.data(range, sizeof(range));
  trace.end();
  const auto& events = trace.events();
  assert(events.size() == 4);
  assert(events[0].kind == simulator::SpiEventKind::Begin);
  assert(events[1].dc == 0 && events[1].bytes[0] == 0x2A);
  assert(events[2].dc == 1 && events[2].bytes[3] == 1);
  assert(events[3].kind == simulator::SpiEventKind::End);

  simulator::SpiTrace bounded(3, 4);
  bool rejected = false;
  try {
    bounded.data(range, sizeof(range));
  } catch (const simulator::SpiTraceError& error) {
    rejected = error.code() == simulator::SpiTraceErrorCode::ByteLimit;
  }
  assert(rejected);

  simulator::SpiTrace event_bounded(8, 1);
  event_bounded.command(0x2A);
  rejected = false;
  try {
    event_bounded.data(range, 1);
  } catch (const simulator::SpiTraceError& error) {
    rejected = error.code() == simulator::SpiTraceErrorCode::EventLimit;
  }
  assert(rejected);
}
