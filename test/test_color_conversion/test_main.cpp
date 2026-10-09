#include <unity.h>

#include "internal/color_conversion.h"

using namespace tft_espi_internal;

void test_rgb888_boundaries() {
  TEST_ASSERT_EQUAL_HEX16(0x0000, rgb888_to_rgb565(0, 0, 0));
  TEST_ASSERT_EQUAL_HEX16(0xFFFF, rgb888_to_rgb565(255, 255, 255));
  TEST_ASSERT_EQUAL_HEX16(0xF800, rgb888_to_rgb565(255, 0, 0));
  TEST_ASSERT_EQUAL_HEX16(0x07E0, rgb888_to_rgb565(0, 255, 0));
  TEST_ASSERT_EQUAL_HEX16(0x001F, rgb888_to_rgb565(0, 0, 255));
  TEST_ASSERT_EQUAL_HEX16(0x0000, rgb888_to_rgb565(7, 3, 7));
  TEST_ASSERT_EQUAL_HEX16(0x0821, rgb888_to_rgb565(8, 4, 8));
}

void test_rgb565_truncation_boundaries() {
  TEST_ASSERT_EQUAL_UINT8(0x1F, rgb565_to_rgb332(0x07FF));
  TEST_ASSERT_EQUAL_UINT8(0xE0, rgb565_to_rgb332(0xF800));
  TEST_ASSERT_EQUAL_UINT8(0x1C, rgb565_to_rgb332(0x07E0));
  TEST_ASSERT_EQUAL_UINT8(0x03, rgb565_to_rgb332(0x001F));
  TEST_ASSERT_EQUAL_UINT8(0x01, rgb565_to_rgb332(0x0008));
}

void test_rgb332_all_expansions() {
  const uint8_t blue[4] = {0, 11, 21, 31};
  for (unsigned i = 0; i < 256; ++i) {
    const uint16_t r = static_cast<uint16_t>((i >> 5) & 7);
    const uint16_t g = static_cast<uint16_t>((i >> 2) & 7);
    const uint16_t expected =
        static_cast<uint16_t>((r << 13) | ((r >> 1) << 11) | (g << 8) | (g << 5) | blue[i & 3]);
    TEST_ASSERT_EQUAL_HEX16(expected, rgb332_to_rgb565(static_cast<uint8_t>(i)));
    TEST_ASSERT_EQUAL_UINT8(i, rgb565_to_rgb332(rgb332_to_rgb565(static_cast<uint8_t>(i))));
  }
  TEST_ASSERT_EQUAL_HEX16(0x000B, rgb332_to_rgb565(1));
  TEST_ASSERT_EQUAL_HEX16(0x0015, rgb332_to_rgb565(2));
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_rgb888_boundaries);
  RUN_TEST(test_rgb565_truncation_boundaries);
  RUN_TEST(test_rgb332_all_expansions);
  return UNITY_END();
}
