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
from plugins.modules import reolink_facts  # noqa: E402


class TestRunAsync(unittest.TestCase):
    def test_runs_coroutine(self):
        async def _coro():
            return 42

        result = reolink_utils.run_async(_coro())
        self.assertEqual(result, 42)


class TestConnect(unittest.TestCase):
    def test_host_constructed_inside_running_loop(self):
        # reolink-aio's Host creates asyncio primitives in __init__, which
        # fails with "no running event loop" (Python 3.14) if connect()
        # builds it from synchronous code instead of inside a coroutine.
        from reolink_aio.api import Host as FakeHost
        import asyncio

        class LoopCheckingHost(FakeHost):
            def __init__(self, *args, **kwargs):
                asyncio.get_running_loop()  # raises RuntimeError if none
                super().__init__(*args, **kwargs)

        module = MagicMock()
        module.params = {
            "hostname": "192.168.1.1",
            "username": "admin",
            "password": "pass",
            "port": None,
            "use_https": True,
        }
        module.fail_json.side_effect = AssertionError

        with patch.object(reolink_utils, "Host", LoopCheckingHost):
            host = reolink_utils.connect(module)

        self.assertIsInstance(host, LoopCheckingHost)
        module.fail_json.assert_not_called()


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


class _FailJson(Exception):
    """Stands in for AnsibleModule.fail_json, which never returns."""


def _failing_module():
    module = MagicMock()
    module.fail_json.side_effect = _FailJson
    return module


class TestApplyFlipMirror(unittest.TestCase):
    # Real cameras (RLC-810A, RLC-822A, P330) name these rotation and
    # mirroring in GetIsp; 0.2.0 looked for flip and mirror and so never
    # found them.
    def _make_host(self, isp):
        host = MagicMock()
        host._isp_settings = {0: isp}
        host.get_state = AsyncMock()
        host.send_setting = AsyncMock()
        return host

    def test_flip_and_mirror_sent_when_changed(self):
        host = self._make_host({"channel": 0, "rotation": 0, "mirroring": 0})
        module = MagicMock()
        changes = []
        reolink_camera._apply_flip_mirror(
            module, host, channel=0, flip=True, mirror=True,
            check_mode=False, changes=changes,
        )
        self.assertIn("flip_mirror", changes)
        host.send_setting.assert_awaited_once()
        body = host.send_setting.await_args.args[0]
        self.assertEqual(body[0]["cmd"], "SetIsp")
        self.assertEqual(body[0]["param"]["Isp"]["rotation"], 1)
        self.assertEqual(body[0]["param"]["Isp"]["mirroring"], 1)

    def test_only_mirror_changed_when_flip_already_set(self):
        host = self._make_host({"channel": 0, "rotation": 1, "mirroring": 0})
        module = MagicMock()
        changes = []
        reolink_camera._apply_flip_mirror(
            module, host, channel=0, flip=True, mirror=True,
            check_mode=False, changes=changes,
        )
        body = host.send_setting.await_args.args[0]
        self.assertEqual(body[0]["param"]["Isp"]["rotation"], 1)
        self.assertEqual(body[0]["param"]["Isp"]["mirroring"], 1)

    def test_idempotent_when_already_matching(self):
        host = self._make_host({"channel": 0, "rotation": 1, "mirroring": 0})
        module = MagicMock()
        changes = []
        reolink_camera._apply_flip_mirror(
            module, host, channel=0, flip=True, mirror=False,
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, [])
        host.send_setting.assert_not_awaited()

    def test_check_mode_does_not_send(self):
        host = self._make_host({"channel": 0, "rotation": 0, "mirroring": 0})
        module = MagicMock()
        changes = []
        reolink_camera._apply_flip_mirror(
            module, host, channel=0, flip=True, mirror=None,
            check_mode=True, changes=changes,
        )
        self.assertIn("flip_mirror", changes)
        host.send_setting.assert_not_awaited()

    def test_unsupported_key_fails(self):
        host = self._make_host({"channel": 0, "rotation": 0})  # no "mirroring"
        module = _failing_module()
        changes = []
        with self.assertRaises(_FailJson):
            reolink_camera._apply_flip_mirror(
                module, host, channel=0, flip=None, mirror=True,
                check_mode=False, changes=changes,
            )
        self.assertIn("mirroring", module.fail_json.call_args.kwargs["msg"])
        self.assertEqual(changes, [])
        host.send_setting.assert_not_awaited()

    def test_none_skipped(self):
        host = self._make_host({"channel": 0, "rotation": 0, "mirroring": 0})
        module = MagicMock()
        changes = []
        reolink_camera._apply_flip_mirror(
            module, host, channel=0, flip=None, mirror=None,
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, [])
        host.get_state.assert_not_awaited()


