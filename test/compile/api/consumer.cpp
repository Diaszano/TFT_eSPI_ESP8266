#include <TFT_eSPI.h>
TFT_eSPI display;
TFT_eSprite sprite(&display);
void setup() {
  display.init();
  display.setTextColor(TFT_WHITE, TFT_BLACK);
  display.drawString("layout", 0, 0, 2);
  sprite.createSprite(8, 8);
  sprite.fillSprite(TFT_RED);
  sprite.deleteSprite();
}
void loop() {
}
