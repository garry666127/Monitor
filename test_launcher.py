"""Exercise cmd.exe parsing, including the actual drag-and-drop argument path."""
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent


@unittest.skipUnless(os.name == 'nt', 'Windows batch launcher')
class LauncherTests(unittest.TestCase):
    def invoke(self, argument=''):
        command = f'cmd.exe /d /s /c ""{HERE / "run_yolo.bat"}"{argument}"'
        return subprocess.run(command, input=b'\r\n', capture_output=True, timeout=45)

    def test_dragged_missing_file_is_reported_without_parser_errors(self):
        result = self.invoke(' "C:\\missing folder\\不存在 (test) & sample!.mp4"')
        output = result.stdout + result.stderr
        self.assertIn(b'Video file not found.', output)
        self.assertNotIn(b'is not recognized', output)
        self.assertEqual(result.returncode, 1)

    def test_double_click_displays_instructions_and_waits(self):
        result = self.invoke()
        output = result.stdout + result.stderr
        self.assertIn(b'Drag a video file onto run_yolo.bat', output)
        self.assertIn(b'Press any key', output)
        self.assertNotIn(b'is not recognized', output)
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
