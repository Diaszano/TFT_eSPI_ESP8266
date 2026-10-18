#include "core/St7789VirtualController.h"

#include <cassert>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using simulator::St7789Error;
using simulator::St7789ErrorCode;
using simulator::St7789VirtualController;

static simulator::SpiTrace read_fixture() {
  simulator::SpiTrace trace(128, 16);
  std::ifstream input(std::string(SIMULATOR_SOURCE_DIR) +
                      "/tests/fixtures/commands/basic-rgb565.trace");
  assert(input.good());
  std::string line;
  while (std::getline(input, line)) {
    std::istringstream row(line);
    char kind;
    row >> kind;
    if (kind == 'B')
      trace.begin();
    else if (kind == 'E')
      trace.end();
    else if (kind == 'C') {
      unsigned value;
      row >> std::hex >> value;
      trace.command(static_cast<uint8_t>(value));
    } else if (kind == 'D') {
      std::vector<uint8_t> bytes;
      unsigned value;
      while (row >> std::hex >> value) bytes.push_back(static_cast<uint8_t>(value));
      trace.data(bytes.data(), bytes.size());
    }
  }
  return trace;
}

static void setup_window(St7789VirtualController& lcd) {
  lcd.command(0x2A);
  const uint8_t columns[] = {0, 1, 0, 2};
  lcd.data(columns, sizeof(columns));
  lcd.command(0x2B);
  const uint8_t rows[] = {0, 1, 0, 2};
  lcd.data(rows, sizeof(rows));
}

