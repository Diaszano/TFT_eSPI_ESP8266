#include <cassert>
#include "ValidationCommand.h"

int main() {
  using validation::ValidationCommandKind;
  assert(validation::parse_validation_command("?").kind == ValidationCommandKind::Menu);
  assert(validation::parse_validation_command("B").kind == ValidationCommandKind::Bench);
  assert(validation::parse_validation_command("S").kind == ValidationCommandKind::Visual);
  assert(validation::parse_validation_command("S3").visual_case == 3);
  assert(validation::parse_validation_command("S4").visual_case == 4);
  assert(validation::parse_validation_command("L").kind == ValidationCommandKind::Stress);
  assert(validation::parse_validation_command("M").kind == ValidationCommandKind::Memory);
  assert(validation::parse_validation_command("E30").kind == ValidationCommandKind::Endurance30);
  assert(validation::parse_validation_command("X").kind == ValidationCommandKind::Extremes);
  for (uint8_t rotation = 0; rotation < 4; ++rotation) {
    char input[] = {'R', static_cast<char>('0' + rotation), '\0'};
    const validation::ValidationCommand parsed = validation::parse_validation_command(input);
    assert(parsed.kind == ValidationCommandKind::Rotation);
    assert(parsed.rotation == rotation);
  }
  assert(validation::parse_validation_command("R4").kind == ValidationCommandKind::Unknown);
  assert(validation::parse_validation_command("R10").kind == ValidationCommandKind::Unknown);
  assert(validation::parse_validation_command("N").kind == ValidationCommandKind::Next);
  assert(validation::parse_validation_command("Q").kind == ValidationCommandKind::Quit);
  assert(validation::parse_validation_command("TI").kind ==
         ValidationCommandKind::TelemetryIntegrity);
  assert(validation::parse_validation_command("FP1").kind == ValidationCommandKind::FrameFull);
  assert(validation::parse_validation_command("FP2").kind == ValidationCommandKind::FramePartial);
  assert(validation::parse_validation_command("FP3").kind == ValidationCommandKind::FrameMixed);
  assert(validation::parse_validation_command("HC").kind == ValidationCommandKind::HeapChurn);
  assert(validation::parse_validation_command("HP").kind == ValidationCommandKind::HeapPressure);
  assert(validation::parse_validation_command("FM").kind ==
         ValidationCommandKind::FrameMixedLong30);
  assert(validation::parse_validation_command("FM8H").kind ==
         ValidationCommandKind::FrameMixedLong8H);
  assert(validation::parse_validation_command("FM24H").kind ==
         ValidationCommandKind::FrameMixedLong24H);
  assert(validation::parse_validation_command("LW").kind == ValidationCommandKind::LatencyWifi);
  assert(validation::parse_validation_command("S5").kind == ValidationCommandKind::Unknown);
  assert(validation::parse_validation_command("b").kind == ValidationCommandKind::Unknown);
  assert(validation::parse_validation_command("Bextra").kind == ValidationCommandKind::Unknown);
  assert(validation::parse_validation_command(" ").kind == ValidationCommandKind::Unknown);
  assert(validation::parse_validation_command("\r\n").kind == ValidationCommandKind::Unknown);
  assert(validation::parse_validation_command(nullptr).kind == ValidationCommandKind::Unknown);

  validation::ValidationCommandReader reader;
  validation::ValidationCommand command = {ValidationCommandKind::Unknown, 0, 0};
  bool complete = false;
  const char crlf[] = "B\r\n";
  for (char ch : crlf)
    if (ch) complete = reader.consume(ch, &command) || complete;
  assert(complete && command.kind == ValidationCommandKind::Bench);
  const char tooLong[] = "1234567890123456\nB\n";
  unsigned completed = 0;
  for (char ch : tooLong) {
    if (ch && reader.consume(ch, &command)) {
      ++completed;
      if (completed == 1) assert(command.kind == ValidationCommandKind::Unknown);
    }
  }
  assert(completed == 2 && command.kind == ValidationCommandKind::Bench);
  const char embeddedNul[] = {'B', '\0', '\n'};
  reader.consume(embeddedNul[0], &command);
  reader.consume(embeddedNul[1], &command);
  assert(reader.consume(embeddedNul[2], &command));
  assert(command.kind == ValidationCommandKind::Unknown);
  assert(validation::control_action({ValidationCommandKind::Next, 0, 0}, true) ==
         validation::ControlAction::Next);
  assert(validation::control_action({ValidationCommandKind::Next, 0, 0}, false) ==
         validation::ControlAction::Busy);
  assert(validation::control_action({ValidationCommandKind::Quit, 0, 0}, false) ==
         validation::ControlAction::Quit);
  assert(validation::control_action({ValidationCommandKind::Bench, 0, 0}, true) ==
         validation::ControlAction::Busy);
}
