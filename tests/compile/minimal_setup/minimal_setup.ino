#include <TFT_eSPI.h>

TFT_eSPI tft;
TFT_eSprite sprite(&tft);

void setup() {
  tft.init();
  sprite.setColorDepth(4);
  if (sprite.createSprite(4, 1) == nullptr) return;
  sprite.scroll(1, 0);
  sprite.deleteSprite();
}

void loop() {}