int main(int argc, char**) {
  St7789VirtualController lcd(simulator::Profile::test(4, 4));
  if (argc == 1) {
    setup_window(lcd);
    assert(lcd.column_window().first == 1 && lcd.column_window().last == 2);
    assert(lcd.row_window().first == 1 && lcd.row_window().last == 2);
    bool rejected = false;
    try {
      lcd.data(reinterpret_cast<const uint8_t*>("x"), 1);
    } catch (const St7789Error& error) {
      rejected = error.code() == St7789ErrorCode::DataWithoutCommand;
    }
    assert(rejected);

    lcd.command(0x2A);
    bool incomplete = false;
    try {
      lcd.command(0x2B);
    } catch (const St7789Error& error) {
      incomplete = error.code() == St7789ErrorCode::IncompleteParameters &&
                   error.command() == 0x2A && error.offset() == 0;
    }
    assert(incomplete);
    lcd.reset();
    bool unknown_rejected = false;
    try {
      lcd.command(0x55);
    } catch (const St7789Error& error) {
      unknown_rejected =
          error.code() == St7789ErrorCode::UnsupportedCommand && error.command() == 0x55;
    }
    assert(unknown_rejected);

    lcd.reset();
    bool bad_window = false;
    try {
      lcd.command(0x2A);
      const uint8_t columns[] = {0, 0, 0, 4};
      lcd.data(columns, sizeof(columns));
    } catch (const St7789Error& error) {
      bad_window = error.code() == St7789ErrorCode::InvalidWindow;
    }
    assert(bad_window);

    lcd.reset();
    bool extra_parameter = false;
    try {
      lcd.command(0x2A);
      const uint8_t too_many[] = {0, 0, 0, 1, 2};
      lcd.data(too_many, sizeof(too_many));
    } catch (const St7789Error& error) {
      extra_parameter = error.code() == St7789ErrorCode::InvalidParameters && error.offset() == 4;
    }
    assert(extra_parameter);
    lcd.reset();
    bool format_rejected = false;
    try {
      lcd.command(0x3A);
      const uint8_t rgb666[] = {0x66};
      lcd.data(rgb666, sizeof(rgb666));
    } catch (const St7789Error& error) {
      format_rejected = error.code() == St7789ErrorCode::UnsupportedPixelFormat;
    }
    assert(format_rejected);
    St7789VirtualController fixture_lcd(simulator::Profile::test(4, 4));
    fixture_lcd.replay(read_fixture());
    assert(fixture_lcd.gram(1, 1) == 0xF800);
    assert(fixture_lcd.gram(2, 1) == 0x07E0);
    assert(fixture_lcd.gram(1, 2) == 0x001F);
    assert(fixture_lcd.gram(2, 2) == 0xFFFF);
    St7789VirtualController panel(simulator::Profile::nodemcu_st7789_240x240());
    panel.command(0x2A);
    const uint8_t first_column[] = {0, 0, 0, 0};
    panel.data(first_column, sizeof(first_column));
    panel.command(0x2B);
    panel.data(first_column, sizeof(first_column));
    panel.command(0x2C);
    const uint8_t red_pixel[] = {0xF8, 0x00};
    panel.data(red_pixel, sizeof(red_pixel));
    panel.command(0x36);
    const uint8_t panel_bgr[] = {0x08};
    panel.data(panel_bgr, sizeof(panel_bgr));
    assert(panel.raw_gram_pixel(0, 0) == 0xF800);
    assert(panel.visible_pixel(0, 0) == 0xF800);
    panel.command(0x36);
    const uint8_t panel_rgb[] = {0x00};
    panel.data(panel_rgb, sizeof(panel_rgb));
    assert(panel.visible_pixel(0, 0) == 0x001F);
    return 0;
  }

  setup_window(lcd);
  lcd.begin();
  lcd.command(0x2C);
  const uint8_t first[] = {0xF8};
  const uint8_t rest[] = {0x00, 0x07, 0xE0, 0x00};
  lcd.data(first, sizeof(first));
  lcd.data(rest, sizeof(rest));
  assert(lcd.gram(1, 1) == 0xF800);
  assert(lcd.gram(2, 1) == 0x07E0);
  assert(lcd.has_incomplete_pixel());
  bool odd_rejected = false;
  try {
    lcd.end();
  } catch (const St7789Error& error) {
    odd_rejected = error.code() == St7789ErrorCode::IncompletePixel;
  }
  assert(odd_rejected);

  lcd.reset();
  setup_window(lcd);
  lcd.begin();
  lcd.command(0x2C);
  const uint8_t row_wrap[] = {0xF8, 0x00, 0x07, 0xE0, 0x00, 0x1F, 0xFF, 0xFF};
  lcd.data(row_wrap, sizeof(row_wrap));
  assert(lcd.gram(1, 2) == 0x001F && lcd.gram(2, 2) == 0xFFFF);
  lcd.end();

  lcd.reset();
  setup_window(lcd);
  lcd.begin();
  lcd.command(0x2C);
  const uint8_t too_many[] = {0, 1, 0, 2, 0, 3, 0, 4, 0, 5};
  bool overflow_rejected = false;
  try {
    lcd.data(too_many, sizeof(too_many));
  } catch (const St7789Error& error) {
    overflow_rejected = error.code() == St7789ErrorCode::WindowOverflow;
  }
  assert(overflow_rejected);

  lcd.reset();
  lcd.command(0x2A);
  const uint8_t whole_columns[] = {0, 0, 0, 3};
  lcd.data(whole_columns, sizeof(whole_columns));
  lcd.command(0x2B);
  const uint8_t whole_rows[] = {0, 0, 0, 3};
  lcd.data(whole_rows, sizeof(whole_rows));
  lcd.begin();
  lcd.command(0x2C);
  const uint8_t red[] = {0xF8, 0x00};
  lcd.data(red, sizeof(red));
  lcd.end();
  lcd.command(0x36);
  const uint8_t bgr[] = {0x08};
  lcd.data(bgr, sizeof(bgr));
  lcd.command(0x21);
  assert(lcd.inverted() && lcd.raw_gram_pixel(0, 0) == 0xF800);
  assert(lcd.visible_pixel(0, 0) == 0x001F);
  lcd.command(0x20);
  assert(!lcd.inverted() && lcd.raw_gram_pixel(0, 0) == 0xF800);
  lcd.command(0x01);
  assert(!lcd.display_on() && lcd.colmod() == 0x55 && lcd.raw_gram_pixel(0, 0) == 0);
}
