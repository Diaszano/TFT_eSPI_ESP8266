/// @file
/// @brief Public API and configuration for TFT_eSPI on ESP8266.
/***************************************************
  Arduino TFT graphics library for ESP8266.

  This is a stand-alone library that contains the
  hardware driver, the graphics functions and the
  proportional fonts.

  The built-in fonts 4, 6, 7 and 8 are Run Length
  Encoded (RLE) to reduce the FLASH footprint.

  Last review/edit by Bodmer: 04/02/22
 ****************************************************/

// Stop fonts etc. being loaded multiple times
#ifndef _TFT_eSPIH_
#define _TFT_eSPIH_

/// @brief TFT ESPI VERSION configuration constant.
#define TFT_ESPI_VERSION "2.5.44"

// Bit level feature flags
// Bit 0 set: viewport capability
/// @brief TFT ESPI FEATURES configuration constant.
#define TFT_ESPI_FEATURES 1

/***************************************************************************************
**                         Section 1: Load required header files
***************************************************************************************/

//Standard support
#include <Arduino.h>
#include <Print.h>
  #include <SPI.h>
/***************************************************************************************
**                         Section 2: Load library and processor specific header files
***************************************************************************************/
// Include header file that defines the fonts loaded, the TFT drivers
// available and the pins to be used, etc. etc.

// New ESP8266 board package uses ARDUINO_ARCH_ESP8266
// old package defined ESP8266

// The following lines allow the user setup to be included in the sketch folder, see
// "Sketch_with_tft_setup" generic example.
#if !defined __has_include
  #if !defined(DISABLE_ALL_LIBRARY_WARNINGS)
    #warning Compiler does not support __has_include, so sketches cannot define the setup
  #endif
#else
  #if __has_include(<tft_setup.h>)
    // Include the sketch setup file
    #include <tft_setup.h>
    #ifndef USER_SETUP_LOADED
      // Prevent loading further setups
      #define USER_SETUP_LOADED
    #endif
  #endif
#endif

#include <User_Setup_Select.h>

#ifndef ST7789_DRIVER
  #error "TFT_eSPI_ESP8266 supports only ST7789_DRIVER"
#endif
#if defined (TFT_PARALLEL_8_BIT) || defined (TFT_PARALLEL_16_BIT)
  #error "TFT_eSPI_ESP8266 supports only SPI"
#endif
#ifdef TOUCH_CS
  #error "TFT_eSPI_ESP8266 has no touch support"
#endif

  #include "TFT_Drivers/ST7789_Defines.h"
/// @brief TFT DRIVER configuration constant.
  #define TFT_DRIVER 0x7789

// Handle FLASH based storage e.g. PROGMEM
  #include <pgmspace.h>

// Include the processor specific drivers
// ESP8266 SPI layer
// Processor ID reported by getSetup()
/// @brief PROCESSOR ID configuration constant.
#define PROCESSOR_ID 0x8266

// Include processor specific header
// None

// Processor specific code used by SPI bus transaction startWrite and endWrite functions
/// @brief SET BUS WRITE MODE configuration constant.
#define SET_BUS_WRITE_MODE SPI1U=SPI1U_WRITE
/// @brief SET BUS READ MODE configuration constant.
#define SET_BUS_READ_MODE  SPI1U=SPI1U_READ

// Initialise processor specific SPI functions, used by init()
#if (!defined (SUPPORT_TRANSACTIONS) && defined (ARDUINO_ARCH_ESP8266))
  #define INIT_TFT_DATA_BUS \
    spi.setBitOrder(MSBFIRST); \
    spi.setDataMode(TFT_SPI_MODE); \
    spi.setFrequency(SPI_FREQUENCY);
  #else
/// @brief INIT TFT DATA BUS configuration constant.
    #define INIT_TFT_DATA_BUS
#endif

// If smooth fonts are enabled the filing system may need to be loaded
#ifdef SMOOTH_FONT
  // Call up the SPIFFS FLASH filing system for the anti-aliased fonts
/// @brief FS NO GLOBALS configuration constant.
  #define FS_NO_GLOBALS
  #include <FS.h>
/// @brief FONT FS AVAILABLE configuration constant.
  #define FONT_FS_AVAILABLE
#endif



/// @cond INTERNAL
////////////////////////////////////////////////////////////////////////////////////////
// Define the DC (TFT Data/Command or Register Select (RS))pin drive code
////////////////////////////////////////////////////////////////////////////////////////
#ifndef TFT_DC
  #define DC_C // No macro allocated so it generates no code
  #define DC_D // No macro allocated so it generates no code
#else
  #if (TFT_DC == 16)
    #define DC_C digitalWrite(TFT_DC, LOW)
    #define DC_D digitalWrite(TFT_DC, HIGH)
  #else
/// @brief DC C configuration constant.
    #define DC_C GPOC=dcpinmask
/// @brief DC D configuration constant.
    #define DC_D GPOS=dcpinmask
  #endif
#endif

////////////////////////////////////////////////////////////////////////////////////////
// Define the CS (TFT chip select) pin drive code
////////////////////////////////////////////////////////////////////////////////////////
#ifndef TFT_CS
/// @brief CS L configuration constant.
  #define CS_L // No macro allocated so it generates no code
/// @brief CS H configuration constant.
  #define CS_H // No macro allocated so it generates no code
#else
  #if (TFT_CS == 16)
    #define CS_L digitalWrite(TFT_CS, LOW)
    #define CS_H digitalWrite(TFT_CS, HIGH)
  #else
    #define CS_L GPOC=cspinmask
    #define CS_H GPOS=cspinmask
  #endif
#endif

////////////////////////////////////////////////////////////////////////////////////////
// Define the WR (TFT Write) pin drive code
////////////////////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////////////////////
// Define the touch screen chip select pin drive code
////////////////////////////////////////////////////////////////////////////////////////
/// @brief T CS L configuration constant.
  #define T_CS_L // No macro allocated so it generates no code
/// @brief T CS H configuration constant.
  #define T_CS_H // No macro allocated so it generates no code
/// @endcond

////////////////////////////////////////////////////////////////////////////////////////
// Make sure TFT_MISO is defined if not used to avoid an error message
////////////////////////////////////////////////////////////////////////////////////////
#ifndef TFT_MISO
/// @brief TFT MISO configuration constant.
  #define TFT_MISO -1
#endif

/// @cond INTERNAL
////////////////////////////////////////////////////////////////////////////////////////
// ESP8266 specific SPI macros
////////////////////////////////////////////////////////////////////////////////////////
#if defined (TFT_SPI_OVERLAP)
  #undef TFT_CS
  #define SPI1U_WRITE (SPIUMOSI | SPIUSSE | SPIUCSSETUP | SPIUCSHOLD)
  #define SPI1U_READ  (SPIUMOSI | SPIUSSE | SPIUCSSETUP | SPIUCSHOLD | SPIUDUPLEX)
#else
/// @brief SPI1U WRITE configuration constant.
  #define SPI1U_WRITE (SPIUMOSI | SPIUSSE)
/// @brief SPI1U READ configuration constant.
  #define SPI1U_READ  (SPIUMOSI | SPIUSSE | SPIUDUPLEX)
#endif

////////////////////////////////////////////////////////////////////////////////////////
// Macros to write commands and pixel colour data over SPI
////////////////////////////////////////////////////////////////////////////////////////
  // Command is 8 bits
