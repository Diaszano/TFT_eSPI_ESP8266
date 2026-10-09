#include <ESP8266WiFi.h>
#include <sys/time.h>
#include <time.h>

void syncTime(void) {
  static bool configured = false;
  static uint32_t lastUpdate = millis();
  const uint32_t current = millis();
  const uint32_t elapsed = current - lastUpdate;
  lastUpdate = current;
  time_secs += elapsed / 1000.0f;
  while (time_secs >= 86400.0f) time_secs -= 86400.0f;

  if (!configured) {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    configTime("GMT0BST,M3.5.0/1,M10.5.0/2", "pool.ntp.org");
    configured = true;
  }
  if (WiFi.status() != WL_CONNECTED) return;

  timeval now;
  if (gettimeofday(&now, nullptr) != 0 || now.tv_sec <= 1700000000) return;
  tm localTime;
  if (localtime_r(&now.tv_sec, &localTime) == nullptr) return;
  time_secs = localTime.tm_hour * 3600 + localTime.tm_min * 60 + localTime.tm_sec +
              now.tv_usec / 1000000.0f;
}
