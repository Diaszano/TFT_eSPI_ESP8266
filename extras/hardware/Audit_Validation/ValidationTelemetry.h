#ifndef VALIDATION_TELEMETRY_H
#define VALIDATION_TELEMETRY_H

#include <Print.h>
#include <stdint.h>

void validation_emit_run(Print& out);
void validation_emit_case_start(Print& out, const char* id, uint32_t seed);
void validation_emit_case_return(Print& out, const char* id, uint32_t duration_us,
                                 const char* status);

#endif