/// @brief CMD BITS configuration constant.
  #define CMD_BITS 8

/// @brief tft Write 8 configuration constant.
  #define tft_Write_8(C) \
  SPI1U1 = ((CMD_BITS-1) << SPILMOSI) | ((CMD_BITS-1) << SPILMISO); \
  SPI1W0 = (C)<<(CMD_BITS - 8); \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

/// @brief tft Write 16 configuration constant.
  #define tft_Write_16(C) \
  SPI1U1 = (15 << SPILMOSI) | (15 << SPILMISO); \
  SPI1W0 = ((C)<<8 | (C)>>8); \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

/// @brief tft Write 16N configuration constant.
  #define tft_Write_16N(C) \
  SPI1U1 = (15 << SPILMOSI) | (15 << SPILMISO); \
  SPI1W0 = ((C)<<8 | (C)>>8); \
  SPI1CMD |= SPIBUSY

/// @brief tft Write 16S configuration constant.
  #define tft_Write_16S(C) \
  SPI1U1 = (15 << SPILMOSI) | (15 << SPILMISO); \
  SPI1W0 = C; \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

/// @brief tft Write 32 configuration constant.
  #define tft_Write_32(C) \
  SPI1U1 = (31 << SPILMOSI) | (31 << SPILMISO); \
  SPI1W0 = C; \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

/// @brief tft Write 32C configuration constant.
  #define tft_Write_32C(C,D) \
  SPI1U1 = (31 << SPILMOSI) | (31 << SPILMISO); \
  SPI1W0 = ((D)>>8 | (D)<<8)<<16 | ((C)>>8 | (C)<<8); \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

/// @brief tft Write 32D configuration constant.
  #define tft_Write_32D(C) \
  SPI1U1 = (31 << SPILMOSI) | (31 << SPILMISO); \
  SPI1W0 = ((C)>>8 | (C)<<8)<<16 | ((C)>>8 | (C)<<8); \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}


#ifndef tft_Write_16N
  #define tft_Write_16N tft_Write_16
#endif

////////////////////////////////////////////////////////////////////////////////////////
// Macros to read from display using SPI or software SPI
////////////////////////////////////////////////////////////////////////////////////////
  // Use a SPI read transfer
/// @brief tft Read 8 configuration constant.
  #define tft_Read_8() spi.transfer(0)

// Concatenate a byte sequence A,B,C,D to CDAB, P is a uint8_t pointer
/// @brief DAT8TO32 configuration constant.
#define DAT8TO32(P) ( (uint32_t)P[0]<<8 | P[1] | P[2]<<24 | P[3]<<16 )
/// @endcond

/***************************************************************************************
**                         Section 3: Interface setup
***************************************************************************************/
#ifndef TAB_COLOUR
/// @brief TAB COLOUR configuration constant.
  #define TAB_COLOUR 0
#endif

// If the SPI frequency is not defined, set a default
#ifndef SPI_FREQUENCY
  #define SPI_FREQUENCY  20000000
#endif

// If the SPI read frequency is not defined, set a default
#ifndef SPI_READ_FREQUENCY
/// @brief SPI READ FREQUENCY configuration constant.
  #define SPI_READ_FREQUENCY 10000000
#endif

// Some ST7789 boards do not work with Mode 0
#ifndef TFT_SPI_MODE
/// @brief TFT SPI MODE configuration constant.
    #define TFT_SPI_MODE SPI_MODE3
#endif

#ifndef SPI_BUSY_CHECK
/// @brief SPI BUSY CHECK configuration constant.
  #define SPI_BUSY_CHECK
#endif

// If half duplex SDA mode is defined then MISO pin should be -1

/***************************************************************************************
**                         Section 4: Setup fonts
***************************************************************************************/
// Use GLCD font in error case where user requests a smooth font file
// that does not exist (temporary workaround)
#ifdef SMOOTH_FONT
  #ifndef LOAD_GLCD
    #define LOAD_GLCD
  #endif
#endif

// Only load the fonts defined in User_Setup.h (to save space)
// Set flag so RLE rendering code is optionally compiled
#ifdef LOAD_GLCD
  #include <Fonts/glcdfont.c>
#endif

#ifdef LOAD_FONT2
  #include <Fonts/Font16.h>
#endif

#ifdef LOAD_FONT4
  #include <Fonts/Font32rle.h>
/// @brief LOAD RLE configuration constant.
  #define LOAD_RLE
#endif

#ifdef LOAD_FONT6
  #include <Fonts/Font64rle.h>
  #ifndef LOAD_RLE
    #define LOAD_RLE
  #endif
#endif

#ifdef LOAD_FONT7
  #include <Fonts/Font7srle.h>
  #ifndef LOAD_RLE
    #define LOAD_RLE
  #endif
#endif

#ifdef LOAD_FONT8
  #include <Fonts/Font72rle.h>
  #ifndef LOAD_RLE
    #define LOAD_RLE
  #endif
#elif defined LOAD_FONT8N // Optional narrower version
  #define LOAD_FONT8
  #include <Fonts/Font72x53rle.h>
  #ifndef LOAD_RLE
    #define LOAD_RLE
  #endif
#endif

#ifdef LOAD_GFXFF
  // We can include all the free fonts and they will only be built into
  // the sketch if they are used
  #include <Fonts/GFXFF/gfxfont.h>
  // Call up any user custom fonts
  #include <User_Setups/User_Custom_Fonts.h>
#endif // #ifdef LOAD_GFXFF

// Create a null default font in case some fonts not used (to prevent crash)
/// @brief Fallback width table used when a font is not loaded.
const  uint8_t widtbl_null[1] = {0};
/// @brief Fallback character bitmap used when a font is not loaded.
PROGMEM const uint8_t chr_null[1] = {0};
/// @brief Fallback character table used when a font is not loaded.
PROGMEM const uint8_t* const chrtbl_null[1] = {chr_null};

// This is a structure to conveniently hold information on the default fonts
// Stores pointer to font character image address table, width table and height
/// @brief fontinfo API.
typedef struct {
    const uint8_t *chartbl; ///< chartbl value.
    const uint8_t *widthtbl; ///< widthtbl value.
    uint8_t height; ///< height value.
    uint8_t baseline; ///< baseline value.
    } fontinfo;

// Now fill the structure
/// @brief Metadata table for the built-in fonts.
const PROGMEM fontinfo fontdata [] = {
  #ifdef LOAD_GLCD
   { (const uint8_t *)font, widtbl_null, 0, 0 },
  #else
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 },
  #endif
   // GLCD font (Font 1) does not have all parameters
   { (const uint8_t *)chrtbl_null, widtbl_null, 8, 7 },

  #ifdef LOAD_FONT2
   { (const uint8_t *)chrtbl_f16, widtbl_f16, chr_hgt_f16, baseline_f16},
  #else
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 },
  #endif

   // Font 3 current unused
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 },

  #ifdef LOAD_FONT4
   { (const uint8_t *)chrtbl_f32, widtbl_f32, chr_hgt_f32, baseline_f32},
  #else
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 },
  #endif

   // Font 5 current unused
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 },

  #ifdef LOAD_FONT6
   { (const uint8_t *)chrtbl_f64, widtbl_f64, chr_hgt_f64, baseline_f64},
  #else
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 },
  #endif

  #ifdef LOAD_FONT7
   { (const uint8_t *)chrtbl_f7s, widtbl_f7s, chr_hgt_f7s, baseline_f7s},
  #else
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 },
  #endif

  #ifdef LOAD_FONT8
   { (const uint8_t *)chrtbl_f72, widtbl_f72, chr_hgt_f72, baseline_f72}
  #else
   { (const uint8_t *)chrtbl_null, widtbl_null, 0, 0 }
  #endif
};

