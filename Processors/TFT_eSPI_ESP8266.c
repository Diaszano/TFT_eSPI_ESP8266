
        //////////////////////////////////////////////////////
        // TFT_eSPI driver functions for ESP8266 processors //
        //////////////////////////////////////////////////////

// Select the SPI port to use
// ESP8266 default (FLASH port also available via overlap mode)
  SPIClass& spi = SPI;

// Buffer for SPI transmit byte padding and byte order manipulation
uint8_t   spiBuffer[8] = {0,0,0,0,0,0,0,0};

////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////


/***************************************************************************************
** Function name:           read byte  - supports class functions
** Description:             Parallel bus only - dummy function - not used
***************************************************************************************/
uint8_t TFT_eSPI::readByte(void)
{
  uint8_t b = 0xAA;
  return b;
}

////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////

/***************************************************************************************
** Function name:           pushBlock - for ESP8266
** Description:             Write a block of pixels of the same colour
***************************************************************************************/
//Clear screen test 76.8ms theoretical. 81.5ms TFT_eSPI, 967ms Adafruit_ILI9341
//Performance 26.15Mbps@26.66MHz, 39.04Mbps@40MHz, 75.4Mbps@80MHz SPI clock
//Efficiency:
//       TFT_eSPI       98.06%              97.59%          94.24%
//       Adafruit_GFX   19.62%              14.31%           7.94%
//
void TFT_eSPI::pushBlock(uint16_t color, uint32_t len)
{
/*
while (len>1) { tft_Write_32(color<<16 | color); len-=2;}
if (len) tft_Write_16(color);
return;
//*/
  uint16_t color16 = (color >> 8) | (color << 8);
  uint32_t color32 = color16 | color16 << 16;
/*
  while(len--) {
    SPI1U1 = ((16-1) << SPILMOSI) | ((16-1) << SPILMISO);
    SPI1W0 = color16;
    SPI1CMD |= SPIBUSY;
    while(SPI1CMD & SPIBUSY) {}
  }
  return;
//*/

  SPI1W0 = color32;
  SPI1W1 = color32;
  SPI1W2 = color32;
  SPI1W3 = color32;
  if (len > 8)
  {
    SPI1W4 = color32;
    SPI1W5 = color32;
    SPI1W6 = color32;
    SPI1W7 = color32;
  }
  if (len > 16)
  {
    SPI1W8 = color32;
    SPI1W9 = color32;
    SPI1W10 = color32;
    SPI1W11 = color32;
  }
  if (len > 24)
  {
    SPI1W12 = color32;
    SPI1W13 = color32;
    SPI1W14 = color32;
    SPI1W15 = color32;
  }
  if (len > 31)
  {
    SPI1U1 = (511 << SPILMOSI);
    while(len>31)
    {
#if (defined (SPI_FREQUENCY) && (SPI_FREQUENCY == 80000000))
      if(SPI1CMD & SPIBUSY) // added to sync with flag change
#endif
      while(SPI1CMD & SPIBUSY) {}
      SPI1CMD |= SPIBUSY;
      len -= 32;
    }
    while(SPI1CMD & SPIBUSY) {}
  }

  if (len)
  {
    len = (len << 4) - 1;
    SPI1U1 = (len << SPILMOSI);
    SPI1CMD |= SPIBUSY;
    while(SPI1CMD & SPIBUSY) {}
  }

}

/***************************************************************************************
** Function name:           pushPixels - for ESP8266
** Description:             Write a sequence of pixels
***************************************************************************************/
void TFT_eSPI::pushPixels(const void* data_in, uint32_t len){

  if(_swapBytes) {
    pushSwapBytePixels(data_in, len);
    return;
  }

  uint16_t *data = (uint16_t*) data_in;

  uint32_t color[8];

  SPI1U1 = (255 << SPILMOSI) | (255 << SPILMISO);


  while(len>15)
  {
    memcpy(color,data,32);
    data+=16;

    len -= 16;

    // ESP8266 wait time here at 40MHz SPI is ~5.45us
    while(SPI1CMD & SPIBUSY) {}
    SPI1W0 = color[0];
    SPI1W1 = color[1];
    SPI1W2 = color[2];
    SPI1W3 = color[3];
    SPI1W4 = color[4];
    SPI1W5 = color[5];
    SPI1W6 = color[6];
    SPI1W7 = color[7];
    SPI1CMD |= SPIBUSY;
  }

  if(len)
  {
    uint32_t bits = (len*16-1); // bits left to shift - 1

    memcpy(color,data,len<<1);

    while(SPI1CMD & SPIBUSY) {}
    SPI1U1 = (bits << SPILMOSI) | (bits << SPILMISO);
    SPI1W0 = color[0];
    SPI1W1 = color[1];
    SPI1W2 = color[2];
    SPI1W3 = color[3];
    SPI1W4 = color[4];
    SPI1W5 = color[5];
    SPI1W6 = color[6];
    SPI1W7 = color[7];
    SPI1CMD |= SPIBUSY;
  }

  while(SPI1CMD & SPIBUSY) {}

}

/***************************************************************************************
** Function name:           pushSwapBytePixels - for ESP8266
** Description:             Write a sequence of pixels with swapped bytes
***************************************************************************************/
void TFT_eSPI::pushSwapBytePixels(const void* data_in, uint32_t len){

  uint8_t* data = (uint8_t*)data_in;
  //uint16_t* data = (uint16_t*)data_in;

  uint32_t color[8];

  SPI1U1 = (255 << SPILMOSI) | (255 << SPILMISO);

  while(len>15)
  {
    uint32_t i = 0;
    while(i<8) { color[i++] = DAT8TO32(data); data+=4; }

    len -= 16;

    // ESP8266 wait time here at 40MHz SPI is ~5.45us
    while(SPI1CMD & SPIBUSY) {}
    SPI1W0 = color[0];
    SPI1W1 = color[1];
    SPI1W2 = color[2];
    SPI1W3 = color[3];
    SPI1W4 = color[4];
    SPI1W5 = color[5];
    SPI1W6 = color[6];
    SPI1W7 = color[7];
    SPI1CMD |= SPIBUSY;
  }

  if(len)
  {
    uint32_t i = 0;
    uint32_t bits = (len*16-1); // bits left to shift - 1
    len = (len+1)>>1;
    while(len--) { color[i++] = DAT8TO32(data); data+=4; }

    while(SPI1CMD & SPIBUSY) {}
    SPI1U1 = (bits << SPILMOSI) | (bits << SPILMISO);
    SPI1W0 = color[0];
    SPI1W1 = color[1];
    SPI1W2 = color[2];
    SPI1W3 = color[3];
    SPI1W4 = color[4];
    SPI1W5 = color[5];
    SPI1W6 = color[6];
    SPI1W7 = color[7];
    SPI1CMD |= SPIBUSY;
  }

  while(SPI1CMD & SPIBUSY) {}

}

////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////
