// ST7789 SPI stream model for the ESP8266 render primitives.
// The ESP8266 SPI registers are replaced by a decoder that tags every byte with the DC level,
// replays CASET/RASET/RAMWR into controller RAM and counts SPI transactions. A transfer stays
// in flight until the code polls SPI1CMD, so a register or DC write that real hardware would
// race against is reported as a bus violation.
#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "internal/clip.h"

using namespace tft_espi_internal;

#define PROGMEM
#define pgm_read_byte(p) (*(const uint8_t*)(p))
#define pgm_read_word(p) (*(const uint16_t*)(p))
// Font tables hold flash addresses; on the host they are pointer-width.
template <typename T>
uintptr_t pgm_read_dword(const T* p) {
  return (uintptr_t)*p;
}
inline uintptr_t pgm_read_dword(const void* p) {
  return *(const uintptr_t*)p;
}
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_RLE
#define CGRAM_OFFSET
#define TFT_CASET 0x2A
#define TFT_PASET 0x2B
#define TFT_RAMWR 0x2C
#define SPIBUSY   (1 << 18)
#define SPILMISO  8
#define SPILMOSI  17

namespace sim {
constexpr int kRam = 320;
uint16_t ram[kRam][kRam];
bool dc = true, busy = false;
uint32_t w[16], u1;
uint64_t transactions, bytes, violations, commands[256];
uint8_t cmd;
int arg, xs, xe, ys, ye, px, py;
uint8_t hi;

void feed(uint8_t b, bool data) {
  ++bytes;
  if (!data) {
    cmd = b;
    arg = 0;
    ++commands[b];
    if (b == TFT_RAMWR) px = xs, py = ys;
    return;
  }
  if (cmd == TFT_CASET || cmd == TFT_PASET) {
    int& lo = cmd == TFT_CASET ? xs : ys;
    int& hi2 = cmd == TFT_CASET ? xe : ye;
    if (arg == 0) lo = b << 8;
    if (arg == 1) lo |= b;
    if (arg == 2) hi2 = b << 8;
    if (arg == 3) hi2 |= b;
  } else if (cmd == TFT_RAMWR) {
    if (arg & 1) {
      if (px < kRam && py < kRam) ram[py][px] = uint16_t(hi << 8 | b);
      if (++px > xe) px = xs, ++py;
    } else {
      hi = b;
    }
  }
  ++arg;
}

void guard() {
  if (busy) ++violations;
}

struct Reg {
  uint32_t* r;
  Reg& operator=(uint32_t v) {
    guard();
    *r = v;
    return *this;
  }
};
struct Pin {
  bool level;
  Pin& operator=(uint32_t) {
    guard();
    dc = level;
    return *this;
  }
};
struct Cmd {
  operator uint32_t() {
    uint32_t v = busy ? SPIBUSY : 0;
    busy = false;
    return v;
  }
  void operator|=(uint32_t) {
    guard();
    ++transactions;
    const uint32_t n = (((u1 >> SPILMOSI) & 0x1FF) + 1) / 8;
    for (uint32_t i = 0; i < n; ++i) feed(uint8_t(w[i / 4] >> ((i % 4) * 8)), dc);
    busy = true;
  }
};
Cmd cmd_reg;

void reset() {
  std::memset(ram, 0, sizeof(ram));
  std::memset(commands, 0, sizeof(commands));
  transactions = bytes = violations = 0;
  busy = false;
  dc = true;
}
}  // namespace sim

#define SPI1CMD  sim::cmd_reg
#define SPI1U1   (sim::Reg{&sim::u1})
#define SPI1W(p) (sim::Reg{&sim::w[(p) & 0xF]})
#define SPI1W0   SPI1W(0)
#define SPI1W1   SPI1W(1)
#define SPI1W2   SPI1W(2)
#define SPI1W3   SPI1W(3)
#define SPI1W4   SPI1W(4)
#define SPI1W5   SPI1W(5)
#define SPI1W6   SPI1W(6)
#define SPI1W7   SPI1W(7)
#define SPI1W8   SPI1W(8)
#define SPI1W9   SPI1W(9)
#define SPI1W10  SPI1W(10)
#define SPI1W11  SPI1W(11)
#define SPI1W12  SPI1W(12)
#define SPI1W13  SPI1W(13)
#define SPI1W14  SPI1W(14)
#define SPI1W15  SPI1W(15)
#define GPOC     (sim::Pin{false})
#define GPOS     (sim::Pin{true})
#define DC_C     GPOC = dcpinmask
#define DC_D     GPOS = dcpinmask
#define CS_L
#define CS_H
#define SET_BUS_WRITE_MODE
#define SET_BUS_READ_MODE