/***************************************************************************************
**                         Section 5: Font datum enumeration
***************************************************************************************/
//These enumerate the text plotting alignment (reference datum point)
/// @brief TL DATUM configuration constant.
#define TL_DATUM 0 // Top left (default)
/// @brief TC DATUM configuration constant.
#define TC_DATUM 1 // Top centre
/// @brief TR DATUM configuration constant.
#define TR_DATUM 2 // Top right
/// @brief ML DATUM configuration constant.
#define ML_DATUM 3 // Middle left
/// @brief CL DATUM configuration constant.
#define CL_DATUM 3 // Centre left, same as above
/// @brief MC DATUM configuration constant.
#define MC_DATUM 4 // Middle centre
/// @brief CC DATUM configuration constant.
#define CC_DATUM 4 // Centre centre, same as above
/// @brief MR DATUM configuration constant.
#define MR_DATUM 5 // Middle right
/// @brief CR DATUM configuration constant.
#define CR_DATUM 5 // Centre right, same as above
/// @brief BL DATUM configuration constant.
#define BL_DATUM 6 // Bottom left
/// @brief BC DATUM configuration constant.
#define BC_DATUM 7 // Bottom centre
/// @brief BR DATUM configuration constant.
#define BR_DATUM 8 // Bottom right
/// @brief L BASELINE configuration constant.
#define L_BASELINE  9 // Left character baseline (Line the 'A' character would sit on)
/// @brief C BASELINE configuration constant.
#define C_BASELINE 10 // Centre character baseline
/// @brief R BASELINE configuration constant.
#define R_BASELINE 11 // Right character baseline

/***************************************************************************************
**                         Section 6: Colour enumeration
***************************************************************************************/
// Default color definitions
/// @brief TFT BLACK configuration constant.
#define TFT_BLACK       0x0000      /*   0,   0,   0 */
/// @brief TFT NAVY configuration constant.
#define TFT_NAVY        0x000F      /*   0,   0, 128 */
/// @brief TFT DARKGREEN configuration constant.
#define TFT_DARKGREEN   0x03E0      /*   0, 128,   0 */
/// @brief TFT DARKCYAN configuration constant.
#define TFT_DARKCYAN    0x03EF      /*   0, 128, 128 */
/// @brief TFT MAROON configuration constant.
#define TFT_MAROON      0x7800      /* 128,   0,   0 */
/// @brief TFT PURPLE configuration constant.
#define TFT_PURPLE      0x780F      /* 128,   0, 128 */
/// @brief TFT OLIVE configuration constant.
#define TFT_OLIVE       0x7BE0      /* 128, 128,   0 */
/// @brief TFT LIGHTGREY configuration constant.
#define TFT_LIGHTGREY   0xD69A      /* 211, 211, 211 */
/// @brief TFT DARKGREY configuration constant.
#define TFT_DARKGREY    0x7BEF      /* 128, 128, 128 */
/// @brief TFT BLUE configuration constant.
#define TFT_BLUE        0x001F      /*   0,   0, 255 */
/// @brief TFT GREEN configuration constant.
#define TFT_GREEN       0x07E0      /*   0, 255,   0 */
/// @brief TFT CYAN configuration constant.
#define TFT_CYAN        0x07FF      /*   0, 255, 255 */
/// @brief TFT RED configuration constant.
#define TFT_RED         0xF800      /* 255,   0,   0 */
/// @brief TFT MAGENTA configuration constant.
#define TFT_MAGENTA     0xF81F      /* 255,   0, 255 */
/// @brief TFT YELLOW configuration constant.
#define TFT_YELLOW      0xFFE0      /* 255, 255,   0 */
/// @brief TFT WHITE configuration constant.
#define TFT_WHITE       0xFFFF      /* 255, 255, 255 */
/// @brief TFT ORANGE configuration constant.
#define TFT_ORANGE      0xFDA0      /* 255, 180,   0 */
/// @brief TFT GREENYELLOW configuration constant.
#define TFT_GREENYELLOW 0xB7E0      /* 180, 255,   0 */
/// @brief TFT PINK configuration constant.
#define TFT_PINK        0xFE19      /* 255, 192, 203 */ //Lighter pink, was 0xFC9F
/// @brief TFT BROWN configuration constant.
#define TFT_BROWN       0x9A60      /* 150,  75,   0 */
/// @brief TFT GOLD configuration constant.
#define TFT_GOLD        0xFEA0      /* 255, 215,   0 */
/// @brief TFT SILVER configuration constant.
#define TFT_SILVER      0xC618      /* 192, 192, 192 */
/// @brief TFT SKYBLUE configuration constant.
#define TFT_SKYBLUE     0x867D      /* 135, 206, 235 */
/// @brief TFT VIOLET configuration constant.
#define TFT_VIOLET      0x915C      /* 180,  46, 226 */

// Next is a special 16-bit colour value that encodes to 8 bits
// and will then decode back to the same 16-bit value.
// Convenient for 8-bit and 16-bit transparent sprites.
/// @brief TFT TRANSPARENT configuration constant.
#define TFT_TRANSPARENT 0x0120 // This is actually a dark green

// Default palette for 4-bit colour sprites
static const uint16_t default_4bit_palette[] PROGMEM = {
  TFT_BLACK,    //  0  ^
  TFT_BROWN,    //  1  |
  TFT_RED,      //  2  |
  TFT_ORANGE,   //  3  |
  TFT_YELLOW,   //  4  Colours 0-9 follow the resistor colour code!
  TFT_GREEN,    //  5  |
  TFT_BLUE,     //  6  |
  TFT_PURPLE,   //  7  |
  TFT_DARKGREY, //  8  |
  TFT_WHITE,    //  9  v
  TFT_CYAN,     // 10  Blue+green mix
  TFT_MAGENTA,  // 11  Blue+red mix
  TFT_MAROON,   // 12  Darker red colour
  TFT_DARKGREEN,// 13  Darker green colour
  TFT_NAVY,     // 14  Darker blue colour
  TFT_PINK      // 15
};

/***************************************************************************************
**                         Section 7: Diagnostic support
***************************************************************************************/
// #define TFT_eSPI_DEBUG     // Switch on debug support serial messages  (not used yet)
// #define TFT_eSPI_FNx_DEBUG // Switch on debug support for function "x" (not used yet)

