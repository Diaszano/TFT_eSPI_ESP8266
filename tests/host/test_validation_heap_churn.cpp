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
  assert(TFT_eSprite::seen_depth[1] && TFT_eSprite::seen_depth[4] &&
         TFT_eSprite::seen_depth[8] && TFT_eSprite::seen_depth[16]);
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
}
