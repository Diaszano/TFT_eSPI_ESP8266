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
}