// This structure allows sketches to retrieve the user setup parameters at runtime
// by calling getSetup(), zero impact on code size unless used, mainly for diagnostics
/// @brief setup_t API.
typedef struct
{
String  version = TFT_ESPI_VERSION; ///< version value.
String  setup_info;  ///< Setup reference name available to use in a user setup
uint32_t setup_id;   ///< ID available to use in a user setup
int32_t esp;         ///< Processor code
uint8_t trans;       ///< SPI transaction support
uint8_t serial;      ///< SPI interface
uint8_t  port;       ///< SPI port
uint8_t overlap;     ///< ESP8266 overlap mode
uint8_t interface;   ///< Interface type

uint16_t tft_driver; ///< Hexadecimal code
uint16_t tft_width;  ///< Rotation 0 width and height
uint16_t tft_height; ///< tft height value.

uint8_t r0_x_offset; ///< Display offsets, not all used yet
uint8_t r0_y_offset; ///< r0 y offset value.
uint8_t r1_x_offset; ///< r1 x offset value.
uint8_t r1_y_offset; ///< r1 y offset value.
uint8_t r2_x_offset; ///< r2 x offset value.
uint8_t r2_y_offset; ///< r2 y offset value.
uint8_t r3_x_offset; ///< r3 x offset value.
uint8_t r3_y_offset; ///< r3 y offset value.

int8_t pin_tft_mosi; ///< SPI pins
int8_t pin_tft_miso; ///< pin tft miso value.
int8_t pin_tft_clk; ///< pin tft clk value.
int8_t pin_tft_cs; ///< pin tft cs value.

int8_t pin_tft_dc;   ///< Control pins
int8_t pin_tft_rd; ///< pin tft rd value.
int8_t pin_tft_wr; ///< pin tft wr value.
int8_t pin_tft_rst; ///< pin tft rst value.

int8_t pin_tft_d0;   ///< Data pin
int8_t pin_tft_d1; ///< pin tft d1 value.
int8_t pin_tft_d2; ///< pin tft d2 value.
int8_t pin_tft_d3; ///< pin tft d3 value.
int8_t pin_tft_d4; ///< pin tft d4 value.
int8_t pin_tft_d5; ///< pin tft d5 value.
int8_t pin_tft_d6; ///< pin tft d6 value.
int8_t pin_tft_d7; ///< pin tft d7 value.

int8_t pin_tft_led; ///< pin tft led value.
int8_t pin_tft_led_on; ///< pin tft led on value.


int16_t tft_spi_freq;///< TFT write SPI frequency
int16_t tft_rd_freq; ///< TFT read  SPI frequency
} setup_t;

/***************************************************************************************
**                         Section 8: Class member and support functions
***************************************************************************************/

/// @brief Callback used to read smooth-font pixel colors.
typedef uint16_t (*getColorCallback)(uint16_t x, uint16_t y);

// Class functions and variables
/// @brief TFT_eSPI API.
class TFT_eSPI : public Print { friend class TFT_eSprite; // Sprite class has access to protected members

 //--------------------------------------- public ------------------------------------//
 public:

/// @brief Creates a display driver instance.
  TFT_eSPI(int16_t _W = TFT_WIDTH, int16_t _H = TFT_HEIGHT);

  // init() and begin() are equivalent, begin() included for backwards compatibility
  // Sketch-defined tab colour option
/// @brief Initializes the display.
/// @brief Initializes the display.
  /// @brief Initializes the display.
  void     init(uint8_t tc = TAB_COLOUR);
  /// @brief Initializes the display (backward-compatible alias).
  void     begin(uint8_t tc = TAB_COLOUR);

  // These are virtual so the TFT_eSprite class can override them with sprite specific functions
/// @brief Draws a pixel.
  virtual void     drawPixel(int32_t x, int32_t y, uint32_t color),
/// @brief drawChar operation.
                   drawChar(int32_t x, int32_t y, uint16_t c, uint32_t color, uint32_t bg, uint8_t size),
/// @brief drawLine operation.
                   drawLine(int32_t xs, int32_t ys, int32_t xe, int32_t ye, uint32_t color),
/// @brief drawFastVLine operation.
                   drawFastVLine(int32_t x, int32_t y, int32_t h, uint32_t color),
/// @brief drawFastHLine operation.
                   drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t color),
/// @brief fillRect operation.
                   fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color);

/// @brief drawChar operation.
  virtual int16_t  drawChar(uint16_t uniCode, int32_t x, int32_t y, uint8_t font),
/// @brief drawChar operation.
                   drawChar(uint16_t uniCode, int32_t x, int32_t y),
/// @brief height operation.
                   height(void),
/// @brief width operation.
                   width(void);

                   // Read the colour of a pixel at x,y and return value in 565 format
/// @brief Reads a pixel from the display.
  virtual uint16_t readPixel(int32_t x, int32_t y);

/// @brief setWindow operation.
  virtual void     setWindow(int32_t xs, int32_t ys, int32_t xe, int32_t ye);   // Note: start + end coordinates

                   // Push (aka write pixel) colours to the set window
/// @brief pushColor operation.
  virtual void     pushColor(uint16_t color);

                   // These are non-inlined to enable override
/// @brief begin nin write operation.
  virtual void     begin_nin_write();
/// @brief end nin write operation.
  virtual void     end_nin_write();

/// @brief setRotation operation.
  void     setRotation(uint8_t r); // Set the display image orientation to 0, 1, 2 or 3
/// @brief getRotation operation.
  uint8_t  getRotation(void);      // Read the current rotation

  // Change the origin position from the default top left
  // Note: setRotation, setViewport and resetViewport will revert origin to top left corner of screen/sprite
/// @brief setOrigin operation.
  void     setOrigin(int32_t x, int32_t y);
/// @brief getOriginX operation.
  int32_t  getOriginX(void);
/// @brief getOriginY operation.
  int32_t  getOriginY(void);

/// @brief invertDisplay operation.
  void     invertDisplay(bool i);  // Tell TFT to invert all displayed colours


  // The TFT_eSprite class inherits the following functions (not all are useful to Sprite class
/// @brief setAddrWindow operation.
  void     setAddrWindow(int32_t xs, int32_t ys, int32_t w, int32_t h); // Note: start coordinates + width and height

  // Viewport commands, see "Viewport_Demo" sketch
/// @brief setViewport operation.
  void     setViewport(int32_t x, int32_t y, int32_t w, int32_t h, bool vpDatum = true);
/// @brief checkViewport operation.
  bool     checkViewport(int32_t x, int32_t y, int32_t w, int32_t h);
/// @brief getViewportX operation.
  int32_t  getViewportX(void);
/// @brief getViewportY operation.
  int32_t  getViewportY(void);
/// @brief getViewportWidth operation.
  int32_t  getViewportWidth(void);
/// @brief getViewportHeight operation.
  int32_t  getViewportHeight(void);
/// @brief getViewportDatum operation.
  bool     getViewportDatum(void);
/// @brief frameViewport operation.
  void     frameViewport(uint16_t color, int32_t w);
/// @brief resetViewport operation.
  void     resetViewport(void);

           // Clip input window to viewport bounds, return false if whole area is out of bounds
/// @brief clipAddrWindow operation.
  bool     clipAddrWindow(int32_t* x, int32_t* y, int32_t* w, int32_t* h);
           // Clip input window area to viewport bounds, return false if whole area is out of bounds
/// @brief clipWindow operation.
  bool     clipWindow(int32_t* xs, int32_t* ys, int32_t* xe, int32_t* ye);

           // Push (aka write pixel) colours to the TFT (use setAddrWindow() first)
/// @brief pushColor operation.
  void     pushColor(uint16_t color, uint32_t len),  // Deprecated, use pushBlock()
/// @brief pushColors operation.
           pushColors(uint16_t  *data, uint32_t len, bool swap = true), // With byte swap option
/// @brief pushColors operation.
           pushColors(uint8_t  *data, uint32_t len); // Deprecated, use pushPixels()

           // Write a solid block of a single colour
