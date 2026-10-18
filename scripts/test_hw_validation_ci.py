import unittest
from pathlib import Path


class OfflineWorkflowTests(unittest.TestCase):
    def test_offline_workflow_has_no_hardware_or_upload_commands(self):
        workflow = Path('.github/workflows/hardware-validation-offline.yml').read_text()
        for command in ('make test-python', 'make test-native', 'make test-host',
                        'make test-compile', 'make test-hw-build', 'make test-host-extremes'):
            self.assertIn(command, workflow)
        for forbidden in ('pio run -t upload', 'esptool', 'device monitor', 'uploadfs'):
            self.assertNotIn(forbidden, workflow)

    def test_existing_scroll_fuzz_campaign_is_preserved(self):
        fuzz = Path('.github/workflows/fuzz.yml').read_text()
        self.assertIn('--case scroll --fuzz', fuzz)
        self.assertIn('--case extreme-coordinates --fuzz', fuzz)


if __name__ == '__main__':
    unittest.main()
