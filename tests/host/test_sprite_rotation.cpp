#include <cassert>
#include <cstdint>
#include <vector>
struct TFT_eSPI {
  uint16_t bitmap_fg = 0x1357, bitmap_bg = 0x2468;
};
class TFT_eSprite {
 public:
  TFT_eSPI* _tft;
  bool _created = true, _vpOoB = false;
  uint8_t _bpp = 1, rotation = 0;
  int _xDatum = 0, _yDatum = 0, _vpX = 0, _vpY = 0, _vpW, _vpH;
  int _dwidth, _dheight, _bitwidth, _iwidth, _iheight;
  uint8_t* _img8;
  uint8_t* _img4 = nullptr;
  uint16_t* _img = nullptr;
  uint16_t* _colorMap = nullptr;
  TFT_eSprite(TFT_eSPI* display, int w, int h, uint8_t* buffer)
      : _tft(display),
        _vpW(w),
        _vpH(h),
        _dwidth(w),
        _dheight(h),
        _bitwidth((w + 7) & ~7),
        _iwidth(w),
        _iheight(h),
        _img8(buffer) {}
  void resetViewport() {
    _xDatum = _yDatum = _vpX = _vpY = 0;
    _vpW = (rotation & 1) ? _dheight : _dwidth;
    _vpH = (rotation & 1) ? _dwidth : _dheight;
  }
  void setRotation(uint8_t r);
  void drawPixel(int32_t x, int32_t y, uint32_t color);
  uint16_t readPixel(int32_t x, int32_t y);
  uint16_t readPixelValue(int32_t x, int32_t y);
};
// FUNCTIONS UNDER TEST
int main() {
  for (int width : {16, 13, 8}) {
    for (int height : {8, 16}) {
      TFT_eSPI display;
      std::vector<uint8_t> data(((width + 7) / 8) * height);
      TFT_eSprite sprite(&display, width, height, data.data());
      for (uint8_t rotation = 0; rotation < 4; ++rotation) {
        sprite.setRotation(rotation);
        for (int y = 0; y < sprite._vpH; ++y)
          for (int x = 0; x < sprite._vpW; ++x) sprite.drawPixel(x, y, ((x * 3 + y * 5) % 7) < 3);
        for (int y = 0; y < sprite._vpH; ++y) {
          for (int x = 0; x < sprite._vpW; ++x) {
            const bool expected = ((x * 3 + y * 5) % 7) < 3;
            assert(sprite.readPixelValue(x, y) == expected);
            assert(sprite.readPixel(x, y) == (expected ? display.bitmap_fg : display.bitmap_bg));
          }
        }
        assert(sprite.readPixelValue(-1, 0) == 0xFF);
        assert(sprite.readPixelValue(0, sprite._vpH) == 0xFF);
        assert(sprite.readPixel(sprite._vpW, 0) == 0xFFFF);
        assert(sprite.readPixel(0, -1) == 0xFFFF);
        sprite._xDatum = 1;
        sprite._yDatum = 1;
        assert(sprite.readPixelValue(-1, -1) == (((0 * 3 + 0 * 5) % 7) < 3));
        sprite._vpX = sprite._vpY = 1;
        assert(sprite.readPixel(-1, -1) == 0xFFFF);
        sprite._created = false;
        assert(sprite.readPixelValue(0, 0) == 0xFF);
        sprite._created = true;
      }
    }
  }
}
