#include <ESP8266WiFi.h>
#include <time.h>

void syncTime(void) {
  static bool configured = false;

  if (!configured) {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    configTime("GMT0BST,M3.5.0/1,M10.5.0/2", "pool.ntp.org");
    configured = true;
  }

  const time_t now = time(nullptr);
  if (now > 1700000000) {
    struct tm localTime;
    localtime_r(&now, &localTime);
    time_secs =
        localTime.tm_hour * 3600 + localTime.tm_min * 60 + localTime.tm_sec;
  }
}
