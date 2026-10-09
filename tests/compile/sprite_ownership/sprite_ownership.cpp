#include <type_traits>
#include <TFT_eSPI.h>

static_assert(!std::is_copy_constructible<TFT_eSprite>::value, "sprite must not copy");
static_assert(!std::is_copy_assignable<TFT_eSprite>::value, "sprite must not assign");

TFT_eSPI display;
TFT_eSprite sprite(&display);

void setup() {
  TFT_eSprite& borrowed = sprite;
  borrowed.createSprite(4, 4);
}

void loop() {
}
