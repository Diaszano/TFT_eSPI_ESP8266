#include <cassert>
#include "ValidationInput.h"

HostSerial Serial;

int main() {
  validation::ValidationCommand command;
  Serial.input = "B\r";
  assert(!validation_poll_command(&command));
  Serial.input += "\nQ\n";
  assert(validation_poll_command(&command));
  assert(command.kind == validation::ValidationCommandKind::Bench);
  assert(validation_poll_control(Serial, true) == validation::ControlAction::Quit);
  Serial.input += "N\nB\n";
  assert(validation_poll_control(Serial, true) == validation::ControlAction::Next);
  assert(validation_poll_control(Serial, false) == validation::ControlAction::Busy);
  assert(Serial.bytes == "BUSY\n");
}
