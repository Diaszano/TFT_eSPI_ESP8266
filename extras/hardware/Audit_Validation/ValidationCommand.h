#ifndef VALIDATION_COMMAND_H
#define VALIDATION_COMMAND_H

#include <stdint.h>
#include <string.h>

namespace validation {

enum class ValidationCommandKind : uint8_t {
  Menu,
  Bench,
  Visual,
  Stress,
  Memory,
  Endurance30,
  Extremes,
  Rotation,
  Next,
  Quit,
  TelemetryIntegrity,
  FrameFull,
  FramePartial,
  FrameMixed,
  HeapChurn,
  Unknown
};

enum class ControlAction : uint8_t { None, Next, Quit, Busy };

struct ValidationCommand {
  ValidationCommandKind kind;
  uint8_t visual_case;
  uint8_t rotation;
};

inline ControlAction control_action(ValidationCommand command, bool allow_next) {
  if (command.kind == ValidationCommandKind::Quit) return ControlAction::Quit;
  if (allow_next && command.kind == ValidationCommandKind::Next) return ControlAction::Next;
  return ControlAction::Busy;
}

inline ValidationCommand parse_validation_command(const char* line);

struct ValidationCommandReader {
  char line[16] = {};
  uint8_t length = 0;
  bool invalid = false;

  bool consume(char input, ValidationCommand* command) {
    const uint8_t ch = static_cast<uint8_t>(input);
    if (ch == '\r') return false;
    if (ch == '\n') {
      line[length] = '\0';
      *command = invalid ? ValidationCommand{ValidationCommandKind::Unknown, 0, 0}
                         : parse_validation_command(line);
      length = 0;
      invalid = false;
      return true;
    }
    if (ch < 32 || ch > 126 || length >= sizeof(line) - 1) {
      invalid = true;
      return false;
    }
    if (!invalid) line[length++] = static_cast<char>(ch);
    return false;
  }
};

inline ValidationCommand parse_validation_command(const char* line) {
  ValidationCommand command = {ValidationCommandKind::Unknown, 0, 0};
  if (!line) return command;

  if (strcmp(line, "?") == 0)
    command.kind = ValidationCommandKind::Menu;
  else if (strcmp(line, "B") == 0)
    command.kind = ValidationCommandKind::Bench;
  else if (strcmp(line, "S") == 0)
    command.kind = ValidationCommandKind::Visual;
  else if (line[0] == 'S' && line[1] >= '1' && line[1] <= '4' && line[2] == '\0') {
    command.kind = ValidationCommandKind::Visual;
    command.visual_case = static_cast<uint8_t>(line[1] - '0');
  } else if (strcmp(line, "L") == 0)
    command.kind = ValidationCommandKind::Stress;
  else if (strcmp(line, "M") == 0)
    command.kind = ValidationCommandKind::Memory;
  else if (strcmp(line, "E30") == 0)
    command.kind = ValidationCommandKind::Endurance30;
  else if (strcmp(line, "X") == 0)
    command.kind = ValidationCommandKind::Extremes;
  else if (line[0] == 'R' && line[1] >= '0' && line[1] <= '3' && line[2] == '\0') {
    command.kind = ValidationCommandKind::Rotation;
    command.rotation = static_cast<uint8_t>(line[1] - '0');
  } else if (strcmp(line, "N") == 0)
    command.kind = ValidationCommandKind::Next;
  else if (strcmp(line, "Q") == 0)
    command.kind = ValidationCommandKind::Quit;
  else if (strcmp(line, "TI") == 0)
    command.kind = ValidationCommandKind::TelemetryIntegrity;
  else if (strcmp(line, "FP1") == 0)
    command.kind = ValidationCommandKind::FrameFull;
  else if (strcmp(line, "FP2") == 0)
    command.kind = ValidationCommandKind::FramePartial;
  else if (strcmp(line, "FP3") == 0)
    command.kind = ValidationCommandKind::FrameMixed;
  else if (strcmp(line, "HC") == 0)
    command.kind = ValidationCommandKind::HeapChurn;
  return command;
}

}  // namespace validation

#endif
