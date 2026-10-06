/*
  This sketch reads the user setup information from the processor via the Serial Port

  It is a support and diagnostic sketch for the TFT_eSPI library:
  https://github.com/Bodmer/TFT_eSPI

  The output is essentially a copy of the User_Setep configuration so can be used to
  verify the correct settings are being picked up by the compiler.

  If support is needed the output can be cut and pasted into an Arduino Forum post and
  already includes the formatting [code]...[/code] markups.

  Written by Bodmer 9/4/18
*/

#include <SPI.h>
#include <TFT_eSPI.h>      // Graphics library

TFT_eSPI tft = TFT_eSPI(); // Invoke library

#ifdef ARDUINO_ARCH_ESP8266
  ADC_MODE(ADC_VCC); // Read the supply voltage
#endif

setup_t user; // The library defines the type "setup_t" as a struct
              // Calling tft.getSetup(user) populates it with the settings
//------------------------------------------------------------------------------------------

void setup() {
  // Use serial port
  Serial.begin(115200);

  // Initialise the TFT screen
  tft.init();
}

//------------------------------------------------------------------------------------------

void loop(void) {

tft.getSetup(user); //

Serial.print("\n[code]\n");

Serial.print ("TFT_eSPI ver = "); Serial.println(user.version);
Serial.println("Processor    = ESP8266");
Serial.print("Frequency    = "); Serial.print(ESP.getCpuFreqMHz()); Serial.println("MHz");
#ifdef ARDUINO_ARCH_ESP8266
  Serial.print("Voltage      = "); Serial.print(ESP.getVcc() / 918.0); Serial.println("V"); // 918 empirically determined
#endif
Serial.print("Transactions = "); Serial.println((user.trans  ==  1) ? "Yes" : "No");
Serial.println("Interface    = SPI");
Serial.print("Display driver = "); Serial.println(user.tft_driver, HEX);
Serial.print("Display width  = "); Serial.println(user.tft_width);
Serial.print("Display height = "); Serial.println(user.tft_height);
Serial.println();

if (user.r0_x_offset  != 0)  { Serial.print("R0 x offset = "); Serial.println(user.r0_x_offset); } // Offsets, not all used yet
if (user.r0_y_offset  != 0)  { Serial.print("R0 y offset = "); Serial.println(user.r0_y_offset); }
if (user.r1_x_offset  != 0)  { Serial.print("R1 x offset = "); Serial.println(user.r1_x_offset); }
if (user.r1_y_offset  != 0)  { Serial.print("R1 y offset = "); Serial.println(user.r1_y_offset); }
if (user.r2_x_offset  != 0)  { Serial.print("R2 x offset = "); Serial.println(user.r2_x_offset); }
if (user.r2_y_offset  != 0)  { Serial.print("R2 y offset = "); Serial.println(user.r2_y_offset); }
if (user.r3_x_offset  != 0)  { Serial.print("R3 x offset = "); Serial.println(user.r3_x_offset); }
if (user.r3_y_offset  != 0)  { Serial.print("R3 y offset = "); Serial.println(user.r3_y_offset); }

if (user.pin_tft_mosi != -1) { Serial.print("MOSI    = "); Serial.print("GPIO "); Serial.println(getPinName(user.pin_tft_mosi)); }
if (user.pin_tft_miso != -1) { Serial.print("MISO    = "); Serial.print("GPIO "); Serial.println(getPinName(user.pin_tft_miso)); }
if (user.pin_tft_clk  != -1) { Serial.print("SCK     = "); Serial.print("GPIO "); Serial.println(getPinName(user.pin_tft_clk)); }

String pinNameRef = "D";
if (user.pin_tft_cs != -1) { Serial.print("TFT_CS   = " + pinNameRef); Serial.println(getPinName(user.pin_tft_cs)); }
if (user.pin_tft_dc != -1) { Serial.print("TFT_DC   = " + pinNameRef); Serial.println(getPinName(user.pin_tft_dc)); }
if (user.pin_tft_rst!= -1) { Serial.print("TFT_RST  = " + pinNameRef); Serial.println(getPinName(user.pin_tft_rst)); }


#if defined (TFT_BL)
  Serial.print("\nTFT_BL           = " + pinNameRef); Serial.println(getPinName(user.pin_tft_led));
  #if defined (TFT_BACKLIGHT_ON)
    Serial.print("TFT_BACKLIGHT_ON = "); Serial.println(user.pin_tft_led_on == HIGH ? "HIGH" : "LOW");
  #endif
#endif

Serial.println();

uint16_t fonts = tft.fontsLoaded();
if (fonts & (1 << 1))        Serial.print("Font GLCD   loaded\n");
if (fonts & (1 << 2))        Serial.print("Font 2      loaded\n");
if (fonts & (1 << 4))        Serial.print("Font 4      loaded\n");
if (fonts & (1 << 6))        Serial.print("Font 6      loaded\n");
if (fonts & (1 << 7))        Serial.print("Font 7      loaded\n");
if (fonts & (1 << 9))        Serial.print("Font 8N     loaded\n");
else
if (fonts & (1 << 8))        Serial.print("Font 8      loaded\n");
if (fonts & (1 << 15))       Serial.print("Smooth font enabled\n");
Serial.print("\n");

if (user.serial==1)        { Serial.print("Display SPI frequency = "); Serial.println(user.tft_spi_freq/10.0); }

Serial.println("[/code]");

delay(3000);
}

// Get pin name
int8_t getPinName(int8_t pin)
{
  // NodeMCU pin labels differ from GPIO numbers:
  // GPIO       Dxx
    if (pin == 16) return 0;
    if (pin ==  5) return 1;
    if (pin ==  4) return 2;
    if (pin ==  0) return 3;
    if (pin ==  2) return 4;
    if (pin == 14) return 5;
    if (pin == 12) return 6;
    if (pin == 13) return 7;
    if (pin == 15) return 8;
    if (pin ==  3) return 9;
    if (pin ==  1) return 10;
    if (pin ==  9) return 11;
    if (pin == 10) return 12;
  return pin;
}
