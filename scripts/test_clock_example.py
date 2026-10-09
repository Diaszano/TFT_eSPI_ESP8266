import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class ClockExampleTests(unittest.TestCase):
    def test_clock_stays_live_offline_and_preserves_fraction(self):
        compiler = shutil.which("c++")
        self.assertIsNotNone(compiler, "C++ compiler required")
        header = (ROOT / "examples/Anti-aliased_Clock/NTP_Time.h").read_text()
        header = "\n".join(line for line in header.splitlines() if not line.startswith("#include"))
        source = r"""
#include <cassert>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <sys/time.h>
static uint32_t tick = 0xfffffff0u;
static int begins = 0, configs = 0, statusValue = 0;
static bool validTime = false;
static timeval supplied = {1700000001, 250000};
uint32_t millis() { return tick; }
constexpr int WL_CONNECTED = 3;
#define WIFI_SSID "test"
#define WIFI_PASSWORD "test"
struct Wifi {
  void begin(const char*, const char*) { ++begins; }
  int status() const { return statusValue; }
} WiFi;
void configTime(const char*, const char*) { ++configs; }
int clock_gettimeofday(timeval* now, void*) {
  if (!validTime) return -1;
  *now = supplied;
  return 0;
}
tm* clock_localtime(const time_t* value, tm* result) {
  *result = {};
  const time_t day = *value % 86400;
  result->tm_hour = day / 3600;
  result->tm_min = day / 60 % 60;
  result->tm_sec = day % 60;
  return result;
}
void delay(uint32_t) { assert(false && "blocking delay"); }
time_t clock_time(time_t*) { return supplied.tv_sec; }
#define time clock_time
#define gettimeofday clock_gettimeofday
#define localtime_r clock_localtime
float time_secs = 86399.875f;
""" + header + r"""
int main() {
  syncTime();
  assert(begins == 1 && configs == 1);
  tick += 250;
  syncTime();
  assert(std::fabs(time_secs - 0.125f) < 0.02f);
  assert(begins == 1 && configs == 1);
  statusValue = WL_CONNECTED;
  validTime = true;
  syncTime();
  const float first = time_secs;
  supplied.tv_usec = 750000;
  tick += 500;
  syncTime();
  assert(std::fabs(time_secs - first - 0.5f) < 0.02f);
  validTime = false;
  tick += 100;
  const float before = time_secs;
  syncTime();
  assert(time_secs > before);
  uint32_t target = 0xfffffff0u;
  uint32_t now = 0x10u;
  assert(static_cast<int32_t>(now - target) >= 0);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            cpp = pathlib.Path(directory) / "clock.cpp"
            binary = pathlib.Path(directory) / "clock"
            cpp.write_text(source)
            subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
