# bmp2array4bit

This tool converts indexed BMP images into palette and pixel arrays for four-bit sprites. See the paired [English asset instructions](../../docs/en/fonts.md#convert-bmp-images-for-four-bit-sprites) and [Português (Brasil) instructions](../../docs/pt-BR/fonts.md#converter-bmp-para-sprites-de-4-bits) for image preparation and font-generation guidance.

Run `python bmp2array4bit.py image.bmp -o image.c`.

The converter accepts positive-size, bottom-up, uncompressed 4-bit indexed BMP files with at most 16 palette entries. Row padding is removed, odd-width rows retain their final packed byte, and malformed inputs leave an existing output file untouched.

The converter is loosely based on [SparkFun BMPtoArray](https://github.com/sparkfun/BMPtoArray/blob/master/bmp2array.py).
