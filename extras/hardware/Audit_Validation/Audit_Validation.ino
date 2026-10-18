#include <stdint.h>
#include <TFT_eSPI.h>
#include "ValidationCommand.h"
#include "ValidationTelemetry.h"
#include "ValidationVisual.h"
#include "ValidationBench.h"
#include "ValidationStress.h"
#include "ValidationExtremes.h"

TFT_eSPI tft;
TFT_eSprite sprite32(&tft);
TFT_eSprite wideSprite(&tft);
bool spritesReady = false;

bool readValidationCommand(validation::ValidationCommand* command);

void showMenu() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextFont(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Hardware validation", 4, 12);
  tft.drawString("?: menu   B: bench", 4, 32);
  tft.drawString("S/S1-S4: visual", 4, 48);
  tft.drawString("L: stress   M: memory", 4, 64);
  tft.drawString("E30: endurance   X: extremes", 4, 80);
  tft.drawString("R0-R3: display rotation", 4, 96);
  tft.drawString("Suites are manually selected", 4, 112);
}

bool readValidationCommand(validation::ValidationCommand* command) {
  static validation::ValidationCommandReader reader;
  while (Serial.available()) {
    if (reader.consume(static_cast<char>(Serial.read()), command)) return true;
  }
  return false;
}

void skipSuite(const char* name) {
  validation_emit_case_start(Serial, name, 0);
  validation_emit_case_return(Serial, name, 0, "SKIP");
}

void validation_dispatch(validation::ValidationCommand command) {
  using validation::ValidationCommandKind;
  switch (command.kind) {
    case ValidationCommandKind::Menu:
      showMenu();
      break;
    case ValidationCommandKind::Bench:
      run_bench_suite(tft, sprite32, wideSprite, Serial);
      break;
    case ValidationCommandKind::Visual:
      run_visual_suite(command.visual_case, tft, Serial);
      break;
    case ValidationCommandKind::Stress:
      run_stress_10k(tft, sprite32, Serial);
      break;
    case ValidationCommandKind::Memory:
      run_memory_profiles(tft, sprite32, Serial);
      break;
    case ValidationCommandKind::Endurance30:
      run_endurance_30m(tft, sprite32, Serial);
      break;
    case ValidationCommandKind::Extremes:
      run_extreme_suite(tft, sprite32, Serial);
      break;
    case ValidationCommandKind::Rotation:
      tft.setRotation(command.rotation);
      Serial.print("ROTATION,");
      Serial.println(command.rotation);
      break;
    case ValidationCommandKind::Next:
    case ValidationCommandKind::Quit:
    case ValidationCommandKind::Unknown:
    default:
      Serial.println("UNKNOWN; send ?, B, S, S1-S4, R0-R3, L, M, E30 or X");
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);
  tft.init();
  tft.setRotation(0);
  tft.setSwapBytes(false);

  sprite32.setColorDepth(16);
  wideSprite.setColorDepth(16);
  spritesReady = sprite32.createSprite(32, 32) && wideSprite.createSprite(200, 24);
  if (spritesReady) {
    sprite32.fillSprite(TFT_MAGENTA);
    sprite32.fillRect(4, 4, 24, 24, TFT_CYAN);
    sprite32.drawRect(0, 0, 32, 32, TFT_WHITE);
    wideSprite.fillSprite(TFT_MAGENTA);
    wideSprite.fillRect(2, 2, 196, 20, TFT_GREEN);
    wideSprite.drawRect(0, 0, 200, 24, TFT_WHITE);
    wideSprite.setPivot(120, 120);
  }

  Serial.println("HWTEST,2");
  validation_emit_run(Serial);
  showMenu();
  Serial.println("READY");
}

void loop() {
  validation::ValidationCommand command;
  if (readValidationCommand(&command)) validation_dispatch(command);
}
