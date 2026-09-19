import unittest
from unittest.mock import patch, MagicMock
from gwe.repository.nvml_worker import NvmlWorker


class ControlHelperTests(unittest.TestCase):
    def test_installed_helper_is_used_without_development_python(self):
        with patch('gwe.repository.nvml_worker.is_flatpak', return_value=False), \
             patch('gwe.repository.nvml_worker.Path.is_file', return_value=True), \
             patch('gwe.repository.nvml_worker.os.geteuid', return_value=1000), \
             patch('gwe.repository.nvml_worker.subprocess.Popen') as popen, \
             patch.object(NvmlWorker, 'request'):
            NvmlWorker('GPU-test')
        self.assertEqual(popen.call_args.args[0],
                         ['pkexec', '/usr/local/libexec/greenwithenvi-control', 'GPU-test'])

    def test_uninstalled_helper_keeps_authenticated_fallback(self):
        with patch('gwe.repository.nvml_worker.is_flatpak', return_value=False), \
             patch('gwe.repository.nvml_worker.Path.is_file', return_value=False), \
             patch('gwe.repository.nvml_worker.os.geteuid', return_value=1000), \
             patch('gwe.repository.nvml_worker.subprocess.Popen') as popen, \
             patch.object(NvmlWorker, 'request'):
            NvmlWorker('GPU-test')
        command = popen.call_args.args[0]
        self.assertEqual(command[0], 'pkexec')
        self.assertIn('-I', command)
        self.assertTrue(command[-2].endswith('/nvml_control.py'))
