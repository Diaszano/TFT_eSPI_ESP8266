#define USER_SETUP_INFO "TFT_eSPI_ESP8266 default"

#define ST7789_DRIVER
#define TFT_WIDTH 240
#define TFT_HEIGHT 240

#define TFT_MOSI 13
#define TFT_SCLK 14
#define TFT_DC 0
#define TFT_RST 2
#define TFT_BL 5
#define TFT_BACKLIGHT_ON LOW
// TFT_CS not defined: CS tied to GND
// TFT_MISO not defined: display is write-only

#define SPI_FREQUENCY 40000000
// TFT_SPI_MODE defaults to SPI_MODE3 for ST7789

// Calibration knobs, confirm on hardware with Colour_Test
// #define TFT_RGB_ORDER TFT_BGR
// #define TFT_INVERSION_ON

#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT
