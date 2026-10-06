        //////////////////////////////////////////////////////
        // TFT_eSPI driver functions for ESP8266 processors //
        //////////////////////////////////////////////////////

#ifndef _TFT_eSPI_ESP8266H_
#define _TFT_eSPI_ESP8266H_

// Processor ID reported by getSetup()
#define PROCESSOR_ID 0x8266

// Include processor specific header
// None

// Processor specific code used by SPI bus transaction startWrite and endWrite functions
#define SET_BUS_WRITE_MODE SPI1U=SPI1U_WRITE
#define SET_BUS_READ_MODE  SPI1U=SPI1U_READ

// Code to check if DMA is busy, used by SPI bus transaction transaction and endWrite functions
#define DMA_BUSY_CHECK // DMA not available, leave blank

// Initialise processor specific SPI functions, used by init()
#if (!defined (SUPPORT_TRANSACTIONS) && defined (ARDUINO_ARCH_ESP8266))
  #define INIT_TFT_DATA_BUS \
    spi.setBitOrder(MSBFIRST); \
    spi.setDataMode(TFT_SPI_MODE); \
    spi.setFrequency(SPI_FREQUENCY);
  #else
    #define INIT_TFT_DATA_BUS
#endif

// If smooth fonts are enabled the filing system may need to be loaded
#ifdef SMOOTH_FONT
  // Call up the SPIFFS FLASH filing system for the anti-aliased fonts
  #define FS_NO_GLOBALS
  #include <FS.h>
  #define FONT_FS_AVAILABLE
#endif

// Do not allow parallel mode for ESP8266

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
    #define DC_C GPOC=dcpinmask
    #define DC_D GPOS=dcpinmask
  #endif
#endif

////////////////////////////////////////////////////////////////////////////////////////
// Define the CS (TFT chip select) pin drive code
////////////////////////////////////////////////////////////////////////////////////////
#ifndef TFT_CS
  #define CS_L // No macro allocated so it generates no code
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
  #define T_CS_L // No macro allocated so it generates no code
  #define T_CS_H // No macro allocated so it generates no code

////////////////////////////////////////////////////////////////////////////////////////
// Make sure TFT_MISO is defined if not used to avoid an error message
////////////////////////////////////////////////////////////////////////////////////////
#ifndef TFT_MISO
  #define TFT_MISO -1
#endif

////////////////////////////////////////////////////////////////////////////////////////
// ESP8266 specific SPI macros
////////////////////////////////////////////////////////////////////////////////////////
#if defined (TFT_SPI_OVERLAP)
  #undef TFT_CS
  #define SPI1U_WRITE (SPIUMOSI | SPIUSSE | SPIUCSSETUP | SPIUCSHOLD)
  #define SPI1U_READ  (SPIUMOSI | SPIUSSE | SPIUCSSETUP | SPIUCSHOLD | SPIUDUPLEX)
#else
  #define SPI1U_WRITE (SPIUMOSI | SPIUSSE)
  #define SPI1U_READ  (SPIUMOSI | SPIUSSE | SPIUDUPLEX)
#endif

////////////////////////////////////////////////////////////////////////////////////////
// Macros to write commands/pixel colour data to a SPI ILI948x TFT
////////////////////////////////////////////////////////////////////////////////////////
  // Command is 8 bits
  #define CMD_BITS 8

  #define tft_Write_8(C) \
  SPI1U1 = ((CMD_BITS-1) << SPILMOSI) | ((CMD_BITS-1) << SPILMISO); \
  SPI1W0 = (C)<<(CMD_BITS - 8); \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

  #define tft_Write_16(C) \
  SPI1U1 = (15 << SPILMOSI) | (15 << SPILMISO); \
  SPI1W0 = ((C)<<8 | (C)>>8); \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

  #define tft_Write_16N(C) \
  SPI1U1 = (15 << SPILMOSI) | (15 << SPILMISO); \
  SPI1W0 = ((C)<<8 | (C)>>8); \
  SPI1CMD |= SPIBUSY

  #define tft_Write_16S(C) \
  SPI1U1 = (15 << SPILMOSI) | (15 << SPILMISO); \
  SPI1W0 = C; \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

  #define tft_Write_32(C) \
  SPI1U1 = (31 << SPILMOSI) | (31 << SPILMISO); \
  SPI1W0 = C; \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

  #define tft_Write_32C(C,D) \
  SPI1U1 = (31 << SPILMOSI) | (31 << SPILMISO); \
  SPI1W0 = ((D)>>8 | (D)<<8)<<16 | ((C)>>8 | (C)<<8); \
  SPI1CMD |= SPIBUSY; \
  while(SPI1CMD & SPIBUSY) {;}

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
  #define tft_Read_8() spi.transfer(0)

// Concatenate a byte sequence A,B,C,D to CDAB, P is a uint8_t pointer
#define DAT8TO32(P) ( (uint32_t)P[0]<<8 | P[1] | P[2]<<24 | P[3]<<16 )

#endif // Header end