// HEADER MACROS UNDER TEST

#include <Fonts/glcdfont.inc>
#include <Fonts/Font16.h>
#include <Fonts/Font32rle.h>

const uint8_t widtbl_null[1] = {0};
const uint8_t chr_null[1] = {0};
const uint8_t* const chrtbl_null[1] = {chr_null};
struct fontinfo {
  const uint8_t* chartbl;
  const uint8_t* widthtbl;
  uint8_t height;
  uint8_t baseline;
};
const fontinfo fontdata[] = {
    {(const uint8_t*)font, widtbl_null, 0, 0},
    {(const uint8_t*)chrtbl_null, widtbl_null, 8, 7},
    {(const uint8_t*)chrtbl_f16, widtbl_f16, chr_hgt_f16, baseline_f16},
    {(const uint8_t*)chrtbl_null, widtbl_null, 0, 0},
    {(const uint8_t*)chrtbl_f32, widtbl_f32, chr_hgt_f32, baseline_f32},
};

template <typename T>
static inline void transpose(T& a, T& b) {
  T t = a;
  a = b;
  b = t;
}

class TFT_eSPI {
 public:
  void begin_tft_write();
  void end_tft_write();
  void pushBlock(uint16_t color, uint32_t len);
  void pushPixels(const void* data_in, uint32_t len);
  void pushSwapBytePixels(const void* data_in, uint32_t len);
  void setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1);
  void drawPixel(int32_t x, int32_t y, uint32_t color);
  void fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color);
  void drawFastVLine(int32_t x, int32_t y, int32_t h, uint32_t color);
  void drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t color);
  void drawRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color);
  void drawLine(int32_t x0, int32_t y0, int32_t x1, int32_t y1, uint32_t color);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data, uint16_t transp);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t* data);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t* data, uint16_t transp);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint8_t* data, bool bpp8,
                 uint16_t* cmap = nullptr);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint8_t* data, bool bpp8,
                 uint16_t* cmap = nullptr);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint8_t* data, uint8_t transp,
                 bool bpp8, uint16_t* cmap = nullptr);
  void drawChar(int32_t x, int32_t y, uint16_t c, uint32_t color, uint32_t bg, uint8_t size);
  int16_t drawChar(uint16_t uniCode, int32_t x, int32_t y, uint8_t font);

  uint32_t dcpinmask = 1;
  bool locked = true, inTransaction = false, lockTransaction = false;
  bool _vpOoB = false, _swapBytes = false, _cp437 = true;
  int32_t _xDatum = 0, _yDatum = 0, _vpX = 0, _vpY = 0, _vpW = 240, _vpH = 240;
  int32_t addr_row = 0xFFFF, addr_col = 0xFFFF;
  int32_t colstart = 0, rowstart = 0;
  uint32_t textcolor = 0xFFFF, textbgcolor = 0, _lastColor = 0;
  uint16_t bitmap_fg = 0xFFFF, bitmap_bg = 0;
  uint8_t textsize = 1;
};

// FUNCTIONS UNDER TEST

