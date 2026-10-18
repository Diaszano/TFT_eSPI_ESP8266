#ifndef VALIDATION_INPUT_H
#define VALIDATION_INPUT_H

#include <Arduino.h>
#include "ValidationCommand.h"

bool validation_poll_command(validation::ValidationCommand* out);
validation::ControlAction validation_poll_control(Print& log, bool allow_next);

#endif