/// @brief pushBlock operation.
  void     pushBlock(uint16_t color, uint32_t len);

           // Write a set of pixels stored in memory, use setSwapBytes(true/false) function to correct endianess
/// @brief pushPixels operation.
  void     pushPixels(const void * data_in, uint32_t len);

           // Support for half duplex (bi-directional SDA) SPI bus where MOSI must be switched to input


  // Graphics drawing
/// @brief fillScreen operation.
  void     fillScreen(uint32_t color),
/// @brief drawRect operation.
           drawRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color),
/// @brief drawRoundRect operation.
           drawRoundRect(int32_t x, int32_t y, int32_t w, int32_t h, int32_t radius, uint32_t color),
/// @brief fillRoundRect operation.
           fillRoundRect(int32_t x, int32_t y, int32_t w, int32_t h, int32_t radius, uint32_t color);

/// @brief fillRectVGradient operation.
  void     fillRectVGradient(int16_t x, int16_t y, int16_t w, int16_t h, uint32_t color1, uint32_t color2);
/// @brief fillRectHGradient operation.
  void     fillRectHGradient(int16_t x, int16_t y, int16_t w, int16_t h, uint32_t color1, uint32_t color2);

/// @brief drawCircle operation.
  void     drawCircle(int32_t x, int32_t y, int32_t r, uint32_t color),
/// @brief drawCircleHelper operation.
           drawCircleHelper(int32_t x, int32_t y, int32_t r, uint8_t cornername, uint32_t color),
/// @brief fillCircle operation.
           fillCircle(int32_t x, int32_t y, int32_t r, uint32_t color),
/// @brief fillCircleHelper operation.
           fillCircleHelper(int32_t x, int32_t y, int32_t r, uint8_t cornername, int32_t delta, uint32_t color),

/// @brief drawEllipse operation.
           drawEllipse(int16_t x, int16_t y, int32_t rx, int32_t ry, uint16_t color),
/// @brief fillEllipse operation.
           fillEllipse(int16_t x, int16_t y, int32_t rx, int32_t ry, uint16_t color),

           //                 Corner 1               Corner 2               Corner 3
/// @brief drawTriangle operation.
           drawTriangle(int32_t x1,int32_t y1, int32_t x2,int32_t y2, int32_t x3,int32_t y3, uint32_t color),
/// @brief fillTriangle operation.
           fillTriangle(int32_t x1,int32_t y1, int32_t x2,int32_t y2, int32_t x3,int32_t y3, uint32_t color);


  // Smooth (anti-aliased) graphics drawing
           // Draw a pixel blended with the background pixel colour (bg_color) specified,  return blended colour
           // If the bg_color is not specified, the background pixel colour will be read from TFT or sprite
/// @brief Draws a pixel.
  uint16_t drawPixel(int32_t x, int32_t y, uint32_t color, uint8_t alpha, uint32_t bg_color = 0x00FFFFFF);

           // Draw an anti-aliased (smooth) arc between start and end angles. Arc ends are anti-aliased.
           // By default the arc is drawn with square ends unless the "roundEnds" parameter is included and set true
           // Angle = 0 is at 6 o'clock position, 90 at 9 o'clock etc. The angles must be in range 0-360 or they will be clipped to these limits
           // The start angle may be larger than the end angle. Arcs are always drawn clockwise from the start angle.
/// @brief drawSmoothArc operation.
  void     drawSmoothArc(int32_t x, int32_t y, int32_t r, int32_t ir, uint32_t startAngle, uint32_t endAngle, uint32_t fg_color, uint32_t bg_color, bool roundEnds = false);

           // As per "drawSmoothArc" except the ends of the arc are NOT anti-aliased, this facilitates dynamic arc length changes with
           // arc segments and ensures clean segment joints. 
           // The sides of the arc are anti-aliased by default. If smoothArc is false sides will NOT be anti-aliased
/// @brief drawArc operation.
  void     drawArc(int32_t x, int32_t y, int32_t r, int32_t ir, uint32_t startAngle, uint32_t endAngle, uint32_t fg_color, uint32_t bg_color, bool smoothArc = true);

           // Draw an anti-aliased filled circle at x, y with radius r
           // Note: The thickness of line is 3 pixels to reduce the visible "braiding" effect of anti-aliasing narrow lines
           //       this means the inner anti-alias zone is always at r-1 and the outer zone at r+1
/// @brief drawSmoothCircle operation.
  void     drawSmoothCircle(int32_t x, int32_t y, int32_t r, uint32_t fg_color, uint32_t bg_color);
  
           // Draw an anti-aliased filled circle at x, y with radius r
           // If bg_color is not included the background pixel colour will be read from TFT or sprite
/// @brief fillSmoothCircle operation.
  void     fillSmoothCircle(int32_t x, int32_t y, int32_t r, uint32_t color, uint32_t bg_color = 0x00FFFFFF);

           // Draw a rounded rectangle that has a line thickness of r-ir+1 and bounding box defined by x,y and w,h
           // The outer corner radius is r, inner corner radius is ir
           // The inside and outside of the border are anti-aliased
/// @brief drawSmoothRoundRect operation.
  void     drawSmoothRoundRect(int32_t x, int32_t y, int32_t r, int32_t ir, int32_t w, int32_t h, uint32_t fg_color, uint32_t bg_color = 0x00FFFFFF, uint8_t quadrants = 0xF);

           // Draw a filled rounded rectangle , corner radius r and bounding box defined by x,y and w,h
/// @brief fillSmoothRoundRect operation.
  void     fillSmoothRoundRect(int32_t x, int32_t y, int32_t w, int32_t h, int32_t radius, uint32_t color, uint32_t bg_color = 0x00FFFFFF);

           // Draw a small anti-aliased filled circle at ax,ay with radius r (uses drawWideLine)
           // If bg_color is not included the background pixel colour will be read from TFT or sprite
/// @brief drawSpot operation.
  void     drawSpot(float ax, float ay, float r, uint32_t fg_color, uint32_t bg_color = 0x00FFFFFF);

           // Draw an anti-aliased wide line from ax,ay to bx,by width wd with radiused ends (radius is wd/2)
           // If bg_color is not included the background pixel colour will be read from TFT or sprite
/// @brief drawWideLine operation.
  void     drawWideLine(float ax, float ay, float bx, float by, float wd, uint32_t fg_color, uint32_t bg_color = 0x00FFFFFF);

           // Draw an anti-aliased wide line from ax,ay to bx,by with different width at each end aw, bw and with radiused ends
           // If bg_color is not included the background pixel colour will be read from TFT or sprite
/// @brief drawWedgeLine operation.
  void     drawWedgeLine(float ax, float ay, float bx, float by, float aw, float bw, uint32_t fg_color, uint32_t bg_color = 0x00FFFFFF);


  // Image rendering
           // Swap the byte order for pushImage() and pushPixels() - corrects endianness
/// @brief setSwapBytes operation.
  void     setSwapBytes(bool swap);
/// @brief getSwapBytes operation.
  bool     getSwapBytes(void);

           // Draw bitmap
/// @brief drawBitmap operation.
  void     drawBitmap( int16_t x, int16_t y, const uint8_t *bitmap, int16_t w, int16_t h, uint16_t fgcolor),
