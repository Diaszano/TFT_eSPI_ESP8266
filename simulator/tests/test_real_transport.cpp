#include "TFT_eSPI.h"
#include "SimulatorTransport.h"
#include "core/St7789VirtualController.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

static bool has_rgb565_payload(uint8_t command, const std::vector<uint8_t>& expected) {
  const auto& events = simulator::host_spi().trace().events();
  bool ramwr = false;
  std::vector<uint8_t> payload;
  for (const auto& event : events) {
    if (event.kind == simulator::SpiEventKind::Command) {
      ramwr = event.bytes[0] == command;
      if (ramwr) payload.clear();
    } else if (ramwr && event.kind == simulator::SpiEventKind::Data) {
      payload.insert(payload.end(), event.bytes.begin(), event.bytes.end());
      if (payload == expected) return true;
    }
  }
  return false;
}

static bool has_command(uint8_t command) {
  const auto& events = simulator::host_spi().trace().events();
  for (const auto& event : events)
    if (event.kind == simulator::SpiEventKind::Command && event.bytes[0] == command) return true;
  return false;
}

static bool has_command_data(uint8_t command, const std::vector<uint8_t>& expected) {
  const auto& events = simulator::host_spi().trace().events();
  bool matching = false;
  std::vector<uint8_t> data;
  for (const auto& event : events) {
    if (event.kind == simulator::SpiEventKind::Command) {
      matching = event.bytes[0] == command;
      data.clear();
    } else if (matching && event.kind == simulator::SpiEventKind::Data) {
      data.insert(data.end(), event.bytes.begin(), event.bytes.end());
      if (data == expected) return true;
    }
  }
  return false;
}

int main() {
  TFT_eSPI tft;
  const uint16_t pixels[] = {TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE};
  tft.init();
  const simulator::SpiTrace init_trace = simulator::host_spi().trace();
  simulator::St7789VirtualController lcd(simulator::Profile::nodemcu_st7789_240x240());
  try {
    lcd.replay(init_trace);
  } catch (const simulator::St7789Error& error) {
    std::fprintf(stderr, "init replay failed: code=%d command=0x%02X offset=%zu\n",
                 static_cast<int>(error.code()), error.command(), error.offset());
    throw;
  }
  assert(lcd.display_on());
  assert(lcd.visible_width() == 240 && lcd.visible_height() == 240);
  assert(lcd.row_window().last == 319);
  assert(lcd.gram(0, 0) == TFT_RED);
  const auto init_frame = lcd.frame().pixels();
  lcd.replay(init_trace);
  assert(lcd.frame().pixels() == init_frame);

  const uint16_t diagnostic[] = {0xF800, 0x07E0, 0x001F, 0x07FF, 0xF81F, 0xFFE0, 0xFFFF, 0x0000};
  simulator::St7789VirtualController diagnostic_lcd(simulator::Profile::nodemcu_st7789_240x240());
  diagnostic_lcd.replay(init_trace);
  assert(diagnostic_lcd.madctl() == 0x08);
  for (uint8_t i = 0; i < 8; ++i) {
    simulator::host_spi().reset();
    tft.drawPixel(i, 10, diagnostic[i]);
    assert(has_rgb565_payload(
        0x2C, {static_cast<uint8_t>(diagnostic[i] >> 8), static_cast<uint8_t>(diagnostic[i])}));
    diagnostic_lcd.apply(simulator::host_spi().trace());
    assert(diagnostic_lcd.raw_gram_pixel(i, 10) == diagnostic[i]);
    assert(diagnostic_lcd.visible_pixel(i, 10) == diagnostic[i]);
  }
  simulator::host_spi().reset();
  tft.fillRect(20, 10, 2, 2, 0xF800);
  tft.fillRect(22, 10, 2, 2, 0x001F);
  tft.fillRect(20, 12, 2, 2, 0x07E0);
  tft.drawPixel(23, 13, 0xFFFF);
  diagnostic_lcd.apply(simulator::host_spi().trace());
  assert(diagnostic_lcd.visible_pixel(20, 10) == 0xF800);
  assert(diagnostic_lcd.visible_pixel(22, 10) == 0x001F);
  assert(diagnostic_lcd.visible_pixel(20, 12) == 0x07E0);
  assert(diagnostic_lcd.visible_pixel(23, 13) == 0xFFFF);

  simulator::host_spi().reset();
  tft.fillRect(0, 0, 2, 2, TFT_RED);
  assert(has_command(0x2A) && has_command(0x2B) && has_command(0x2C));
  assert(has_rgb565_payload(0x2C, {0xF8, 0x00, 0xF8, 0x00, 0xF8, 0x00, 0xF8, 0x00}));

  simulator::host_spi().reset();
  tft.fillRect(0, 0, 8, 5, TFT_RED);
  std::vector<uint8_t> solid(8 * 5 * 2);
  for (std::size_t i = 0; i < solid.size(); i += 2) {
    solid[i] = 0xF8;
    solid[i + 1] = 0x00;
  }
  assert(has_rgb565_payload(0x2C, solid));

  simulator::host_spi().reset();
  tft.drawLine(0, 0, 1, 0, TFT_GREEN);
  assert(has_rgb565_payload(0x2C, {0x07, 0xE0, 0x07, 0xE0}));

  simulator::host_spi().reset();
  tft.pushImage(0, 0, 2, 2, pixels);
  assert(has_rgb565_payload(0x2C, {0x00, 0xF8, 0xE0, 0x07, 0x1F, 0x00, 0xFF, 0xFF}));

  tft.setSwapBytes(true);
  simulator::host_spi().reset();
  tft.pushImage(0, 0, 2, 2, pixels);
  assert(has_rgb565_payload(0x2C, {0xF8, 0x00, 0x07, 0xE0, 0x00, 0x1F, 0xFF, 0xFF}));

  simulator::host_spi().reset();
  tft.startWrite();
  tft.setWindow(300, 100, 100, 100);
  tft.endWrite();
  assert(has_command_data(0x2A, {0x01, 0x2C, 0x00, 0x64}));
  assert(has_command_data(0x2B, {0x00, 0x64, 0x00, 0x64}));

  simulator::host_spi().reset();
  tft.drawPixel(188, 100, TFT_WHITE);
  assert(has_command_data(0x2A, {0x00, 0xBC, 0x00, 0xBC}));
  assert(has_command_data(0x2B, {0x00, 0x64, 0x00, 0x64}));

  bool read_rejected = false;
  try {
    SPI.transfer(0);
  } catch (const simulator::SpiTraceError& error) {
    read_rejected = error.code() == simulator::SpiTraceErrorCode::UnsupportedOperation;
  }
  assert(read_rejected);

  bool touch_rejected = false;
  try {
    T_CS_L;
  } catch (const simulator::SpiTraceError& error) {
    touch_rejected = error.code() == simulator::SpiTraceErrorCode::UnsupportedOperation;
  }
  assert(touch_rejected);
}
