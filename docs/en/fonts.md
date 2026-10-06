English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/fonts.md)

# Fonts

## Built-in fonts

Enable a font with its `LOAD_*` macro in `User_Setup.h`. The GLCD font is enabled by default; the others are optional. Built-in fonts 4, 6, 7 and 8 are run-length encoded in flash. The current setup includes all built-in fonts and GFX FreeFonts.

| Font | Setup macro | Notes |
| --- | --- | --- |
| GLCD | `LOAD_GLCD` | 6×8; about 1,820 bytes of flash. |
| Font 2 | `LOAD_FONT2` | 16 pixels high; about 3,534 bytes. |
| Font 4 | `LOAD_FONT4` | 26 pixels high; about 5,848 bytes, RLE encoded. |
| Font 6 | `LOAD_FONT6` | 48 pixels high; about 2,666 bytes, RLE encoded. |
| Font 7 | `LOAD_FONT7` | 48-pixel 7-segment font; about 2,438 bytes, RLE encoded. |
| Font 8 | `LOAD_FONT8` | 75-pixel font; about 3,256 bytes, RLE encoded. |

These are approximate values from the upstream `User_Setup.h` font comments; final size depends on the compiler and selected build. Disable unused `LOAD_*` macros to reduce program flash use.

## FreeFonts

Set `LOAD_GFXFF` to include the Adafruit GFX FreeFonts. Select a font with `setFreeFont()`, for example `tft.setFreeFont(FF18)`. The `FF*` names are aliases provided by the `Free_Font_Demo` example; that example's `Free_Fonts.h` maps them to the actual font objects. Pass `nullptr` to restore the built-in font.

## Smooth fonts

Smooth fonts use `.vlw` files and require `SMOOTH_FONT`. The `Font_Demo_1` example reads files from LittleFS. Upload its data folder, then load and release the font:

```sh
make uploadfs EX=Font_Demo_1
```

```cpp
tft.loadFont("NotoSansBold15", LittleFS);
tft.drawString("Smooth text", 10, 20);
tft.unloadFont();
```

`Font_Demo_1_Array` demonstrates embedding font data in a flash array instead of a filesystem. Creating `.vlw` files is supported by the Processing sketch in `Tools/Create_Smooth_Font/Create_font`. `Tools/bmp2array4bit` converts indexed BMP images into palette and pixel arrays for 4-bit sprites; it does not convert fonts.