/// @brief drawBitmap operation.
           drawBitmap( int16_t x, int16_t y, const uint8_t *bitmap, int16_t w, int16_t h, uint16_t fgcolor, uint16_t bgcolor),
/// @brief drawXBitmap operation.
           drawXBitmap(int16_t x, int16_t y, const uint8_t *bitmap, int16_t w, int16_t h, uint16_t fgcolor),
/// @brief drawXBitmap operation.
           drawXBitmap(int16_t x, int16_t y, const uint8_t *bitmap, int16_t w, int16_t h, uint16_t fgcolor, uint16_t bgcolor),
/// @brief setBitmapColor operation.
           setBitmapColor(uint16_t fgcolor, uint16_t bgcolor); // Define the 2 colours for 1bpp sprites

           // Set TFT pivot point (use when rendering rotated sprites)
/// @brief setPivot operation.
  void     setPivot(int16_t x, int16_t y);
/// @brief getPivotX operation.
  int16_t  getPivotX(void), // Get pivot x
/// @brief getPivotY operation.
           getPivotY(void); // Get pivot y

           // The next functions can be used as a pair to copy screen blocks (or horizontal/vertical lines) to another location
           // Read a block of pixels to a data buffer, buffer is 16-bit and the size must be at least w * h
/// @brief readRect operation.
  void     readRect(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data);
           // Write a block of pixels to the screen which have been read by readRect()
/// @brief pushRect operation.
  void     pushRect(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data);

           // These are used to render images or sprites stored in RAM arrays (used by Sprite class for 16bpp Sprites)
/// @brief pushImage operation.
  void     pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data);
/// @brief pushImage operation.
  void     pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data, uint16_t transparent);

           // These are used to render images stored in FLASH (PROGMEM)
/// @brief pushImage operation.
  void     pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t *data, uint16_t transparent);
/// @brief pushImage operation.
  void     pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t *data);

           // These are used by Sprite class pushSprite() member function for 1, 4 and 8 bits per pixel (bpp) colours
           // They are not intended to be used with user sketches (but could be)
           // Set bpp8 true for 8bpp sprites, false otherwise. The cmap pointer must be specified for 4bpp
/// @brief pushImage operation.
  void     pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint8_t  *data, bool bpp8 = true, uint16_t *cmap = nullptr);
/// @brief pushImage operation.
  void     pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint8_t  *data, uint8_t  transparent, bool bpp8 = true, uint16_t *cmap = nullptr);
           // FLASH version
/// @brief pushImage operation.
  void     pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint8_t *data, bool bpp8,  uint16_t *cmap = nullptr);

           // Render a 16-bit colour image with a 1bpp mask
/// @brief pushMaskedImage operation.
  void     pushMaskedImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *img, uint8_t *mask);

           // This next function has been used successfully to dump the TFT screen to a PC for documentation purposes
           // It reads a screen area and returns the 3 RGB 8-bit colour values of each pixel in the buffer
           // Set w and h to 1 to read 1 pixel's colour. The data buffer must be at least w * h * 3 bytes
/// @brief readRectRGB operation.
  void     readRectRGB(int32_t x, int32_t y, int32_t w, int32_t h, uint8_t *data);


  // Text rendering - value returned is the pixel width of the rendered text
/// @brief drawNumber operation.
  int16_t  drawNumber(long intNumber, int32_t x, int32_t y, uint8_t font), // Draw integer using specified font number
/// @brief drawNumber operation.
           drawNumber(long intNumber, int32_t x, int32_t y),               // Draw integer using current font

           // Decimal is the number of decimal places to render
           // Use with setTextDatum() to position values on TFT, and setTextPadding() to blank old displayed values
/// @brief drawFloat operation.
           drawFloat(float floatNumber, uint8_t decimal, int32_t x, int32_t y, uint8_t font), // Draw float using specified font number
/// @brief drawFloat operation.
           drawFloat(float floatNumber, uint8_t decimal, int32_t x, int32_t y),               // Draw float using current font

           // Handle char arrays
           // Use with setTextDatum() to position string on TFT, and setTextPadding() to blank old displayed strings
/// @brief drawString operation.
           drawString(const char *string, int32_t x, int32_t y, uint8_t font),  // Draw string using specified font number
/// @brief drawString operation.
           drawString(const char *string, int32_t x, int32_t y),                // Draw string using current font
/// @brief drawString operation.
           drawString(const String& string, int32_t x, int32_t y, uint8_t font),// Draw string using specified font number
/// @brief drawString operation.
           drawString(const String& string, int32_t x, int32_t y),              // Draw string using current font

/// @brief drawCentreString operation.
           drawCentreString(const char *string, int32_t x, int32_t y, uint8_t font),  // Deprecated, use setTextDatum() and drawString()
/// @brief drawRightString operation.
           drawRightString(const char *string, int32_t x, int32_t y, uint8_t font),   // Deprecated, use setTextDatum() and drawString()
/// @brief drawCentreString operation.
           drawCentreString(const String& string, int32_t x, int32_t y, uint8_t font),// Deprecated, use setTextDatum() and drawString()
/// @brief drawRightString operation.
           drawRightString(const String& string, int32_t x, int32_t y, uint8_t font); // Deprecated, use setTextDatum() and drawString()


  // Text rendering and font handling support functions
/// @brief setCursor operation.
  void     setCursor(int16_t x, int16_t y),                 // Set cursor for tft.print()
/// @brief setCursor operation.
           setCursor(int16_t x, int16_t y, uint8_t font);   // Set cursor and font number for tft.print()

/// @brief getCursorX operation.
  int16_t  getCursorX(void),                                // Read current cursor x position (moves with tft.print())
/// @brief getCursorY operation.
           getCursorY(void);                                // Read current cursor y position

/// @brief setTextColor operation.
  void     setTextColor(uint16_t color),                    // Set character (glyph) color only (background not over-written)
/// @brief setTextColor operation.
           setTextColor(uint16_t fgcolor, uint16_t bgcolor, bool bgfill = false),  // Set character (glyph) foreground and background colour, optional background fill for smooth fonts
/// @brief setTextSize operation.
           setTextSize(uint8_t size);                       // Set character size multiplier (this increases pixel size)

/// @brief setTextWrap operation.
  void     setTextWrap(bool wrapX, bool wrapY = false);     // Turn on/off wrapping of text in TFT width and/or height

/// @brief setTextDatum operation.
  void     setTextDatum(uint8_t datum);                     // Set text datum position (default is top left), see Section 5 above
/// @brief getTextDatum operation.
  uint8_t  getTextDatum(void);

/// @brief setTextPadding operation.
  void     setTextPadding(uint16_t x_width);                // Set text padding (background blanking/over-write) width in pixels
/// @brief getTextPadding operation.
  uint16_t getTextPadding(void);                            // Get text padding

#ifdef LOAD_GFXFF
/// @brief setFreeFont operation.
  void     setFreeFont(const GFXfont *f = NULL),            // Select the GFX Free Font
/// @brief setTextFont operation.
           setTextFont(uint8_t font);                       // Set the font number to use in future
#else
  void     setFreeFont(uint8_t font),                       // Not used, historical fix to prevent an error
           setTextFont(uint8_t font);                       // Set the font number to use in future
#endif

/// @brief textWidth operation.
  int16_t  textWidth(const char *string, uint8_t font),     // Returns pixel width of string in specified font
