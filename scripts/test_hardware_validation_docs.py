from pathlib import Path
import unittest


class HardwareValidationDocsTests(unittest.TestCase):
    def test_operator_guide_has_manual_gates_and_traceability(self):
        readme = Path('extras/hardware/Audit_Validation/README.md').read_text()
        guide = Path('extras/hardware/Audit_Validation/TESTES.md').read_text()
        self.assertIn('test_demo.mp4', readme)
        self.assertIn('ilustração', readme)
        for token in ('VISUAL_REVIEW_REQUIRED', 'E30', '5 boots', 'sem DTR/RTS', 'X',
                      'validation-guide.mp4', 'sim-visual-video'):
            self.assertIn(token, guide)
        for token in ('test-hw-preflight', 'H1', 'SHA-256', 'upload não autorizado', 'NOT_EXECUTED',
                      'R0', 'ROTATION,n', 'Matriz física do Plano 12', 'RGB565 exata'):
            self.assertIn(token, guide + readme)
        for number in range(1, 15):
            self.assertIn('AC-{:02d}'.format(number), guide)


if __name__ == '__main__':
    unittest.main()