# The US rule: 2nd Sunday of March to 1st Sunday of November, at 02:00.
_US_DST = {
    "enabled": True,
    "offset": 1,
    "start": {"month": 3, "week": 2, "weekday": 0, "hour": 2, "minute": 0, "second": 0},
    "end": {"month": 11, "week": 1, "weekday": 0, "hour": 2, "minute": 0, "second": 0},
}


def _get_time_response(time_zone=14400, dst_enable=0):
    """A GetTime body as an RLC-810A returns it (firmware v3.1.0.4569)."""
    return {
        "Dst": {
            "enable": dst_enable, "offset": 1,
            "startMon": 3, "startWeek": 2, "startWeekday": 0,
            "startHour": 2, "startMin": 0, "startSec": 0,
            "endMon": 10, "endWeek": 5, "endWeekday": 0,
            "endHour": 2, "endMin": 0, "endSec": 0,
        },
        "Time": {
            "year": 2026, "mon": 10, "day": 18, "hour": 13, "min": 34, "sec": 19,
            "hourFmt": 1, "isDst": 0, "timeFmt": "DD/MM/YYYY", "timeZone": time_zone,
        },
    }


class TestApplyTime(unittest.TestCase):
    def _make_host(self, settings):
        host = MagicMock()
        host._time_settings = settings
        host.get_state = AsyncMock()
        host.send_setting = AsyncMock()
        return host

    def test_zone_and_dst_sent_in_one_set_time(self):
        host = self._make_host(_get_time_response())
        module = MagicMock()
        changes = []
        reolink_camera._apply_time(
            module, host, {"timezone_offset": 18000, "dst": _US_DST},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, ["time"])
        host.send_setting.assert_awaited_once()
        body = host.send_setting.await_args.args[0]
        self.assertEqual(body[0]["cmd"], "SetTime")
        param = body[0]["param"]
        self.assertEqual(param["Time"]["timeZone"], 18000)
        self.assertEqual(param["Dst"]["enable"], 1)
        self.assertEqual(param["Dst"]["endMon"], 11)
        self.assertEqual(param["Dst"]["endWeek"], 1)
        # Fields not asked about go back as the camera sent them.
        self.assertEqual(param["Time"]["timeFmt"], "DD/MM/YYYY")
        self.assertEqual(param["Dst"]["startMon"], 3)

    def test_idempotent_when_already_matching(self):
        settings = _get_time_response(time_zone=18000, dst_enable=1)
        settings["Dst"].update(endMon=11, endWeek=1)
        host = self._make_host(settings)
        module = MagicMock()
        changes = []
        reolink_camera._apply_time(
            module, host, {"timezone_offset": 18000, "hours_24": False, "dst": _US_DST},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, [])
        host.send_setting.assert_not_awaited()

    def test_hours_24_maps_to_hour_format(self):
        host = self._make_host(_get_time_response())
        module = MagicMock()
        reolink_camera._apply_time(
            module, host, {"hours_24": True}, check_mode=False, changes=[],
        )
        body = host.send_setting.await_args.args[0]
        self.assertEqual(body[0]["param"]["Time"]["hourFmt"], 0)

    def test_check_mode_does_not_send(self):
        host = self._make_host(_get_time_response())
        module = MagicMock()
        changes = []
        reolink_camera._apply_time(
            module, host, {"dst": {"enabled": True}}, check_mode=True, changes=changes,
        )
        self.assertEqual(changes, ["time"])
        host.send_setting.assert_not_awaited()

    def test_out_of_range_dst_field_fails_before_contacting_camera(self):
        host = self._make_host(_get_time_response())
        module = _failing_module()
        with self.assertRaises(_FailJson):
            reolink_camera._apply_time(
                module, host, {"dst": {"start": {"weekday": 7}}},
                check_mode=False, changes=[],
            )
        self.assertIn("dst.start.weekday", module.fail_json.call_args.kwargs["msg"])
        host.get_state.assert_not_awaited()

    def test_none_skipped(self):
        host = self._make_host(_get_time_response())
        module = MagicMock()
        changes = []
        reolink_camera._apply_time(module, host, None, check_mode=False, changes=changes)
        self.assertEqual(changes, [])
        host.get_state.assert_not_awaited()


