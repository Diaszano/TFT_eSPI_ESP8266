#include <cassert>
#include "ValidationFramePerf.h"
#include "ValidationInput.h"

HostSerial Serial;
HostESP ESP;

int main() {
  TFT_eSPI display;
  TFT_eSprite sprite(&display);
  Print output;
  validation::run_frame_perf(validation::FrameSuite::Full, display, sprite, output);
  assert(display.rows == 240 * 1001);
  assert(display.payload_pixels == 57600 * 1001);
  assert(display.windows == 1001);
  assert(display.fills == 1001);
  assert(display.first_pixel == 0);
  assert(display.last_pixel != display.first_pixel);
  assert(output.bytes.find("BEGIN,FP1,") != std::string::npos);
  assert(output.bytes.find("END,FP1,1000,") != std::string::npos);
  TFT_eSPI cancelled_display;
  Print cancelled_output;
  Serial.input = "Q\n";
  Serial.position = 0;
  validation::run_frame_perf(validation::FrameSuite::Full, cancelled_display,
                             sprite, cancelled_output);
  assert(cancelled_display.rows == 240);
  assert(cancelled_output.bytes.find("ABORT,FP1,1,Q,") != std::string::npos);
  Serial.input.clear();
  Serial.position = 0;
  TFT_eSPI partial;
  Print partial_output;
  validation::run_frame_perf(validation::FrameSuite::Partial, partial, sprite,
                             partial_output);
  assert(partial.windows == 12 * 1001);
  assert(partial.rows == 560 * 1001);
  assert(partial.payload_pixels == 44064 * 1001);
  assert(partial.bad_windows == 0);
  assert(partial_output.bytes.find("fp2_120_clip") != std::string::npos);
  TFT_eSPI mixed;
  Print mixed_output;
  validation::run_frame_perf(validation::FrameSuite::Mixed, mixed, sprite,
                             mixed_output);
  assert(mixed.strings == 2 * 1001);
  assert(mixed.images == 1001);
  assert(sprite.pushes == 1001);
  assert(sprite.min_x >= 40 && sprite.max_x <= 199);
  assert(sprite.min_x != sprite.max_x);
  TFT_eSPI replay_display;
  TFT_eSprite replay_sprite(&replay_display);
  Print replay_output;
  validation::run_frame_perf(validation::FrameSuite::Mixed, replay_display,
                             replay_sprite, replay_output);
  assert(replay_sprite.positions == sprite.positions);
  assert(mixed_output.bytes.find("END,FP3,1000,") != std::string::npos);
  assert(mixed.font == 1 && !mixed.swap_bytes);
  sprite.available = false;
  Print skipped;
  validation::run_frame_perf(validation::FrameSuite::Mixed, mixed, sprite, skipped);
  assert(skipped.bytes.find("END,FP3,0,0,SKIP,") != std::string::npos);
  assert(skipped.bytes.find("PASS") == std::string::npos);
}
