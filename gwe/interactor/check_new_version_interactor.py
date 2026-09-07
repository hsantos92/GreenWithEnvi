# This file is part of gwe.
#
# Copyright (c) 2020 Roberto Leinardi
#
# gst is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gst is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gst.  If not, see <http://www.gnu.org/licenses/>.
import re
import logging
from distutils.version import LooseVersion
from typing import Optional

import requests
import rx
from injector import singleton, inject
from rx import Observable

from gwe.conf import APP_VERSION

_LOG = logging.getLogger(__name__)


@singleton
class CheckNewVersionInteractor:
    RELEASE_URL = 'https://api.github.com/repos/hsantos92/GreenWithEnvi/releases/latest'

    @inject
    def __init__(self) -> None:
        pass

    def execute(self) -> Observable:
        _LOG.debug("CheckNewVersionInteractor.execute()")
        return rx.defer(lambda _: rx.just(self._check_new_version()))

    def _check_new_version(self) -> Optional[LooseVersion]:
        try:
            req = requests.get(self.RELEASE_URL, timeout=10)
            if req.status_code == 404:  # No published release yet.
                return None
            req.raise_for_status()
            tag = req.json().get('tag_name', '')
            if not isinstance(tag, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
                return None
            version = LooseVersion(tag.removeprefix('v'))
            return version if version > LooseVersion(APP_VERSION) else None
        except (requests.RequestException, ValueError, AttributeError):
            _LOG.warning("Unable to check GreenWithEnvi releases", exc_info=True)
            return None
