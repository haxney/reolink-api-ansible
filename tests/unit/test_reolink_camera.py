# -*- coding: utf-8 -*-
"""Unit tests for the reolink_camera module."""

import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Provide a minimal reolink_aio stub so tests run without the real library
# ---------------------------------------------------------------------------

def _make_reolink_stub():
    pkg = types.ModuleType("reolink_aio")
    api_mod = types.ModuleType("reolink_aio.api")
    exc_mod = types.ModuleType("reolink_aio.exceptions")

    class ReolinkError(Exception):
        pass

    class CredentialsInvalidError(ReolinkError):
        pass

    class LoginError(ReolinkError):
        pass

    class NotSupportedError(ReolinkError):
        pass

    class InvalidParameterError(ReolinkError):
        pass

    exc_mod.ReolinkError = ReolinkError
    exc_mod.CredentialsInvalidError = CredentialsInvalidError
    exc_mod.LoginError = LoginError
    exc_mod.NotSupportedError = NotSupportedError
    exc_mod.InvalidParameterError = InvalidParameterError

    class FakeHost:
        def __init__(self, host, username, password, **kwargs):
            self._host = host
            self._username = username
            self.is_nvr = False
            self.num_channel = 1
            self.mac_address = "AA:BB:CC:DD:EE:FF"
            self.firmware_version = "3.0.0.0"
            self.nvr_name = "TestCam"

        async def get_host_data(self):
            pass

        async def get_states(self):
            pass

        async def set_ntp(self, **kwargs):
            pass

        async def sync_ntp(self):
            pass

        async def set_time(self, **kwargs):
            pass

        async def set_encoding(self, channel, value, stream=None):
            pass

        async def set_bit_rate(self, channel, value, stream=None):
            pass

        async def set_frame_rate(self, channel, value, stream=None):
            pass

        async def set_image(self, channel, **kwargs):
            pass

        async def set_ir_lights(self, channel, enable):
            pass

        async def set_recording(self, channel, enable):
            pass

        async def set_audio(self, channel, enable):
            pass

        async def set_motion_detection(self, channel, enable):
            pass

        async def set_osd(self, channel, **kwargs):
            pass

        async def set_daynight(self, channel, value):
            pass

        async def set_backlight(self, channel, value):
            pass

        async def set_spotlight(self, channel, enable):
            pass

        async def set_push(self, channel, enable):
            pass

        async def set_email(self, channel, enable):
            pass

        async def set_ftp(self, channel, enable):
            pass

        async def logout(self):
            pass

        def camera_name(self, ch):
            return "TestCam"

        def camera_model(self, ch):
            return "RLC-810A"

        def ir_enabled(self, ch):
            return True

    api_mod.Host = FakeHost
    pkg.api = api_mod
    pkg.exceptions = exc_mod
    sys.modules["reolink_aio"] = pkg
    sys.modules["reolink_aio.api"] = api_mod
    sys.modules["reolink_aio.exceptions"] = exc_mod


_make_reolink_stub()


# ---------------------------------------------------------------------------
# Now import the modules under test
# ---------------------------------------------------------------------------

import importlib
import os

# Add the collection root to sys.path so relative imports work
_COLLECTION_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, _COLLECTION_ROOT)

from plugins.module_utils import reolink_utils  # noqa: E402
from plugins.modules import reolink_camera  # noqa: E402


class TestRunAsync(unittest.TestCase):
    def test_runs_coroutine(self):
        async def _coro():
            return 42

        result = reolink_utils.run_async(_coro())
        self.assertEqual(result, 42)


class TestApplyNtp(unittest.TestCase):
    def _make_host(self):
        from reolink_aio.api import Host
        return Host("192.168.1.1", "admin", "pass")

    def test_ntp_kwargs_forwarded(self):
        host = self._make_host()
        called_with = {}

        async def fake_set_ntp(**kwargs):
            called_with.update(kwargs)

        host.set_ntp = fake_set_ntp

        module = MagicMock()
        changes = []
        reolink_camera._apply_ntp(
            module,
            host,
            {"enabled": True, "server": "pool.ntp.org", "port": 123, "interval": 1440, "sync_now": False},
            check_mode=False,
            changes=changes,
        )
        self.assertIn("ntp", changes)
        self.assertEqual(called_with["enable"], True)
        self.assertEqual(called_with["server"], "pool.ntp.org")
        self.assertEqual(called_with["port"], 123)
        self.assertEqual(called_with["interval"], 1440)

    def test_ntp_check_mode_does_not_call_api(self):
        host = self._make_host()
        api_called = []

        async def fake_set_ntp(**kwargs):
            api_called.append(kwargs)

        host.set_ntp = fake_set_ntp

        module = MagicMock()
        changes = []
        reolink_camera._apply_ntp(
            module,
            host,
            {"server": "pool.ntp.org"},
            check_mode=True,
            changes=changes,
        )
        self.assertIn("ntp", changes)
        self.assertEqual(api_called, [])

    def test_ntp_none_skipped(self):
        host = self._make_host()
        module = MagicMock()
        changes = []
        reolink_camera._apply_ntp(module, host, None, check_mode=False, changes=changes)
        self.assertEqual(changes, [])


class TestApplyVideo(unittest.TestCase):
    def _make_host(self):
        from reolink_aio.api import Host
        return Host("192.168.1.1", "admin", "pass")

    def test_video_settings_recorded(self):
        host = self._make_host()
        encoding_calls = []
        bitrate_calls = []
        fps_calls = []

        async def fake_encoding(ch, val, stream=None):
            encoding_calls.append((ch, val, stream))

        async def fake_bitrate(ch, val, stream=None):
            bitrate_calls.append((ch, val, stream))

        async def fake_fps(ch, val, stream=None):
            fps_calls.append((ch, val, stream))

        host.set_encoding = fake_encoding
        host.set_bit_rate = fake_bitrate
        host.set_frame_rate = fake_fps

        module = MagicMock()
        changes = []
        reolink_camera._apply_video(
            module,
            host,
            channel=0,
            video_params={"stream": "main", "encoding": "h265", "bitrate": 2048, "frame_rate": 15},
            check_mode=False,
            changes=changes,
        )
        self.assertIn("video_encoding", changes)
        self.assertIn("video_bitrate", changes)
        self.assertIn("video_frame_rate", changes)
        self.assertEqual(encoding_calls[0], (0, "h265", "main"))
        self.assertEqual(bitrate_calls[0], (0, 2048, "main"))
        self.assertEqual(fps_calls[0], (0, 15, "main"))


class TestApplyImage(unittest.TestCase):
    def _make_host(self):
        from reolink_aio.api import Host
        return Host("192.168.1.1", "admin", "pass")

    def test_image_kwargs_forwarded(self):
        host = self._make_host()
        image_calls = []

        async def fake_set_image(ch, **kwargs):
            image_calls.append((ch, kwargs))

        host.set_image = fake_set_image

        module = MagicMock()
        changes = []
        reolink_camera._apply_image(
            module,
            host,
            channel=0,
            image_params={"brightness": 200, "contrast": 100},
            check_mode=False,
            changes=changes,
        )
        self.assertIn("image", changes)
        self.assertEqual(image_calls[0][1]["bright"], 200)
        self.assertEqual(image_calls[0][1]["contrast"], 100)
        self.assertNotIn("saturation", image_calls[0][1])


if __name__ == "__main__":
    unittest.main()