namespace {
TFT_eSPI tft;
uint64_t checksum() {
  uint64_t h = 1469598103934665603ULL;
  for (auto& row : sim::ram)
    for (uint16_t p : row) h = (h ^ p) * 1099511628211ULL;
  return h;
}

struct Case {
  const char* name;
  void (*run)();
};

uint16_t image[240 * 240];
uint8_t image8[240 * 240];
uint8_t sprite8[240 * 240];  // 8bpp/4bpp/1bpp source with transparent (zero) runs
uint16_t palette[16];

const Case kCases[] = {
    {"fillScreen", [] { tft.fillRect(0, 0, 240, 240, 0x1234); }},
    {"fillRect 40x20", [] { tft.fillRect(10, 30, 40, 20, 0xF800); }},
    {"fillRect clipped", [] { tft.fillRect(-5, 230, 20, 30, 0x07E0); }},
    {"hline 240", [] { tft.drawFastHLine(0, 120, 240, 0xABCD); }},
    {"vline 240", [] { tft.drawFastVLine(120, 0, 240, 0xABCD); }},
    {"drawRect 104x44", [] { tft.drawRect(8, 8, 104, 44, 0xFFFF); }},
    {"drawPixel x16",
     [] {
       for (int i = 0; i < 16; ++i) tft.drawPixel(i * 3, 200, 0x1F);
     }},
    {"pushImage ram 64x32", [] { tft.pushImage(5, 5, 64, 32, image); }},
    {"pushImage ram clip", [] { tft.pushImage(-10, 200, 64, 64, image); }},
    {"pushImage ram transp", [] { tft.pushImage(0, 0, 240, 40, image, uint16_t(0x0000)); }},
    {"pushImage flash 240x40", [] { tft.pushImage(0, 0, 240, 40, (const uint16_t*)image); }},
    {"pushImage flash clip", [] { tft.pushImage(200, -3, 64, 20, (const uint16_t*)image); }},
    {"pushImage flash transp",
     [] { tft.pushImage(0, 0, 240, 40, (const uint16_t*)image, uint16_t(0)); }},
    {"pushImage 8bpp 240x20", [] { tft.pushImage(0, 0, 240, 20, (const uint8_t*)image8, true); }},
    {"pushImage 4bpp 240x20",
     [] { tft.pushImage(1, 3, 239, 20, (const uint8_t*)image8, false, palette); }},
    {"pushImage 1bpp 240x20", [] { tft.pushImage(0, 0, 240, 20, (const uint8_t*)image8, false); }},
    {"pushImage 1bpp clip top",
     [] { tft.pushImage(0, -5, 100, 20, (const uint8_t*)image8, false); }},
    {"ram 8bpp 100x20", [] { tft.pushImage(3, 2, 100, 20, image8, true); }},
    {"ram 4bpp odd dx", [] { tft.pushImage(-3, 0, 100, 20, image8, false, palette); }},
    {"ram 1bpp clip top", [] { tft.pushImage(0, -5, 100, 20, image8, false); }},
    {"ram 8bpp transp", [] { tft.pushImage(0, 0, 200, 20, sprite8, uint8_t(0), true); }},
    {"ram 4bpp transp odd dx",
     [] { tft.pushImage(-1, 0, 200, 20, sprite8, uint8_t(0), false, palette); }},
    {"ram 4bpp transp even dx",
     [] { tft.pushImage(-2, 3, 200, 20, sprite8, uint8_t(0), false, palette); }},
    {"ram 1bpp transp", [] { tft.pushImage(0, 0, 200, 20, sprite8, uint8_t(0), false); }},
    {"glcd opaque 10ch",
     [] {
       for (int i = 0; i < 10; ++i) tft.drawChar(i * 6, 10, 'A' + i, 0xFFFF, 0x0010, 1);
     }},
    {"glcd transparent",
     [] {
       for (int i = 0; i < 10; ++i) tft.drawChar(i * 6, 10, 'A' + i, 0xFFFF, 0xFFFF, 1);
     }},
    {"glcd size2 clipped", [] { tft.drawChar(234, 230, 'W', 0xFFFF, 0x0010, 2); }},
    {"font2 opaque 10ch",
     [] {
       for (int i = 0; i < 10; ++i) tft.drawChar('0' + i, i * 9, 50, 2);
     }},
    {"font2 transparent",
     [] {
       tft.textbgcolor = tft.textcolor;
       for (int i = 0; i < 10; ++i) tft.drawChar('0' + i, i * 9, 50, 2);
       tft.textbgcolor = 0;
     }},
    {"font4 opaque 10ch",
     [] {
       for (int i = 0; i < 10; ++i) tft.drawChar('0' + i, i * 15, 80, 4);
     }},
    {"font4 transparent",
     [] {
       tft.textbgcolor = tft.textcolor;
       for (int i = 0; i < 4; ++i) tft.drawChar('0' + i, i * 15, 80, 4);
       tft.textbgcolor = 0;
     }},
    {"font4 clipped", [] { tft.drawChar('8', 230, 225, 4); }},
};

// Drawing at y = -dy must show the source rows from dy onward.
template <typename Draw>
void checkTopClip(const char* name, Draw draw) {
  static uint16_t full[20][100];
  sim::reset();
  draw(0);
  for (int r = 0; r < 20; ++r) std::memcpy(full[r], sim::ram[r], sizeof(full[r]));
  sim::reset();
  draw(-5);
  for (int r = 0; r < 15; ++r)
    if (std::memcmp(full[r + 5], sim::ram[r], sizeof(full[r]))) {
      std::printf("top clip mismatch: %s row %d\n", name, r);
      std::abort();
    }
}

void topClips() {
  checkTopClip("flash 16bpp", [](int y) { tft.pushImage(0, y, 100, 20, (const uint16_t*)image); });
  checkTopClip("flash 8bpp",
               [](int y) { tft.pushImage(0, y, 100, 20, (const uint8_t*)image8, true); });
  checkTopClip("flash 4bpp",
               [](int y) { tft.pushImage(0, y, 100, 20, (const uint8_t*)image8, false, palette); });
  checkTopClip("flash 1bpp",
               [](int y) { tft.pushImage(0, y, 100, 20, (const uint8_t*)image8, false); });
  checkTopClip("ram 1bpp", [](int y) { tft.pushImage(0, y, 100, 20, image8, false); });
  checkTopClip("ram 1bpp transp",
               [](int y) { tft.pushImage(0, y, 100, 20, sprite8, uint8_t(0), false); });
}

// Reference: the original drawLine Bresenham, plotting every pixel through the viewport.
void referenceLine(int64_t x0, int64_t y0, int64_t x1, int64_t y1, uint16_t c,
                   std::vector<uint16_t>& out) {
  bool steep = (y1 > y0 ? y1 - y0 : y0 - y1) > (x1 > x0 ? x1 - x0 : x0 - x1);
  if (steep) std::swap(x0, y0), std::swap(x1, y1);
  if (x0 > x1) std::swap(x0, x1), std::swap(y0, y1);
  int64_t dx = x1 - x0, dy = y1 > y0 ? y1 - y0 : y0 - y1, err = dx >> 1, ystep = y0 < y1 ? 1 : -1;
  for (; x0 <= x1; x0++) {
    int64_t px = (steep ? y0 : x0) + tft._xDatum, py = (steep ? x0 : y0) + tft._yDatum;
    if (px >= tft._vpX && px < tft._vpW && py >= tft._vpY && py < tft._vpH) out[py * 240 + px] = c;
    err -= dy;
    if (err < 0) y0 += ystep, err += dx;
  }
}

void lines() {
  std::vector<uint16_t> want(240 * 240);
  uint32_t seed = 12345;
  auto rnd = [&](int32_t span) {
    seed = seed * 1103515245u + 12345u;
    return int32_t(seed >> 8) % span;
  };
  for (int i = 0; i < 3000; ++i) {
    // Mostly near the panel, some far away so the clipped start must reproduce Bresenham exactly.
    const int32_t span = i % 3 == 0 ? 200000 : i % 3 == 1 ? 600 : 260;
    const int32_t x0 = rnd(span) - span / 2 + 120, y0 = rnd(span) - span / 2 + 120;
    const int32_t x1 = rnd(span) - span / 2 + 120, y1 = rnd(span) - span / 2 + 120;
    tft._xDatum = i % 5 == 0 ? 7 : 0, tft._yDatum = i % 5 == 0 ? -3 : 0;
    sim::reset();
    std::fill(want.begin(), want.end(), 0);
    tft.drawLine(x0, y0, x1, y1, 0xBEEF);
    referenceLine(x0, y0, x1, y1, 0xBEEF, want);
    for (int y = 0; y < 240; ++y)
      for (int x = 0; x < 240; ++x)
        if (sim::ram[y][x] != want[y * 240 + x]) {
          std::printf("drawLine mismatch (%d,%d)-(%d,%d) at %d,%d\n", x0, y0, x1, y1, x, y);
          std::abort();
        }
  }
  // Extreme endpoints: defined behaviour and bounded work (each visible pixel at most one run).
  const int32_t big[] = {INT32_MIN, -100000, -1, 0, 120, 239, 240, 100000, INT32_MAX};
  for (int32_t datum : {0, 9, INT32_MIN, INT32_MAX})
    for (int32_t a : big)
      for (int32_t b : big) {
        tft._xDatum = tft._yDatum = datum;
        sim::reset();
        tft.drawLine(a, b, b, a, 1);
        tft.drawLine(a, 0, b, 239, 1);
        tft.drawLine(0, a, 239, b, 1);
        tft.drawLine(a, a, b, b, 1);
        assert(sim::transactions < 4 * 3 * 2 * 240 + 64);
      }
  tft._xDatum = tft._yDatum = 0;
}

// Inputs a correct clip rejects or trims; signed-overflow here is caught by UBSan.
void extremes() {
  const int32_t big[] = {INT32_MIN, INT32_MIN + 1, -1000000,      -1,       0, 1, 239,
                         240,       1000000,       INT32_MAX - 1, INT32_MAX};
  for (int32_t a : big)
    for (int32_t b : big) {
      sim::reset();
      tft.fillRect(a, 10, b, 2, 0xFFFF);
      tft.fillRect(10, a, 2, b, 0xFFFF);
      tft.drawFastHLine(a, 10, b, 0xFFFF);
      tft.drawFastVLine(10, a, b, 0xFFFF);
      // Nothing may ever be written outside the 240x240 panel window.
      assert(sim::bytes <= 4 * 240 * 240 + 64);
    }
  // Points, outlines and glyphs at extreme positions, also with an origin offset (setOrigin).
  for (int32_t datum : {0, 7, -7, INT32_MAX, INT32_MIN}) {
    tft._xDatum = tft._yDatum = datum;
    for (int32_t a : big)
      for (int32_t b : big) {
        sim::reset();
        tft.drawPixel(a, b, 0xFFFF);
        tft.drawRect(a, 10, b, 5, 0xFFFF);
        tft.drawRect(10, a, 5, b, 0xFFFF);
        tft.drawRect(a, b, b, a, 0xFFFF);
        tft.drawChar(a, b, 'W', 0xFFFF, 0x0000, 1);
        tft.drawChar(a, b, 'W', 0xFFFF, 0xFFFF, 3);
        assert(tft.drawChar('8', a, b, 2) == 8 && tft.drawChar('8', a, b, 4) == 14);
        tft.textsize = 3;
        assert(tft.drawChar('8', a, b, 2) == 24 && tft.drawChar('8', a, b, 4) == 42);
        tft.textsize = 1;
        assert(sim::bytes <= 8 * 240 * 240);
      }
  }
  tft._xDatum = tft._yDatum = 0;
  // pushImage never reads the source when the clip leaves nothing, and stays in the window otherwise.
  for (int32_t a : big)
    for (int32_t b : {INT32_MIN, -1, 0, 1, INT32_MAX}) {
      // Only spans that end before the panel or start after it are guaranteed empty.
      const int64_t end = (int64_t)a + b;
      if (b > 0 && end > 0 && a < 240) continue;
      sim::reset();
      tft.pushImage(a, 10, b, 1, (const uint16_t*)nullptr);
      tft.pushImage(10, a, 1, b, (uint16_t*)nullptr);
      tft.pushImage(a, a, b, b, (const uint8_t*)nullptr, true);
      assert(sim::bytes == 0);
    }
  sim::reset();
  tft.pushImage(230, 230, INT32_MAX, 1, image);  // reads only the visible 10 pixels
  assert(sim::ram[230][239] == image[9] && sim::ram[230][229] == 0);
  // drawPixel through an origin: exact position, and nothing when the sum leaves int32_t.
  tft._xDatum = 5, tft._yDatum = -5;
  tft.addr_row = tft.addr_col = 0xFFFF;
  sim::reset();
  tft.drawPixel(10, 20, 0x00F0);
  tft.drawPixel(INT32_MAX, 20, 0x00F1);
  assert(sim::ram[15][15] == 0x00F0 && sim::bytes == 13);  // CASET 5 + RASET 5 + RAMWR 1 + pixel 2
  tft._xDatum = tft._yDatum = 0;
  // A glyph whose origin cancels a large position still lands on the panel.
  tft._xDatum = -(1 << 29), tft._yDatum = 0;
  sim::reset();
  tft.drawChar((1 << 29) + 3, 4, 'A', 0xFFFF, 0x0000, 1);
  assert(sim::bytes > 0 && sim::ram[4 + 7][3 + 5] == 0x0000);
  tft._xDatum = 0;
  // drawRect in normal range: 4 edges, corners included, interior untouched; clipped at the panel edge.
  sim::reset();
  tft.drawRect(230, 5, 20, 4, 0x0F0F);
  assert(sim::ram[5][230] == 0x0F0F && sim::ram[8][239] == 0x0F0F && sim::ram[6][231] == 0);
  assert(sim::ram[8][230] == 0x0F0F && sim::ram[6][230] == 0x0F0F);
  sim::reset();
  tft.fillRect(100, 100, INT32_MAX, INT32_MAX, 0x0001);
  assert(sim::ram[100][100] == 1 && sim::ram[239][239] == 1 && sim::ram[99][99] == 0);
  assert(sim::ram[100][240] == 0 && sim::ram[240][100] == 0);
}

// Transparent text over a blank panel writes exactly the foreground pixels, so it must equal
// opaque text with a zero background at every text size.
void transparentEquivalence() {
  const auto draw = [&](bool transparent, int size) {
    sim::reset();
    tft.textsize = size;
    tft.textbgcolor = transparent ? tft.textcolor : 0;
    for (int i = 0; i < 4; ++i) tft.drawChar('0' + i, i * 15 * size, 80, 4);
    tft.textsize = 1;
    tft.textbgcolor = 0;
  };
  uint16_t a[240][240], b[240][240];
  for (int size : {1, 2, 3}) {
    draw(true, size);
    std::memcpy(a, sim::ram, sizeof(a));
    draw(false, size);
    std::memcpy(b, sim::ram, sizeof(b));
    if (std::memcmp(a, b, sizeof(a))) {
      std::printf("transparent != opaque at size %d\n", size);
      std::abort();
    }
  }
}

}  // namespace

