#include "core/St7789VirtualController.h"

#include <cassert>
#include <cstdint>
#include <cstdio>

int main() {
  const uint16_t pattern[] = {0xF800, 0x07E0, 0x001F, 0xFFFF, 0x1234, 0x5678, 0x9ABC, 0xDEF0,
                              0x1357, 0x2468, 0x369C, 0xABCD, 0x0F0F, 0xF0F0, 0x55AA, 0xAA55};
  const uint8_t madctl[] = {0x00, 0x60, 0xC0, 0xA0};
  const uint16_t expected[][4] = {{0xF800, 0x07E0, 0x001F, 0xFFFF},
                                  {0xFFFF, 0xDEF0, 0xABCD, 0xAA55},
                                  {0xAA55, 0x55AA, 0xF0F0, 0x0F0F},
                                  {0x0F0F, 0x1357, 0x1234, 0xF800}};
  for (unsigned rotation = 0; rotation < 4; ++rotation) {
    simulator::St7789VirtualController lcd(simulator::Profile::test(4, 4));
    lcd.command(0x36);
    lcd.data(&madctl[rotation], 1);
    lcd.command(0x2A);
    const uint8_t columns[] = {0, 0, 0, 3};
    lcd.data(columns, sizeof(columns));
    lcd.command(0x2B);
    const uint8_t rows[] = {0, 0, 0, 3};
    lcd.data(rows, sizeof(rows));
    lcd.begin();
    lcd.command(0x2C);
    uint8_t bytes[sizeof(pattern)];
    for (unsigned i = 0; i < 16; ++i) {
      bytes[i * 2] = static_cast<uint8_t>(pattern[i] >> 8);
      bytes[i * 2 + 1] = static_cast<uint8_t>(pattern[i]);
    }
    lcd.data(bytes, sizeof(bytes));
    lcd.end();
    if (rotation == 0) assert(lcd.raw_gram_pixel(0, 0) == pattern[0]);
    for (unsigned x = 0; x < 4; ++x) {
      const uint16_t actual = lcd.visible_pixel(x, 0);
      if (actual != expected[rotation][x])
        std::fprintf(stderr, "rotation=%u x=%u expected=%04X actual=%04X\n", rotation, x,
                     expected[rotation][x], actual);
      assert(actual == expected[rotation][x]);
    }
  }

  simulator::St7789VirtualController transposed(simulator::Profile::nodemcu_st7789_240x240());
  const uint8_t mv = 0x20;
  transposed.command(0x36);
  transposed.data(&mv, 1);
  transposed.command(0x2A);
  const uint8_t transposed_columns[] = {0, 0, 0, 1};
  transposed.data(transposed_columns, sizeof(transposed_columns));
  transposed.command(0x2B);
  const uint8_t transposed_rows[] = {0, 0, 0, 2};
  transposed.data(transposed_rows, sizeof(transposed_rows));
  transposed.begin();
  transposed.command(0x2C);
  const uint16_t transposed_pattern[] = {0xF800, 0x07E0, 0x001F, 0xFFFF, 0x1234, 0x5678};
  uint8_t transposed_bytes[sizeof(transposed_pattern)];
  for (unsigned i = 0; i < 6; ++i) {
    transposed_bytes[i * 2] = static_cast<uint8_t>(transposed_pattern[i] >> 8);
    transposed_bytes[i * 2 + 1] = static_cast<uint8_t>(transposed_pattern[i]);
  }
  transposed.data(transposed_bytes, sizeof(transposed_bytes));
  transposed.end();
  assert(transposed.gram(0, 0) == transposed_pattern[0]);
  assert(transposed.gram(1, 0) == transposed_pattern[1]);
  assert(transposed.gram(2, 0) == transposed_pattern[2]);
  assert(transposed.gram(0, 1) == transposed_pattern[3]);
  assert(transposed.gram(1, 1) == transposed_pattern[4]);
  assert(transposed.gram(2, 1) == transposed_pattern[5]);

  transposed.reset();
  transposed.command(0x36);
  transposed.data(&mv, 1);
  transposed.command(0x2A);
  transposed.data(transposed_columns, sizeof(transposed_columns));
  transposed.command(0x2B);
  transposed.data(transposed_rows, sizeof(transposed_rows));
  transposed.begin();
  transposed.command(0x2C);
  const uint8_t too_many_transposed[14] = {};
  bool transposed_overflow = false;
  try {
    transposed.data(too_many_transposed, sizeof(too_many_transposed));
  } catch (const simulator::St7789Error& error) {
    transposed_overflow = error.code() == simulator::St7789ErrorCode::WindowOverflow;
  }
  assert(transposed_overflow);

  simulator::St7789VirtualController rotated_bounds(simulator::Profile::nodemcu_st7789_240x240());
  const uint8_t mv_my = 0xA0;
  rotated_bounds.command(0x36);
  rotated_bounds.data(&mv_my, 1);
  rotated_bounds.command(0x2A);
  const uint8_t last_columns[] = {1, 63, 1, 63};
  rotated_bounds.data(last_columns, sizeof(last_columns));
  rotated_bounds.command(0x2B);
  const uint8_t last_row[] = {0, 239, 0, 239};
  rotated_bounds.data(last_row, sizeof(last_row));
  rotated_bounds.begin();
  rotated_bounds.command(0x2C);
  const uint8_t last_pixel[] = {0x12, 0x34};
  rotated_bounds.data(last_pixel, sizeof(last_pixel));
  rotated_bounds.end();
  assert(rotated_bounds.gram(239, 319) == 0x1234);

  rotated_bounds.command(0x2A);
  const uint8_t invalid_column[] = {1, 64, 1, 64};
  bool invalid_mv_column = false;
  try {
    rotated_bounds.data(invalid_column, sizeof(invalid_column));
  } catch (const simulator::St7789Error& error) {
    invalid_mv_column = error.code() == simulator::St7789ErrorCode::InvalidWindow;
  }
  assert(invalid_mv_column);

  rotated_bounds.command(0x2B);
  const uint8_t invalid_row[] = {0, 0, 0, 240};
  bool invalid_mv_row = false;
  try {
    rotated_bounds.data(invalid_row, sizeof(invalid_row));
  } catch (const simulator::St7789Error& error) {
    invalid_mv_row = error.code() == simulator::St7789ErrorCode::InvalidWindow;
  }
  assert(invalid_mv_row);

  simulator::St7789VirtualController hidden_gram_pixel(
      simulator::Profile::nodemcu_st7789_240x240());
  hidden_gram_pixel.command(0x2A);
  const uint8_t one_column[] = {0, 0, 0, 0};
  hidden_gram_pixel.data(one_column, sizeof(one_column));
  hidden_gram_pixel.command(0x2B);
  const uint8_t hidden_row[] = {0, 250, 0, 250};
  hidden_gram_pixel.data(hidden_row, sizeof(hidden_row));
  hidden_gram_pixel.begin();
  hidden_gram_pixel.command(0x2C);
  hidden_gram_pixel.data(last_pixel, sizeof(last_pixel));
  hidden_gram_pixel.end();
  assert(hidden_gram_pixel.gram(0, 250) == 0x1234);
  for (uint16_t y = 0; y < 240; ++y)
    for (uint16_t x = 0; x < 240; ++x) assert(hidden_gram_pixel.visible_pixel(x, y) == 0);

  simulator::Profile offset = simulator::Profile::test(6, 6);
  offset.visible_width = 4;
  offset.visible_height = 4;
  offset.offset_x = 1;
  offset.offset_y = 1;
  simulator::St7789VirtualController lcd(offset);
  lcd.command(0x2A);
  const uint8_t columns[] = {0, 0, 0, 5};
  lcd.data(columns, sizeof(columns));
  lcd.command(0x2B);
  const uint8_t rows[] = {0, 0, 0, 5};
  lcd.data(rows, sizeof(rows));
  lcd.begin();
  lcd.command(0x2C);
  uint8_t bytes[6 * 6 * 2];
  for (unsigned y = 0; y < 6; ++y)
    for (unsigned x = 0; x < 6; ++x) {
      const uint16_t color = static_cast<uint16_t>((y << 8) | x);
      const std::size_t i = (y * 6 + x) * 2;
      bytes[i] = static_cast<uint8_t>(color >> 8);
      bytes[i + 1] = static_cast<uint8_t>(color);
    }
  lcd.data(bytes, sizeof(bytes));
  lcd.end();
  assert(lcd.visible_pixel(0, 0) == 0x0101);

  bool memory_budget_enforced = false;
  try {
    simulator::Rgb565Frame too_large(241, 320);
    (void)too_large;
  } catch (const std::invalid_argument&) {
    memory_budget_enforced = true;
  }
  assert(memory_budget_enforced);
}
