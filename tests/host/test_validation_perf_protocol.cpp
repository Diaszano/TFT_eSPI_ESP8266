#include <cassert>
#include <cstdint>
#include "ValidationPerfTelemetry.h"

int main() {
  assert(validation_perf_crc32("123456789", 9) == 0xcbf43926UL);
  Print out;
  ValidationPerfEmitter emitter(out, "run42");
  assert(emitter.begin("TI", 0, 16, "sentinel"));
  const uint32_t samples[] = {1, 0x12345678};
  assert(emitter.samples("TI", 0, 0, samples, 2));
  assert(emitter.mem("TI", 1, 40000, 30000, 39000, 0));
  assert(emitter.end("TI", 2, 1000, "PASS"));
  assert(out.bytes ==
         "PERF,1,run42,0,BEGIN,TI,0,16,sentinel,667cb70d\n"
         "PERF,1,run42,1,SAMPLES,TI,0,0,2,AQAAAHhWNBI=,d6bd2315\n"
         "PERF,1,run42,2,MEM,TI,1,40000,30000,39000,0,21a51298\n"
         "PERF,1,run42,3,END,TI,2,1000,PASS,0e2d27f2\n");
  assert(!emitter.begin("bad,token", 0, 1, "x"));
  assert(!emitter.samples("TI", 0, 0, samples, 0));
  assert(out.bytes.back() == '\n');
  Print aborted;
  ValidationPerfEmitter aborted_emitter(aborted, "run43");
  assert(aborted_emitter.abort("TI", 0, "Q"));
  assert(aborted.bytes.find("PERF,1,run43,0,ABORT,TI,0,Q,") == 0);
  Print maximum;
  ValidationPerfEmitter maximum_emitter(maximum, "abcdefghijklmnop");
  uint32_t sixteen[16] = {};
  assert(maximum_emitter.samples("FP1", 0, 0, sixteen, 16));
  assert(maximum.bytes.size() <= 192);
}
