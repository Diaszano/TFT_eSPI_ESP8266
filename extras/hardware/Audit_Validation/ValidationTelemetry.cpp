#include "ValidationTelemetry.h"

#include <Arduino.h>
#include <TFT_eSPI.h>

#ifndef VALIDATION_GIT_SHA
#define VALIDATION_GIT_SHA "unknown"
#endif
#ifndef TFT_WIDTH
#define TFT_WIDTH 0
#endif
#ifndef TFT_HEIGHT
#define TFT_HEIGHT 0
#endif
#ifndef SPI_FREQUENCY
#define SPI_FREQUENCY 0
#endif

#if defined(ESP8266)
extern "C" {
#include <user_interface.h>
}
#endif

const char* validation_wifi_mode() {
#if defined(ESP8266)
  const uint8_t mode = wifi_get_opmode();
  if (mode == 0) return "off";
  if (mode == 1) {
    if (wifi_station_get_connect_status() == 5) return "sta";
    return "on";
  }
  if (mode == 2 || mode == 3) return "ap";
  return "unknown";
#else
  return host_wifi_mode_value();
#endif
}

void validation_emit_run(Print& out) {
  out.print("RUN,");
  out.print(millis());
  out.print(',');
  out.print(VALIDATION_GIT_SHA);
  out.print(",nodemcuv2,");
#if defined(ST7789_DRIVER)
  out.print("ST7789,");
#else
  out.print("unknown,");
#endif
  out.print(TFT_WIDTH);
  out.print(',');
  out.print(TFT_HEIGHT);
  out.print(",0,");
  out.print(ESP.getCpuFreqMHz() * 1000000UL);
  out.print(',');
  out.print(SPI_FREQUENCY);
  out.print(',');
  out.print(validation_wifi_mode());
  out.print(',');
#if defined(VALIDATION_DIRTY_TREE) && VALIDATION_DIRTY_TREE
  out.print("dirty,");
#else
  out.print("default,");
#endif
  out.print(ESP.getResetReason());
  out.print(',');
  out.print(ESP.getFreeHeap());
  out.print(',');
  out.println(ESP.getMaxFreeBlockSize());
}

void validation_emit_case_start(Print& out, const char* id, uint32_t seed) {
  out.print("CASE,START,");
  out.print(id);
  out.print(',');
  out.println(seed);
}

void validation_emit_case_return(Print& out, const char* id, uint32_t duration_us,
                                 const char* status) {
  out.print("CASE,RETURN,");
  out.print(id);
  out.print(',');
  out.print(duration_us);
  out.print(',');
  out.print(ESP.getFreeHeap());
  out.print(',');
  out.print(ESP.getMaxFreeBlockSize());
  out.print(',');
  out.println(status);
}