/// @brief textWidth operation.
           textWidth(const char *string),                   // Returns pixel width of string in current font
/// @brief textWidth operation.
           textWidth(const String& string, uint8_t font),   // As above for String types
/// @brief textWidth operation.
           textWidth(const String& string),
/// @brief fontHeight operation.
           fontHeight(uint8_t font),                        // Returns pixel height of specified font
/// @brief fontHeight operation.
           fontHeight(void);                                // Returns pixel height of current font

           // Used by library and Smooth font class to extract Unicode point codes from a UTF8 encoded string
/// @brief decodeUTF8 operation.
  uint16_t decodeUTF8(uint8_t *buf, uint16_t *index, uint16_t remaining),
/// @brief decodeUTF8 operation.
           decodeUTF8(uint8_t c);

           // Support function to UTF8 decode and draw characters piped through print stream
/// @brief write operation.
  size_t   write(uint8_t);
           // size_t   write(const uint8_t *buf, size_t len);

           // Used by Smooth font class to fetch a pixel colour for the anti-aliasing
/// @brief setCallback operation.
  void     setCallback(getColorCallback getCol);

/// @brief fontsLoaded operation.
  uint16_t fontsLoaded(void); // Each bit in returned value represents a font type that is loaded - used for debug/error handling only


  // Low level read/write
/// @brief spiwrite operation.
  void     spiwrite(uint8_t);        // legacy support only
/// @brief writecommand operation.
  void     writecommand(uint8_t c);  // Send an 8-bit command, function resets DC/RS high ready for data
/// @brief writedata operation.
  void     writedata(uint8_t d);     // Send data with DC/RS set high

/// @brief commandList operation.
  void     commandList(const uint8_t *addr); // Send a initialisation sequence to TFT stored in FLASH

/// @brief readcommand8 operation.
  uint8_t  readcommand8( uint8_t cmd_function, uint8_t index = 0); // read 8 bits from TFT
/// @brief readcommand16 operation.
  uint16_t readcommand16(uint8_t cmd_function, uint8_t index = 0); // read 16 bits from TFT
/// @brief readcommand32 operation.
  uint32_t readcommand32(uint8_t cmd_function, uint8_t index = 0); // read 32 bits from TFT


  // Colour conversion
           // Convert 8-bit red, green and blue to 16 bits
/// @brief color565 operation.
  uint16_t color565(uint8_t red, uint8_t green, uint8_t blue);

           // Convert 8-bit colour to 16 bits
/// @brief color8to16 operation.
  uint16_t color8to16(uint8_t color332);
           // Convert 16-bit colour to 8 bits
/// @brief color16to8 operation.
  uint8_t  color16to8(uint16_t color565);

           // Convert 16-bit colour to/from 24-bit, R+G+B concatenated into LS 24 bits
/// @brief color16to24 operation.
  uint32_t color16to24(uint16_t color565);
/// @brief color24to16 operation.
  uint32_t color24to16(uint32_t color888);

           // Alpha blend 2 colours, see generic "alphaBlend_Test" example
           // alpha =   0 = 100% background colour
           // alpha = 255 = 100% foreground colour
/// @brief alphaBlend operation.
  uint16_t alphaBlend(uint8_t alpha, uint16_t fgc, uint16_t bgc);

           // 16-bit colour alphaBlend with alpha dither (dither reduces colour banding)
/// @brief alphaBlend operation.
  uint16_t alphaBlend(uint8_t alpha, uint16_t fgc, uint16_t bgc, uint8_t dither);
           // 24-bit colour alphaBlend with optional alpha dither
/// @brief alphaBlend24 operation.
  uint32_t alphaBlend24(uint8_t alpha, uint32_t fgc, uint32_t bgc, uint8_t dither = 0);


  // Bare metal functions
/// @brief startWrite operation.
  void     startWrite(void);                         // Begin SPI transaction
/// @brief writeColor operation.
  void     writeColor(uint16_t color, uint32_t len); // Deprecated, use pushBlock()
/// @brief endWrite operation.
  void     endWrite(void);                           // End SPI transaction

  // Set/get an arbitrary library configuration attribute or option
  //       Use to switch ON/OFF capabilities such as UTF8 decoding - each attribute has a unique ID
  //       id = 0: reserved - may be used in future to reset all attributes to a default state
  //       id = 1: Turn on (a=true) or off (a=false) GLCD cp437 font character error correction
  //       id = 2: Turn on (a=true) or off (a=false) UTF8 decoding

/// @brief CP437 SWITCH configuration constant.
           #define CP437_SWITCH 1
/// @brief UTF8 SWITCH configuration constant.
           #define UTF8_SWITCH  2
/// @brief PSRAM ENABLE configuration constant.
           #define PSRAM_ENABLE 3
/// @brief setAttribute operation.
  void     setAttribute(uint8_t id = 0, uint8_t a = 0); // Set attribute value
/// @brief getAttribute operation.
  uint8_t  getAttribute(uint8_t id = 0);                // Get attribute value

           // Used for diagnostic sketch to see library setup adopted by compiler, see Section 7 above
/// @brief getSetup operation.
  void     getSetup(setup_t& tft_settings); // Sketch provides the instance to populate
/// @brief verifySetupID operation.
  bool     verifySetupID(uint32_t id);

  // Global variables
