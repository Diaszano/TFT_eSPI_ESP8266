#include <cassert>
#include "ValidationSoak.h"
#include "ValidationInput.h"

HostSerial Serial;
HostESP ESP;
int TFT_eSprite::create_calls = 0;
int TFT_eSprite::delete_calls = 0;
int TFT_eSprite::fail_at = -1;
uint8_t TFT_eSprite::last_depth = 0;
bool TFT_eSprite::seen_depth[17] = {};

int main() {
  TFT_eSPI display;
  Print output;
  host_yield_step_value() = 60000;
  validation::run_mixed_soak(30, display, output);
  assert(output.bytes.find("END,FM,30,1800000000,PASS,") != std::string::npos);
  assert(TFT_eSprite::create_calls == TFT_eSprite::delete_calls);
  Print long_output;
  host_millis_value() = 0;
  validation::run_mixed_soak(480, display, long_output);
  assert(long_output.bytes.find(",28800000000,PASS,") != std::string::npos);
  Print extended_output;
  host_millis_value() = 0;
  validation::run_mixed_soak(1440, display, extended_output);
  assert(extended_output.bytes.find(",86400000000,PASS,") != std::string::npos);
  Print wrapped_output;
  host_millis_value() = 0xffff0000UL;
  validation::run_mixed_soak(30, display, wrapped_output);
  assert(wrapped_output.bytes.find(",1800000000,PASS,") != std::string::npos);
  host_millis_value() = 0;
  Serial.input = "Q\n";
  Serial.position = 0;
  Print cancelled;
  validation::run_mixed_soak(30, display, cancelled);
  assert(cancelled.bytes.find("ABORT,FM,1,Q,") != std::string::npos);
  assert(TFT_eSprite::create_calls == TFT_eSprite::delete_calls);
  host_millis_value() = 0;
  Serial.input = "Q\n";
  Serial.position = 0;
  Serial.available_calls = 0;
  Serial.suppress_until = 127;
  host_yield_step_value() = 1000;
  Print late_cancelled;
  validation::run_mixed_soak(30, display, late_cancelled);
  assert(late_cancelled.bytes.find("ABORT,FM,128,Q,") != std::string::npos);
  Serial.suppress_until = 0;
  host_yield_step_value() = 60000;

  Print wifi_off_output;
  host_wifi_mode_value() = "off";
  validation::run_wifi_latency(display, wifi_off_output);
  assert(wifi_off_output.bytes.find("BEGIN,LW,324508639,1000,lw_off,") != std::string::npos);
  assert(wifi_off_output.bytes.find("END,LW,1000,") != std::string::npos);
  assert(wifi_off_output.bytes.find(",PASS,") != std::string::npos);
  assert(TFT_eSprite::create_calls == TFT_eSprite::delete_calls);

  Print wifi_sta_output;
  host_wifi_mode_value() = "sta";
  validation::run_wifi_latency(display, wifi_sta_output);
  assert(wifi_sta_output.bytes.find("BEGIN,LW,324508639,1000,lw_sta,") != std::string::npos);
  assert(wifi_sta_output.bytes.find("END,LW,1000,") != std::string::npos);

  Serial.input = "Q\n";
  Serial.position = 0;
  Serial.available_calls = 0;
  Print wifi_cancelled;
  validation::run_wifi_latency(display, wifi_cancelled);
  assert(wifi_cancelled.bytes.find("ABORT,LW,1,Q,") != std::string::npos);
  assert(TFT_eSprite::create_calls == TFT_eSprite::delete_calls);
}
