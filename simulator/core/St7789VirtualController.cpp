#include "core/St7789VirtualController.h"

#include <algorithm>

namespace simulator {
namespace {
constexpr int kNoCommand = -1;
constexpr uint8_t kNop = 0x00;
constexpr uint8_t kSwReset = 0x01;
constexpr uint8_t kSleepIn = 0x10;
constexpr uint8_t kSleepOut = 0x11;
constexpr uint8_t kNormalOn = 0x13;
constexpr uint8_t kInversionOff = 0x20;
constexpr uint8_t kInversionOn = 0x21;
constexpr uint8_t kDisplayOff = 0x28;
constexpr uint8_t kDisplayOn = 0x29;
constexpr uint8_t kColumnSet = 0x2A;
constexpr uint8_t kRowSet = 0x2B;
constexpr uint8_t kRamWrite = 0x2C;
constexpr uint8_t kMadctl = 0x36;
constexpr uint8_t kColmod = 0x3A;
constexpr uint8_t kBgr = 0x08;
}  // namespace

Profile Profile::test(uint16_t width, uint16_t height) {
  return {width, height, width, height, 0, 0};
}

Profile Profile::nodemcu_st7789_240x240() {
  return {240, 320, 240, 240, 0, 0, true};
}

St7789Error::St7789Error(St7789ErrorCode code, uint8_t command, std::size_t offset,
                         const char* message)
    : std::runtime_error(message), code_(code), command_(command), offset_(offset) {
}

St7789VirtualController::St7789VirtualController(Profile profile)
    : profile_(profile), frame_(profile.gram_width, profile.gram_height) {
  if (profile.visible_width == 0 || profile.visible_height == 0 ||
      profile.offset_x + profile.visible_width > profile.gram_width ||
      profile.offset_y + profile.visible_height > profile.gram_height)
    throw std::invalid_argument("visible area is outside controller GRAM");
  reset();
}

void St7789VirtualController::reset() {
  frame_.clear();
  columns_ = {0, static_cast<uint16_t>(profile_.gram_width - 1)};
  rows_ = {0, static_cast<uint16_t>(profile_.gram_height - 1)};
  parameters_.clear();
  expected_parameters_ = -1;
  current_command_ = kNoCommand;
  ramwr_active_ = false;
  has_high_byte_ = false;
  high_byte_ = 0;
  cursor_x_ = cursor_y_ = 0;
  transaction_active_ = false;
  madctl_ = 0;
  colmod_ = 0x55;
  display_on_ = false;
  sleeping_ = false;
  inverted_ = false;
}

void St7789VirtualController::begin() {
  if (transaction_active_)
    throw St7789Error(St7789ErrorCode::InvalidTransaction, 0, 0, "nested controller transaction");
  transaction_active_ = true;
}

int St7789VirtualController::parameter_count(uint8_t command_value) const {
  switch (command_value) {
    case kNop:
    case kSwReset:
    case kSleepIn:
    case kSleepOut:
    case kNormalOn:
    case kInversionOff:
    case kInversionOn:
    case kDisplayOff:
    case kDisplayOn:
    case kRamWrite:
      return 0;
    case kColumnSet:
    case kRowSet:
      return 4;
    case kMadctl:
    case kColmod:
    case 0xB7:
    case 0xBB:
    case 0xC0:
    case 0xC3:
    case 0xC4:
    case 0xC6:
      return 1;
    case 0xB0:
    case 0xB6:
    case 0xC2:
    case 0xD0:
      return 2;
    case 0xB2:
      return 5;
    case 0xE0:
    case 0xE1:
      return 14;
    default:
      return -1;
  }
}

void St7789VirtualController::finish_pixels() {
  if (has_high_byte_)
    throw St7789Error(St7789ErrorCode::IncompletePixel, kRamWrite, 1,
                      "RAMWR ended with an incomplete RGB565 pixel");
}

void St7789VirtualController::finish_command() {
  if (current_command_ == kRamWrite) {
    finish_pixels();
    ramwr_active_ = false;
  } else if (current_command_ != kNoCommand && expected_parameters_ >= 0 &&
             parameters_.size() != static_cast<std::size_t>(expected_parameters_)) {
    throw St7789Error(St7789ErrorCode::IncompleteParameters, static_cast<uint8_t>(current_command_),
                      parameters_.size(), "ST7789 command has incomplete parameters");
  }
  current_command_ = kNoCommand;
  expected_parameters_ = -1;
  parameters_.clear();
}

void St7789VirtualController::command(uint8_t value) {
  finish_command();
  if (value == kSwReset) {
    const bool transaction = transaction_active_;
    reset();
    transaction_active_ = transaction;
  }
  const int count = parameter_count(value);
  if (count < 0)
    throw St7789Error(St7789ErrorCode::UnsupportedCommand, value, 0, "unsupported ST7789 command");
  if (value == kRamWrite) {
    if (colmod_ != 0x55)
      throw St7789Error(St7789ErrorCode::UnsupportedPixelFormat, value, 0,
                        "only RGB565 COLMOD 0x55 is supported");
    if (columns_.first > columns_.last || rows_.first > rows_.last)
      throw St7789Error(St7789ErrorCode::InvalidWindow, value, 0, "RAMWR has an invalid window");
    cursor_x_ = columns_.first;
    cursor_y_ = rows_.first;
    has_high_byte_ = false;
    ramwr_active_ = true;
    current_command_ = value;
    expected_parameters_ = 0;
    return;
  }
  current_command_ = value;
  expected_parameters_ = count;
  if (count == 0) {
    switch (value) {
      case kSleepIn:
        sleeping_ = true;
        break;
      case kSleepOut:
        sleeping_ = false;
        break;
      case kDisplayOn:
        display_on_ = true;
        break;
      case kDisplayOff:
        display_on_ = false;
        break;
      case kInversionOn:
        inverted_ = true;
        break;
      case kInversionOff:
        inverted_ = false;
        break;
      default:
        break;
    }
    current_command_ = kNoCommand;
    expected_parameters_ = -1;
    return;
  }
  parameters_.reserve(static_cast<std::size_t>(count));
}

void St7789VirtualController::apply_parameters() {
  if (current_command_ == kColumnSet || current_command_ == kRowSet) {
    const uint16_t first = static_cast<uint16_t>((parameters_[0] << 8) | parameters_[1]);
    const uint16_t last = static_cast<uint16_t>((parameters_[2] << 8) | parameters_[3]);
    const bool exchanged = (madctl_ & 0x20) != 0;
    const uint16_t maximum = current_command_ == kColumnSet
                                 ? (exchanged ? profile_.gram_height : profile_.gram_width)
                                 : (exchanged ? profile_.gram_width : profile_.gram_height);
    if (first > last || last >= maximum)
      throw St7789Error(St7789ErrorCode::InvalidWindow, static_cast<uint8_t>(current_command_), 0,
                        "ST7789 address window is outside GRAM");
    (current_command_ == kColumnSet ? columns_ : rows_) = {first, last};
  } else if (current_command_ == kMadctl) {
    if (parameters_[0] & 0x17)
      throw St7789Error(St7789ErrorCode::UnsupportedMadctl, kMadctl, 0,
                        "unsupported MADCTL scan-order bits");
    madctl_ = parameters_[0];
  } else if (current_command_ == kColmod) {
    if (parameters_[0] != 0x55)
      throw St7789Error(St7789ErrorCode::UnsupportedPixelFormat, kColmod, 0,
                        "only RGB565 COLMOD 0x55 is supported");
    colmod_ = parameters_[0];
  }
}

void St7789VirtualController::write_pixel_byte(uint8_t value) {
  if (cursor_x_ > columns_.last || cursor_y_ > rows_.last)
    throw St7789Error(St7789ErrorCode::WindowOverflow, kRamWrite, 0,
                      "RAMWR exceeds its inclusive address window");
  if (!has_high_byte_) {
    high_byte_ = value;
    has_high_byte_ = true;
    return;
  }
  const uint16_t color = static_cast<uint16_t>((high_byte_ << 8) | value);
  if (madctl_ & 0x20)
    frame_.set_pixel(cursor_y_, cursor_x_, color);
  else
    frame_.set_pixel(cursor_x_, cursor_y_, color);
  has_high_byte_ = false;
  if (madctl_ & 0x20) {
    if (cursor_y_ < rows_.last)
      ++cursor_y_;
    else {
      cursor_y_ = rows_.first;
      ++cursor_x_;
    }
  } else if (cursor_x_ < columns_.last)
    ++cursor_x_;
  else {
    cursor_x_ = columns_.first;
    ++cursor_y_;
  }
}

void St7789VirtualController::data(const uint8_t* bytes, std::size_t size) {
  if (size && !bytes)
    throw St7789Error(St7789ErrorCode::DataWithoutCommand, 0, 0, "null ST7789 data buffer");
  if (ramwr_active_) {
    for (std::size_t i = 0; i < size; ++i) write_pixel_byte(bytes[i]);
    return;
  }
  if (current_command_ == kNoCommand)
    throw St7789Error(St7789ErrorCode::DataWithoutCommand, 0, 0,
                      "ST7789 data arrived without an active command");
  for (std::size_t i = 0; i < size; ++i) {
    if (current_command_ == kNoCommand)
      throw St7789Error(St7789ErrorCode::InvalidParameters, 0, i,
                        "too many bytes in ST7789 data transfer");
    parameters_.push_back(bytes[i]);
    if (parameters_.size() > static_cast<std::size_t>(expected_parameters_))
      throw St7789Error(St7789ErrorCode::InvalidParameters, static_cast<uint8_t>(current_command_),
                        parameters_.size() - 1, "too many ST7789 command parameters");
    if (parameters_.size() == static_cast<std::size_t>(expected_parameters_)) {
      apply_parameters();
      current_command_ = kNoCommand;
      expected_parameters_ = -1;
      parameters_.clear();
    }
  }
}

void St7789VirtualController::end() {
  if (!transaction_active_)
    throw St7789Error(St7789ErrorCode::InvalidTransaction, 0, 0,
                      "controller transaction ended without begin");
  if (ramwr_active_) finish_pixels();
  transaction_active_ = false;
}

void St7789VirtualController::replay(const SpiTrace& trace) {
  reset();
  apply(trace);
}

void St7789VirtualController::apply(const SpiTrace& trace) {
  for (const SpiEvent& event : trace.events()) {
    switch (event.kind) {
      case SpiEventKind::Begin:
        begin();
        break;
      case SpiEventKind::Command:
        if (event.bytes.size() != 1)
          throw St7789Error(St7789ErrorCode::UnsupportedCommand, 0, 0,
                            "command trace event must contain one byte");
        command(event.bytes[0]);
        break;
      case SpiEventKind::Data:
        data(event.bytes.data(), event.bytes.size());
        break;
      case SpiEventKind::End:
        end();
        break;
    }
  }
  if (transaction_active_)
    throw St7789Error(St7789ErrorCode::InvalidTransaction, 0, trace.events().size(),
                      "SPI trace ended with an open transaction");
  finish_command();
}

uint16_t St7789VirtualController::visible_pixel(uint16_t x, uint16_t y) const {
  if (x >= profile_.visible_width || y >= profile_.visible_height)
    throw std::out_of_range("visible pixel coordinate out of range");
  const bool mx = madctl_ & 0x40;
  const bool my = madctl_ & 0x80;
  const bool mv = madctl_ & 0x20;
  uint16_t raw_x, raw_y;
  if (mv) {
    raw_x = mx ? static_cast<uint16_t>(profile_.visible_height - 1 - y) : y;
    raw_y = my ? static_cast<uint16_t>(profile_.gram_height - 1 - x) : x;
  } else {
    raw_x = mx ? static_cast<uint16_t>(profile_.gram_width - 1 - x) : x;
    raw_y = my ? static_cast<uint16_t>(profile_.gram_height - 1 - y) : y;
  }
  raw_x = static_cast<uint16_t>(raw_x + profile_.offset_x);
  raw_y = static_cast<uint16_t>(raw_y + profile_.offset_y);
  uint16_t color = frame_.pixel(raw_x, raw_y);
  if (((madctl_ & kBgr) != 0) != profile_.panel_bgr)
    color = static_cast<uint16_t>(((color & 0x001F) << 11) | (color & 0x07E0) |
                                  ((color & 0xF800) >> 11));
  return color;
}

}  // namespace simulator