class TestApplyHostSwitch(unittest.TestCase):
    """auto_upgrade, upnp and ddns: raw Get/Set of one enable flag."""

    def _make_host(self, blocks):
        # blocks: {"AutoUpgrade": {"enable": 1}, ...}, mutated by Set like a camera.
        host = MagicMock()
        host.sent = []
        host.ignore_set = False

        async def send(body, expected_response_type=None):
            block = body[0]["cmd"][len("Get"):]
            return [{"cmd": body[0]["cmd"], "code": 0, "value": {block: dict(blocks[block])}}]

        async def send_setting(body):
            host.sent.append(body)
            block = body[0]["cmd"][len("Set"):]
            if not host.ignore_set:
                blocks[block] = dict(body[0]["param"][block])

        host.send = send
        host.send_setting = send_setting
        return host

    def test_disables_and_reads_back(self):
        host = self._make_host({"AutoUpgrade": {"enable": 1}})
        module = _failing_module()
        changes = []
        reolink_camera._apply_host_switch(module, host, "auto_upgrade", False, check_mode=False, changes=changes)
        self.assertEqual(changes, ["auto_upgrade"])
        self.assertEqual(host.sent, [[{"cmd": "SetAutoUpgrade", "action": 0, "param": {"AutoUpgrade": {"enable": 0}}}]])

    def test_keeps_rest_of_block(self):
        host = self._make_host({"Ddns": {"enable": 1, "type": "no-ip", "domain": "cam.example"}})
        module = _failing_module()
        reolink_camera._apply_host_switch(module, host, "ddns", False, check_mode=False, changes=[])
        sent = host.sent[0][0]["param"]["Ddns"]
        self.assertEqual(sent, {"enable": 0, "type": "no-ip", "domain": "cam.example"})

    def test_idempotent_when_already_matching(self):
        host = self._make_host({"Upnp": {"enable": 0}})
        module = _failing_module()
        changes = []
        reolink_camera._apply_host_switch(module, host, "upnp", False, check_mode=False, changes=changes)
        self.assertEqual(changes, [])
        self.assertEqual(host.sent, [])

    def test_check_mode_does_not_send(self):
        host = self._make_host({"AutoUpgrade": {"enable": 1}})
        module = _failing_module()
        changes = []
        reolink_camera._apply_host_switch(module, host, "auto_upgrade", False, check_mode=True, changes=changes)
        self.assertEqual(changes, ["auto_upgrade"])
        self.assertEqual(host.sent, [])

    def test_fails_when_camera_does_not_take_it(self):
        host = self._make_host({"AutoUpgrade": {"enable": 1}})
        host.ignore_set = True
        module = _failing_module()
        with self.assertRaises(_FailJson):
            reolink_camera._apply_host_switch(module, host, "auto_upgrade", False, check_mode=False, changes=[])
        self.assertIn("still reports enable=1", module.fail_json.call_args.kwargs["msg"])

    def test_none_skipped(self):
        host = self._make_host({})
        module = _failing_module()
        changes = []
        reolink_camera._apply_host_switch(module, host, "upnp", None, check_mode=False, changes=changes)
        self.assertEqual(changes, [])


