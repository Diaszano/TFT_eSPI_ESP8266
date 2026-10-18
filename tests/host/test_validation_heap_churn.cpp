#include <cassert>
#include "ValidationMemoryMath.h"
#include "ValidationMemoryExtended.h"
#include "ValidationInput.h"

HostSerial Serial;
HostESP ESP;
int TFT_eSprite::create_calls = 0;
int TFT_eSprite::delete_calls = 0;
int TFT_eSprite::fail_at = -1;
uint8_t TFT_eSprite::last_depth = 0;
bool TFT_eSprite::seen_depth[17] = {};

int main() {
  uint16_t fragmentation = 0;
  assert(!validation::fragmentation_permille(0, 0, &fragmentation));
  assert(!validation::fragmentation_permille(100, 101, &fragmentation));
  assert(validation::fragmentation_permille(20000, 15000, &fragmentation));
  assert(fragmentation == 250);
  assert(!validation::may_allocate(20000, 15000, 7712));
  assert(validation::may_allocate(20000, 15000, 7711));
  assert(!validation::may_allocate(20000, 1000, 1001));
  uint32_t bytes = 0;
  assert(validation::estimate_sprite_bytes(32, 32, 16, &bytes));
  assert(bytes >= 2048);
  assert(!validation::estimate_sprite_bytes(65535, 65535, 16, &bytes));
  assert(!validation::estimate_sprite_bytes(0, 32, 16, &bytes));
  TFT_eSPI display;
  Print output;
  validation::run_heap_churn(display, output);
  assert(TFT_eSprite::create_calls == 100000);
  assert(TFT_eSprite::delete_calls == 100000);
  assert(TFT_eSprite::seen_depth[1] && TFT_eSprite::seen_depth[4] && TFT_eSprite::seen_depth[8] &&
         TFT_eSprite::seen_depth[16]);
  assert(output.bytes.find("END,HC,100000,") != std::string::npos);
  TFT_eSprite::create_calls = TFT_eSprite::delete_calls = 0;
  TFT_eSprite::fail_at = 100;
  Print failed;
  validation::run_heap_churn(display, failed);
  assert(TFT_eSprite::create_calls == 100);
  assert(TFT_eSprite::delete_calls == 99);
  assert(failed.bytes.find("ABORT,HC,99,ALLOC_FAIL,") != std::string::npos);
  TFT_eSprite::create_calls = TFT_eSprite::delete_calls = 0;
  TFT_eSprite::fail_at = -1;
  Serial.input = "Q\n";
  Serial.position = 0;
  Print cancelled;
  validation::run_heap_churn(display, cancelled);
  assert(TFT_eSprite::create_calls == 128);
  assert(TFT_eSprite::delete_calls == 128);
  assert(cancelled.bytes.find("ABORT,HC,128,Q,") != std::string::npos);
  Serial.input.clear();
  Serial.position = 0;
  TFT_eSprite::create_calls = TFT_eSprite::delete_calls = 0;
  Print pressure;
  validation::run_heap_pressure(display, pressure);
  assert(TFT_eSprite::create_calls == 5);
  assert(TFT_eSprite::delete_calls == 5);
  assert(pressure.bytes.find("END,HP,4,") != std::string::npos);
  for (int failure_at : {1, 2, 4}) {
    TFT_eSprite::create_calls = TFT_eSprite::delete_calls = 0;
    TFT_eSprite::fail_at = failure_at;
    Print pressure_failure;
    validation::run_heap_pressure(display, pressure_failure);
    assert(TFT_eSprite::delete_calls == failure_at);
    assert(pressure_failure.bytes.find("ALLOC_FAIL_RECOVERED") != std::string::npos);
  }
  TFT_eSprite::fail_at = -1;
  TFT_eSprite::create_calls = TFT_eSprite::delete_calls = 0;
  Serial.input = "Q\n";
  Serial.position = 0;
  Print pressure_cancelled;
  validation::run_heap_pressure(display, pressure_cancelled);
  assert(TFT_eSprite::delete_calls == 2);
  assert(pressure_cancelled.bytes.find("ABORT,HP,1,Q,") != std::string::npos);
  Serial.input.clear();
  Serial.position = 0;
  ESP.free_heap = 12288;
  Print pressure_skip;
  validation::run_heap_pressure(display, pressure_skip);
  assert(pressure_skip.bytes.find("END,HP,0,0,SKIP,") != std::string::npos);
}
