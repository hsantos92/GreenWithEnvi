"""Release checks must use this fork and tolerate missing or invalid releases."""
import unittest
from unittest.mock import Mock, patch

import requests

from gwe.interactor.check_new_version_interactor import CheckNewVersionInteractor


class ReleaseCheckTests(unittest.TestCase):
    def check(self, tag=None, status=200, error=None):
        response = Mock(status_code=status)
        response.json.return_value = {'tag_name': tag}
        with patch('gwe.interactor.check_new_version_interactor.requests.get',
                   return_value=response, side_effect=error) as get:
            result = CheckNewVersionInteractor()._check_new_version()
        get.assert_called_once_with(
            'https://api.github.com/repos/hsantos92/GreenWithEnvi/releases/latest', timeout=10)
        return result

    def test_new_release_with_optional_v_prefix(self):
        for tag in ('0.21.0', 'v0.21.0'):
            self.assertEqual(str(self.check(tag)), '0.21.0')

    def test_no_published_release(self):
        self.assertIsNone(self.check(status=404))

    def test_old_or_current_release(self):
        for tag in ('0.15.5', '0.20.0'):
            self.assertIsNone(self.check(tag))

    def test_invalid_or_prerelease_tag(self):
        for tag in (None, 123, 'nightly', 'v0.16.0-rc1'):
            self.assertIsNone(self.check(tag))

    def test_connection_failure(self):
        self.assertIsNone(self.check(error=requests.Timeout()))