class TestPush(unittest.TestCase):
    # The three shapes GetPush/GetPushV20 return, keyed by what they switch.
    DEVICE_WIDE = {"enable": 1, "schedule": {"channel": 0, "table": {"MD": "1" * 168}}}
    PER_CHANNEL_V20 = {"scheduleEnable": 1, "schedule": {"channel": 0}}
    LEGACY = {"schedule": {"enable": 1, "channel": 0}}

    def _make_host(self, settings, channel_supported, device_supported=True):
        host = MagicMock()
        host._push_settings = {0: settings}
        host.get_state = AsyncMock()
        host.supported = lambda ch, cap: channel_supported if ch is not None else device_supported

        async def set_push(ch, enable):
            host.set_push_calls.append((ch, enable))
            key = "scheduleEnable" if "scheduleEnable" in settings else "enable"
            if "schedule" in settings and key not in settings:
                settings["schedule"]["enable"] = int(enable)
            else:
                settings[key] = int(enable)

        host.set_push_calls = []
        host.set_push = set_push
        return host

    def test_reads_each_shape(self):
        for settings in (self.DEVICE_WIDE, self.PER_CHANNEL_V20, self.LEGACY):
            host = self._make_host(dict(settings), channel_supported=True)
            self.assertIs(reolink_utils.push_enabled(host, 0), True)

    def test_device_wide_switch_used_when_channel_unsupported(self):
        # RLC-810A, RLC-822A and P330: supported(0, "push") is false.
        host = self._make_host({"enable": 1, "schedule": {"channel": 0}}, channel_supported=False)
        module = _failing_module()
        changes = []
        reolink_camera._apply_push(module, host, 0, False, check_mode=False, changes=changes)
        self.assertEqual(changes, ["push_notifications"])
        self.assertEqual(host.set_push_calls, [(None, False)])

    def test_channel_switch_used_when_supported(self):
        host = self._make_host({"scheduleEnable": 1, "schedule": {"channel": 0}}, channel_supported=True)
        module = _failing_module()
        reolink_camera._apply_push(module, host, 0, False, check_mode=False, changes=[])
        self.assertEqual(host.set_push_calls, [(0, False)])

    def test_idempotent_when_already_off(self):
        host = self._make_host({"enable": 0, "schedule": {"channel": 0}}, channel_supported=False)
        module = _failing_module()
        changes = []
        reolink_camera._apply_push(module, host, 0, False, check_mode=False, changes=changes)
        self.assertEqual(changes, [])
        self.assertEqual(host.set_push_calls, [])

    def test_unsupported_fails(self):
        host = self._make_host({}, channel_supported=False, device_supported=False)
        module = _failing_module()
        with self.assertRaises(_FailJson):
            reolink_camera._apply_push(module, host, 0, False, check_mode=False, changes=[])


class TestFacts(unittest.TestCase):
    def test_orientation_reads_isp_keys(self):
        host = MagicMock()
        host._isp_settings = {0: {"channel": 0, "rotation": 1, "mirroring": 0}}
        host.get_state = AsyncMock()
        self.assertEqual(reolink_facts._orientation(host, 0), {"flip": True, "mirror": False})

    def test_orientation_none_where_missing(self):
        host = MagicMock()
        host._isp_settings = {0: {"channel": 0}}
        host.get_state = AsyncMock()
        self.assertEqual(reolink_facts._orientation(host, 0), {"flip": None, "mirror": None})

    def test_get_switch(self):
        host = MagicMock()
        host.send = AsyncMock(return_value=[{"cmd": "GetUpnp", "code": 0, "value": {"Upnp": {"enable": 0}}}])
        self.assertEqual(reolink_utils.get_switch(host, "Upnp"), {"enable": 0})

    def test_clock(self):
        from datetime import datetime, timedelta, timezone

        edt = timezone(timedelta(hours=-4))
        camera_now = datetime.now(edt).replace(microsecond=0) + timedelta(seconds=30)
        host = MagicMock()
        host.async_get_time = AsyncMock(return_value=camera_now)
        settings = _get_time_response(time_zone=18000, dst_enable=1)
        host._time_settings = settings
        clock = reolink_facts._clock(host)
        self.assertEqual(clock["utc_offset"], -14400)
        self.assertAlmostEqual(clock["clock_error"], 30, delta=2)
        self.assertEqual(clock["local_time"], camera_now.replace(tzinfo=None).isoformat())
        self.assertEqual(clock["timezone_offset"], 18000)
        self.assertTrue(clock["dst"]["enabled"])
        self.assertEqual(clock["dst"]["end"], {"month": 10, "week": 5, "weekday": 0, "hour": 2, "minute": 0, "second": 0})


if __name__ == "__main__":
    unittest.main()