int main(int argc, char** argv) {
  for (int i = 0; i < 240 * 240; ++i) {
    image[i] = uint16_t((i * 2654435761u) >> 16);
    if (i % 7 < 3) image[i] = 0;  // transparent runs
    image8[i] = uint8_t(i * 37 + (i >> 5));
    sprite8[i] = i % 11 < 4 ? 0 : uint8_t(i * 37 + 1);
  }
  for (int i = 0; i < 16; ++i) palette[i] = uint16_t(i * 0x1111);
  const bool table = argc > 1 && std::strcmp(argv[1], "--table") == 0;
  if (table)
    std::printf("%-24s %8s %8s %6s %6s %6s %16s\n", "case", "txns", "bytes", "CASET", "RASET",
                "RAMWR", "ram");
  for (const Case& c : kCases) {
    uint64_t txns = 0, bytes = 0, caset = 0, raset = 0, ramwr = 0, ram = 0;
    for (int offset : {0, 80}) {  // 80: CGRAM offset of rotations 2 and 3 on 240x240 panels
      sim::reset();
      tft.rowstart = offset;
      tft.addr_row = tft.addr_col = 0xFFFF;
      c.run();
      assert(!sim::busy);  // every primitive leaves the bus idle
      assert(sim::violations == 0);
      ram = ram * 31 + checksum();
      if (offset) continue;
      txns = sim::transactions, bytes = sim::bytes;
      caset = sim::commands[TFT_CASET], raset = sim::commands[TFT_PASET],
      ramwr = sim::commands[TFT_RAMWR];
    }
    if (table)
      std::printf("%-24s %8llu %8llu %6llu %6llu %6llu %016llx\n", c.name, (unsigned long long)txns,
                  (unsigned long long)bytes, (unsigned long long)caset, (unsigned long long)raset,
                  (unsigned long long)ramwr, (unsigned long long)ram);
  }
  tft.rowstart = 0;
  if (!table) extremes(), topClips(), lines(), transparentEquivalence();
  std::puts("PASS render-stream");
}
