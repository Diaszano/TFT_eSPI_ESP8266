#include "ValidationInput.h"

bool validation_poll_command(validation::ValidationCommand* out) {
  static validation::ValidationCommandReader reader;
  while (Serial.available()) {
    if (reader.consume(static_cast<char>(Serial.read()), out)) return true;
  }
  return false;
}

validation::ControlAction validation_poll_control(Print& log, bool allow_next) {
  validation::ValidationCommand command;
  if (!validation_poll_command(&command)) return validation::ControlAction::None;
  const validation::ControlAction action = validation::control_action(command, allow_next);
  if (action == validation::ControlAction::Busy) log.println("BUSY");
  return action;
}
