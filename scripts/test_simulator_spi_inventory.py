import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SpiInventoryTests(unittest.TestCase):
    def test_audit_covers_direct_registers_and_fast_paths(self):
        audit = (ROOT / 'simulator/native/SPI_AUDIT.md').read_text(encoding='utf-8')
        for token in ('SPI1W0', 'SPI1CMD', 'tft_Write_32C', 'pushBlock',
                      'pushPixels', 'pushSwapBytePixels', 'DC_C', 'setWindow'):
            self.assertIn(token, audit)
        self.assertNotIn('untested-path', audit)

    def test_every_production_direct_spi_register_is_classified(self):
        audit = (ROOT / 'simulator/native/SPI_AUDIT.md').read_text(encoding='utf-8')
        source = '\n'.join(path.read_text(encoding='utf-8')
                            for path in (ROOT / 'src').rglob('*')
                            if path.suffix in ('.h', '.cpp', '.inc'))
        registers = sorted(set(re.findall(r'\bSPI1(?:W\d+|CMD|U\d?)\b', source)))
        for register in registers:
            with self.subTest(register=register):
                self.assertRegex(audit, r'\|\s*`?' + re.escape(register) + r'`?\s*\|')


if __name__ == '__main__':
    unittest.main()