/// @brief getSPIinstance operation.
  static   SPIClass& getSPIinstance(void); // Get SPI class handle
  uint32_t textcolor; ///< Text foreground colour.
  uint32_t textbgcolor; ///< Text background colour.

  uint32_t bitmap_fg; ///< Bitmap foreground colour (bit=1).
  uint32_t bitmap_bg; ///< Bitmap background colour (bit=0).

  uint8_t  textfont,  ///< Current selected font number
           textsize,  ///< Current font size multiplier
           textdatum, ///< Text reference datum
           rotation;  ///< Display rotation (0-3)

  uint8_t  decoderState = 0;   ///< UTF8 decoder state        - not for user access
  uint16_t decoderBuffer;      ///< Unicode code-point buffer - not for user access

 //--------------------------------------- private ------------------------------------//
 /// @cond INTERNAL
 private:
           // Legacy begin and end prototypes - deprecated TODO: delete
  void     spi_begin();
  void     spi_end();

  void     spi_begin_read();
  void     spi_end_read();

           // New begin and end prototypes
           // begin/end a TFT write transaction
           // For SPI bus the transmit clock rate is set
  inline void begin_tft_write() __attribute__((always_inline));
  inline void end_tft_write()   __attribute__((always_inline));

           // begin/end a TFT read transaction
           // For SPI bus: begin lowers SPI clock rate, end reinstates transmit clock rate
  inline void begin_tft_read()  __attribute__((always_inline));
  inline void end_tft_read()    __attribute__((always_inline));

           // Initialise the data bus GPIO and hardware interfaces
  void     initBus(void);

           // Temporary  library development function  TODO: remove need for this
  void     pushSwapBytePixels(const void* data_in, uint32_t len);

           // Same as setAddrWindow but exits with CGRAM in read mode
  void     readAddrWindow(int32_t xs, int32_t ys, int32_t w, int32_t h);

           // Byte read prototype
  uint8_t  readByte(void);

           // GPIO input/output direction control
  void     busDir(uint32_t mask, uint8_t mode);

           // Single GPIO input/output direction control
  void     gpioMode(uint8_t gpio, uint8_t mode);

           // Smooth graphics helper
  uint8_t  sqrt_fraction(uint32_t num);

           // Helper function: calculate distance of a point from a finite length line between two points
  float    wedgeLineDistance(float pax, float pay, float bax, float bay, float dr);

           // Display variant settings
  uint8_t  tabcolor,                   // Display tab colour (now invalid)
           colstart = 0, rowstart = 0; // Screen display area to CGRAM area coordinate offsets

           // Port and pin masks for control signals (ESP826 only) - TODO: remove need for this
  volatile uint32_t *dcport, *csport;
  uint32_t cspinmask, dcpinmask, wrpinmask, sclkpinmask;


  //uint32_t lastColor = 0xFFFF; // Last colour - used to minimise bit shifting overhead

  getColorCallback getColor = nullptr; // Smooth font callback function pointer

  bool     locked, inTransaction, lockTransaction; // SPI transaction and mutex lock flags

 //-------------------------------------- protected ----------------------------------//
 protected:

  //int32_t  win_xe, win_ye;          // Window end coords - not needed

  int32_t  _init_width, _init_height; ///< Display w/h as input, used by setRotation()
  int32_t  _width, _height;           ///< Display w/h as modified by current rotation
  int32_t  addr_row, addr_col;        ///< Window position - used to minimise window commands

  int16_t  _xPivot;   ///< TFT x pivot point coordinate for rotated Sprites
  int16_t  _yPivot;   ///< TFT x pivot point coordinate for rotated Sprites

  // Viewport variables
  int32_t  _vpX, _vpY, _vpW, _vpH;    ///< Note: x start, y start, x end + 1, y end + 1
  int32_t  _xDatum; ///<  xDatum value.
  int32_t  _yDatum; ///<  yDatum value.
  int32_t  _xWidth; ///<  xWidth value.
  int32_t  _yHeight; ///<  yHeight value.
  bool     _vpDatum; ///<  vpDatum value.
  bool     _vpOoB; ///<  vpOoB value.

  int32_t  cursor_x, cursor_y, padX;       ///< Text cursor x,y and padding setting
  int32_t  bg_cursor_x;                    ///< Background fill cursor
  int32_t  last_cursor_x;                  ///< Previous text cursor position when fill used

  uint32_t fontsloaded;               ///< Bit field of fonts loaded

  uint8_t  glyph_ab,   ///< Smooth font glyph delta Y (height) above baseline
           glyph_bb;   ///< Smooth font glyph delta Y (height) below baseline

  bool     isDigits;   ///< adjust bounding box for numbers to reduce visual jiggling
  bool     textwrapX, textwrapY;  ///< If set, 'wrap' text at right and optionally bottom edge of display
  bool     _swapBytes; ///< Swap the byte order for TFT pushImage()

  bool     _booted;    ///< init() or begin() has already run once

                       // User sketch manages these via set/getAttribute()
  bool     _cp437;        ///< If set, use correct CP437 charset (default is OFF)
  bool     _utf8;         ///< If set, use UTF-8 decoder in print stream 'write()' function (default ON)
  bool     _psram_enable; ///< Enable PSRAM use for library functions (TBD) and Sprites

  uint32_t _lastColor; ///< Buffered value of last colour used

  bool     _fillbg;    ///< Fill background flag (just for for smooth fonts at the moment)


#ifdef LOAD_GFXFF
  GFXfont  *gfxFont; ///< gfxFont value.
#endif

/***************************************************************************************
**                         Section 9: TFT_eSPI class conditional extensions
***************************************************************************************/

// Load the Anti-aliased font extension
/// @endcond

#ifdef SMOOTH_FONT
  // Smooth (anti-aliased) fonts

 public:

  // These are for the new anti-aliased fonts
/// @brief Loads a smooth font.
  void     loadFont(const uint8_t array[]);
#ifdef FONT_FS_AVAILABLE
/// @brief Loads a smooth font.
  void     loadFont(String fontName, fs::FS &ffs);
#endif
/// @brief Loads a smooth font.
  void     loadFont(String fontName, bool flash = true);
/// @brief Releases the loaded smooth font.
  void     unloadFont( void );
/// @brief Finds the index of a Unicode character.
  bool     getUnicodeIndex(uint16_t unicode, uint16_t *index);

/// @brief Draws a glyph from the loaded font.
  virtual void drawGlyph(uint16_t code);

/// @brief Displays a font character map.
  void     showFont(uint32_t td);

 // This is for the whole font
/// @brief TFT_eSPI::fontMetrics API.
  typedef struct
  {
    const uint8_t* gArray;           ///< array start pointer
    uint16_t gCount;                 ///< Total number of characters
    uint16_t yAdvance;               ///< Line advance
    uint16_t spaceWidth;             ///< Width of a space character
    int16_t  ascent;                 ///< Height of top of 'd' above baseline, other characters may be taller
    int16_t  descent;                ///< Offset to bottom of 'p', other characters may have a larger descent
    uint16_t maxAscent;              ///< Maximum ascent found in font
    uint16_t maxDescent;             ///< Maximum descent found in font
  } fontMetrics;

fontMetrics gFont = { nullptr, 0, 0, 0, 0, 0, 0, 0 }; ///< gFont value.

  // These are for the metrics for each individual glyph (so we don't need to seek this in file and waste time)
  uint16_t* gUnicode = NULL;  ///< UTF-16 code, the codes are searched so do not need to be sequential
  uint8_t*  gHeight = NULL;   ///< cheight
  uint8_t*  gWidth = NULL;    ///< cwidth
  uint8_t*  gxAdvance = NULL; ///< setWidth
  int16_t*  gdY = NULL;       ///< topExtent
  int8_t*   gdX = NULL;       ///< leftExtent
  uint32_t* gBitmap = NULL;   ///< file pointer to greyscale bitmap

  bool     fontLoaded = false; ///< Flags when a anti-aliased font is loaded

#ifdef FONT_FS_AVAILABLE
  fs::File fontFile; ///< fontFile value.
  fs::FS   &fontFS  = SPIFFS; ///< fontFS value.
  bool     spiffs   = true; ///< spiffs value.
  bool     fs_font = false;    ///< Use a smooth font file or FLASH (PROGMEM) array

#else
  bool     fontFile = true;
#endif

  private:

  void     loadMetrics(void);
  uint32_t readInt32(void);

  uint8_t* fontPtr = nullptr;
#endif

}; // End of class TFT_eSPI

// Swap any type
template <typename T> static inline void
transpose(T& a, T& b) { T t = a; a = b; b = t; }

// Fast alphaBlend
template <typename A, typename F, typename B> static inline uint16_t
fastBlend(A alpha, F fgc, B bgc)
{
  // Split out and blend 5-bit red and blue channels
  uint32_t rxb = bgc & 0xF81F;
  rxb += ((fgc & 0xF81F) - rxb) * (alpha >> 2) >> 6;
  // Split out and blend 6-bit green channel
  uint32_t xgx = bgc & 0x07E0;
  xgx += ((fgc & 0x07E0) - xgx) * alpha >> 8;
  // Recombine channels
  return (rxb & 0xF81F) | (xgx & 0x07E0);
}

/***************************************************************************************
**                         Section 10: Additional extension classes
***************************************************************************************/

// Load the Sprite Class
#include "Extensions/Sprite.h"

#endif // ends #ifndef _TFT_eSPIH_
