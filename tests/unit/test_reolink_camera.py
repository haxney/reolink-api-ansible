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


def _make_aiohttp_stub():
    """Just enough aiohttp for verify_reolink_com(): sessions that record
    their SSL setting and whether they were closed."""
    mod = types.ModuleType("aiohttp")

    class TCPConnector:
        def __init__(self, ssl=None):
            self.ssl = ssl

    class ClientSession:
        def __init__(self, connector=None):
            self.connector = connector
            self.closed = False

        async def close(self):
            self.closed = True

    mod.TCPConnector = TCPConnector
    mod.ClientSession = ClientSession
    sys.modules.setdefault("aiohttp", mod)


_make_aiohttp_stub()


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
from plugins.modules import reolink_firmware  # noqa: E402


class _FailJson(Exception):
    """Stands in for AnsibleModule.fail_json, which never returns."""


def _failing_module():
    module = MagicMock()
    module.fail_json.side_effect = _FailJson
    return module


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


class TestEndpoint(unittest.TestCase):
    """reolink-aio switches services on when the port or protocol is unknown
    (_login_try_ports): HTTPS, RTSP and ONVIF. Neither may ever be None."""

    def test_unset_means_https_on_443(self):
        self.assertEqual(reolink_utils._endpoint({"use_https": None, "port": None}), (True, 443))

    def test_http_on_80(self):
        self.assertEqual(reolink_utils._endpoint({"use_https": False, "port": None}), (False, 80))

    def test_explicit_port_kept(self):
        self.assertEqual(reolink_utils._endpoint({"use_https": True, "port": 8443}), (True, 8443))

    def test_connect_never_opens_ports(self):
        from reolink_aio.api import Host as FakeHost

        class GuardedHost(FakeHost):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.init_kwargs = kwargs
                self.logins = 0

            async def login(self):
                self.logins += 1

            async def _login_try_ports(self):
                raise AssertionError("_login_try_ports switches ports on")

            async def get_host_data(self):
                await self._login_open_port()

        module = MagicMock()
        module.params = {"hostname": "192.168.1.1", "username": "admin", "password": "pass", "port": None, "use_https": None}
        module.fail_json.side_effect = AssertionError
        with patch.object(reolink_utils, "Host", GuardedHost):
            host = reolink_utils.connect(module)
        self.assertEqual((host.init_kwargs["use_https"], host.init_kwargs["port"]), (True, 443))
        self.assertEqual(host.logins, 1)


class TestCredentialsWork(unittest.TestCase):
    def _run(self, login_error):
        from reolink_aio.api import Host as FakeHost

        class LoginHost(FakeHost):
            async def login(self):
                if login_error:
                    raise login_error

        with patch.object(reolink_utils, "Host", LoginHost):
            return reolink_utils.credentials_work({"hostname": "h", "use_https": True, "port": None}, "viewer", "pw")

    def test_true_when_login_works(self):
        self.assertIs(self._run(None), True)

    def test_false_on_bad_credentials(self):
        from reolink_aio.exceptions import CredentialsInvalidError
        self.assertIs(self._run(CredentialsInvalidError("password wrong")), False)

    def test_other_errors_raise(self):
        from reolink_aio.exceptions import LoginError
        with self.assertRaises(LoginError):
            self._run(LoginError("502"))


class TestApplyNtp(unittest.TestCase):
    def _make_host(self, ntp):
        host = MagicMock()
        host._ntp_settings = {"Ntp": ntp}
        host.get_state = AsyncMock()
        host.set_ntp = AsyncMock()
        host.sync_ntp = AsyncMock()
        return host

    def test_only_differing_fields_sent(self):
        host = self._make_host({"enable": 1, "server": "pool.ntp.org", "port": 123, "interval": 1440})
        changes = []
        reolink_camera._apply_ntp(
            _failing_module(), host,
            {"enabled": True, "server": "172.16.4.40", "port": 123, "interval": 1440, "sync_now": False},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, ["ntp"])
        host.set_ntp.assert_awaited_once_with(server="172.16.4.40")

    def test_idempotent_and_sync_now_is_not_a_change(self):
        host = self._make_host({"enable": 1, "server": "172.16.4.40", "port": 123, "interval": 1440})
        changes = []
        reolink_camera._apply_ntp(
            _failing_module(), host,
            {"enabled": True, "server": "172.16.4.40", "port": 123, "interval": 1440, "sync_now": True},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, [])
        host.set_ntp.assert_not_awaited()
        host.sync_ntp.assert_awaited_once()

    def test_check_mode_does_not_call_api(self):
        host = self._make_host({"enable": 0, "server": "pool.ntp.org", "port": 123, "interval": 1440})
        changes = []
        reolink_camera._apply_ntp(
            _failing_module(), host, {"enabled": True, "sync_now": True}, check_mode=True, changes=changes,
        )
        self.assertEqual(changes, ["ntp"])
        host.set_ntp.assert_not_awaited()
        host.sync_ntp.assert_not_awaited()

    def test_none_skipped(self):
        host = self._make_host({})
        changes = []
        reolink_camera._apply_ntp(_failing_module(), host, None, check_mode=False, changes=changes)
        self.assertEqual(changes, [])


class TestApplyVideo(unittest.TestCase):
    def _make_host(self, main_stream):
        host = MagicMock()
        host._enc_settings = {0: {"mainStream": main_stream}}
        host.bit_rate_list = lambda ch, stream: []
        host.frame_rate_list = lambda ch, stream: []
        host.set_encoding = AsyncMock()
        host.set_bit_rate = AsyncMock()
        host.set_frame_rate = AsyncMock()
        return host

    def test_only_differing_settings_sent(self):
        host = self._make_host({"vType": "h265", "bitRate": 4096, "frameRate": 15})
        changes = []
        reolink_camera._apply_video(
            _failing_module(), host, channel=0,
            video_params={"stream": "main", "encoding": "h265", "bitrate": 8192, "frame_rate": 15},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, ["video_bitrate"])
        host.set_encoding.assert_not_awaited()
        host.set_bit_rate.assert_awaited_once_with(0, 8192, "main")
        host.set_frame_rate.assert_not_awaited()

    def test_encoding_read_over_baichuan_when_http_lacks_it(self):
        # P330: HTTP GetEnc has no vType; Baichuan command 56 has videoEncType.
        host = self._make_host({"bitRate": 4096, "frameRate": 15})
        host.baichuan.send = AsyncMock(return_value=(
            "<body><Compression><mainStream><videoEncType>1</videoEncType></mainStream>"
            "<subStream><videoEncType>0</videoEncType></subStream></Compression></body>"))
        changes = []
        reolink_camera._apply_video(
            _failing_module(), host, channel=0,
            video_params={"stream": "main", "encoding": "h265", "bitrate": 4096, "frame_rate": 15},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, [])
        host.set_encoding.assert_not_awaited()

    def test_bitrate_the_camera_does_not_offer_fails(self):
        host = self._make_host({"vType": "h264", "bitRate": 256, "frameRate": 10})
        host.bit_rate_list = lambda ch, stream: [64, 128, 160, 192, 256, 384, 512]
        module = _failing_module()
        with self.assertRaises(_FailJson):
            reolink_camera._apply_video(
                module, host, channel=0,
                video_params={"stream": "sub", "bitrate": 1024},
                check_mode=False, changes=[],
            )
        self.assertIn("not one the camera offers", module.fail_json.call_args.kwargs["msg"])
        host.set_bit_rate.assert_not_awaited()

    def test_unknown_current_value_is_sent(self):
        host = self._make_host({})  # no vType etc.
        host.baichuan.send = AsyncMock(side_effect=Exception("no Baichuan"))
        changes = []
        reolink_camera._apply_video(
            _failing_module(), host, channel=0,
            video_params={"stream": "main", "encoding": "h265"},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, ["video_encoding"])
        host.set_encoding.assert_awaited_once_with(0, "h265", "main")


class TestApplyImage(unittest.TestCase):
    def test_only_differing_fields_sent(self):
        host = MagicMock()
        host._image_settings = {0: {"Image": {"bright": 128, "contrast": "100", "hue": 128}}}
        host.set_image = AsyncMock()
        changes = []
        reolink_camera._apply_image(
            _failing_module(), host, channel=0,
            image_params={"brightness": 200, "contrast": 100, "hue": None},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, ["image"])
        host.set_image.assert_awaited_once_with(0, bright=200)


class TestApplyOsd(unittest.TestCase):
    def _make_host(self):
        host = MagicMock()
        host._osd_settings = {0: {"Osd": {
            "osdChannel": {"enable": 1, "name": "Garage", "pos": "Lower Right"},
            "osdTime": {"enable": 1, "pos": "Top Center"},
            "watermark": 0,
        }}}
        host.get_state = AsyncMock()
        host.send_setting = AsyncMock()
        return host

    def test_idempotent_when_matching(self):
        host = self._make_host()
        changes = []
        reolink_camera._apply_osd(
            _failing_module(), host, 0, {"name": "Garage", "date_position": "Top Center", "watermark": False},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, [])
        host.send_setting.assert_not_awaited()

    def test_name_change_sent(self):
        host = self._make_host()
        changes = []
        reolink_camera._apply_osd(
            _failing_module(), host, 0, {"name": "Garage Main Entrance", "watermark": False},
            check_mode=False, changes=changes,
        )
        self.assertEqual(changes, ["osd"])
        osd = host.send_setting.await_args.args[0][0]["param"]["Osd"]
        self.assertEqual(osd["osdChannel"]["name"], "Garage Main Entrance")

    def test_off_hides_the_overlay(self):
        host = self._make_host()
        reolink_camera._apply_osd(
            _failing_module(), host, 0, {"date_position": "Off"}, check_mode=False, changes=[],
        )
        osd = host.send_setting.await_args.args[0][0]["param"]["Osd"]
        self.assertEqual(osd["osdTime"]["enable"], 0)


class TestApplyCompared(unittest.TestCase):
    def test_skips_when_matching(self):
        apply = AsyncMock()
        changes = []
        reolink_camera._apply_compared(_failing_module(), "audio", True, True, apply, check_mode=False, changes=changes)
        self.assertEqual(changes, [])
        apply.assert_not_called()

    def test_unknown_current_is_sent(self):
        apply = AsyncMock()
        changes = []
        reolink_camera._apply_compared(_failing_module(), "audio", True, None, apply, check_mode=False, changes=changes)
        self.assertEqual(changes, ["audio"])
        apply.assert_awaited_once()


class TestApplyChannelOrDevice(unittest.TestCase):
    """email_notifications, ftp_upload and recording."""

    def _make_host(self, channel_supported, device_supported=True, enabled=True):
        host = MagicMock()
        host.state = {"enabled": enabled}
        host.supported = lambda ch, cap: channel_supported if ch is not None else device_supported
        host.get_state = AsyncMock()
        host.read = lambda target: host.state["enabled"]

        async def write(target, value):
            host.writes.append((target, value))
            host.state["enabled"] = value

        host.writes = []
        host.write = write
        return host

    def _apply(self, host, value, changes, check_mode=False):
        reolink_camera._apply_channel_or_device(
            _failing_module(), host, 0, value, "email_notifications", "email",
            host.read, host.write, "GetEmail", check_mode, changes)

    def test_device_wide_when_channel_unsupported(self):
        host = self._make_host(channel_supported=False)
        changes = []
        self._apply(host, False, changes)
        self.assertEqual(changes, ["email_notifications"])
        self.assertEqual(host.writes, [(None, False)])

    def test_channel_when_supported(self):
        host = self._make_host(channel_supported=True)
        self._apply(host, False, [])
        self.assertEqual(host.writes, [(0, False)])

    def test_idempotent(self):
        host = self._make_host(channel_supported=False, enabled=False)
        changes = []
        self._apply(host, False, changes)
        self.assertEqual(changes, [])
        self.assertEqual(host.writes, [])

    def test_unsupported_fails(self):
        host = self._make_host(channel_supported=False, device_supported=False)
        with self.assertRaises(_FailJson):
            self._apply(host, False, [])


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


class TestVerifyReolinkCom(unittest.TestCase):
    def _make_host(self):
        host = MagicMock()
        camera_session = object()
        host._aiohttp_session = camera_session
        host.seen_sessions = []

        async def send_reolink_com(URL, expected_response_type="application/json", user_agent="reolink_aio"):
            host.seen_sessions.append(host._aiohttp_session)
            return {"url": URL}

        host.send_reolink_com = send_reolink_com
        return host, camera_session

    def test_reolink_com_uses_a_verifying_session_and_restores_the_camera_one(self):
        import ssl
        host, camera_session = self._make_host()
        close = reolink_utils.verify_reolink_com(host)
        reolink_utils.run_async(host.send_reolink_com("https://reolink.com/x"))
        used = host.seen_sessions[0]
        self.assertIsNot(used, camera_session)
        self.assertEqual(used.connector.ssl.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(used.connector.ssl.check_hostname)
        self.assertIs(host._aiohttp_session, camera_session)
        reolink_utils.run_async(close())
        self.assertTrue(used.closed)

    def test_downloads_served_from_memory(self):
        host, _ = self._make_host()
        reolink_utils.verify_reolink_com(host, downloads={"https://cdn/fw.zip": b"PK..."})
        response = reolink_utils.run_async(
            host.send_reolink_com("https://cdn/fw.zip", expected_response_type="application/octet-stream"))
        self.assertEqual(reolink_utils.run_async(response.read()), b"PK...")
        self.assertEqual(host.seen_sessions, [])


class TestFacts(unittest.TestCase):
    def test_switch_state_device_wide(self):
        host = MagicMock()
        host.supported = lambda ch, cap: ch is None
        host.email_enabled = lambda target: {None: False}[target]
        self.assertIs(reolink_facts._switch_state(host, 0, "email", host.email_enabled), False)

    def test_streams(self):
        host = MagicMock()
        host._enc_settings = {0: {
            "mainStream": {"bitRate": 4096, "frameRate": 15, "width": 3840, "height": 2160},
            "subStream": {"vType": "h264", "bitRate": 512, "frameRate": 7, "width": 640, "height": 360},
        }}
        host.baichuan.send = AsyncMock(return_value=(
            "<body><Compression><mainStream><videoEncType>1</videoEncType></mainStream></Compression></body>"))
        streams = reolink_facts._streams(host, 0)
        self.assertEqual(streams["main"], {"encoding": "h265", "bitrate": 4096, "frame_rate": 15, "width": 3840, "height": 2160})
        self.assertEqual(streams["sub"]["encoding"], "h264")
        self.assertEqual(streams["sub"]["bitrate"], 512)

    def test_active_webhooks(self):
        host = MagicMock()
        host.supported = lambda ch, cap: True
        host.get_state = AsyncMock()
        host._webhook_settings = {0: {"WebHook": [
            {"index": 0, "indexEnable": 1}, {"index": 1, "indexEnable": 0}, {"index": 2, "indexEnable": -1},
        ]}}
        self.assertEqual(reolink_facts._active_webhooks(host, 0), 1)

    def test_no_webhooks_without_support(self):
        host = MagicMock()
        host.supported = lambda ch, cap: False
        self.assertEqual(reolink_facts._active_webhooks(host, 0), 0)

    def test_firmware(self):
        latest = MagicMock(version_string="v3.1.0.5000_2601010000", download_url="https://x", release_notes="notes")
        latest.__gt__ = lambda self, other: True
        host = MagicMock(sw_version="v3.1.0.4569_2502181272")
        host._check_reolink_firmware = AsyncMock(return_value=latest)
        fw = reolink_facts._firmware(host)
        self.assertEqual(fw["latest"], "v3.1.0.5000_2601010000")
        self.assertIs(fw["update_available"], True)
        host._check_reolink_firmware.assert_awaited_once_with(None)

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
        self.assertEqual(clock["date_format"], "DD/MM/YYYY")
        self.assertIs(clock["hours_24"], False)
        self.assertTrue(clock["dst"]["enabled"])
        self.assertEqual(clock["dst"]["end"], {"month": 10, "week": 5, "weekday": 0, "hour": 2, "minute": 0, "second": 0})


class _Version:
    """Comparable like reolink-aio's SoftwareVersion."""

    def __init__(self, n, url=None):
        self.n = n
        self.version_string = f"v3.1.0.{n}"
        self.download_url = url

    def __gt__(self, other):
        return self.n > other.n

    def __ge__(self, other):
        return self.n >= other.n


def _zip(*names):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, b"firmware")
    return buf.getvalue()


class TestFirmware(unittest.TestCase):
    URL = "https://home-cdn.reolink.us/wp-content/uploads/fw.zip"

    def _make_host(self, running, latest, package=None):
        host = MagicMock()
        host.state = {"running": _Version(running)}
        type(host).sw_version_object = property(lambda h: h.state["running"])
        type(host).sw_version = property(lambda h: h.state["running"].version_string)
        host._check_reolink_firmware = AsyncMock(return_value=latest)
        host._latest_sw_version = {}
        host.downloaded = []
        host.uploaded = None

        async def send_reolink_com(URL, expected_response_type="application/json", user_agent="reolink_aio"):
            host.downloaded.append(URL)
            response = MagicMock()
            response.read = AsyncMock(return_value=package)
            return response

        async def upload_firmware(channel, new_version):
            host.uploaded = (channel, new_version)
            host.state["running"] = new_version

        host.send_reolink_com = send_reolink_com
        host.upload_firmware = upload_firmware
        return host

    def _module(self, check_mode=False):
        module = _failing_module()
        module.check_mode = check_mode
        return module

    def test_nothing_newer(self):
        host = self._make_host(5764, _Version(5764, self.URL))
        result = reolink_firmware._ensure_latest(self._module(), host, {})
        self.assertFalse(result["changed"])
        self.assertEqual(host.downloaded, [])

    def test_check_mode_downloads_but_does_not_upload(self):
        host = self._make_host(4569, _Version(5764, self.URL), _zip("IPC_523128M8MP.5764_2512171966.pak"))
        result = reolink_firmware._ensure_latest(self._module(check_mode=True), host, {})
        self.assertTrue(result["changed"])
        self.assertEqual(result["package"]["file"], "IPC_523128M8MP.5764_2512171966.pak")
        self.assertEqual(len(result["package"]["sha256"]), 64)
        self.assertIsNone(host.uploaded)
        self.assertEqual(result["version"], "v3.1.0.4569")

    def test_installs_and_reads_back(self):
        latest = _Version(5764, self.URL)
        package = _zip("fw.pak")
        host = self._make_host(4569, latest, package)
        downloads = {}
        result = reolink_firmware._ensure_latest(self._module(), host, downloads)
        self.assertTrue(result["changed"])
        self.assertEqual(host.uploaded, (None, latest))
        self.assertIs(host._latest_sw_version[None], latest)
        # What upload_firmware() downloads is served from this, so it is the
        # same bytes that were hashed.
        self.assertEqual(downloads[self.URL], package)
        self.assertEqual(result["version"], "v3.1.0.5764")

    def test_refuses_a_non_reolink_url(self):
        host = self._make_host(4569, _Version(5764, "https://evil.example/fw.zip"), _zip("fw.pak"))
        module = self._module()
        with self.assertRaises(_FailJson):
            reolink_firmware._ensure_latest(module, host, {})
        self.assertIn("Refusing firmware", module.fail_json.call_args.kwargs["msg"])
        self.assertEqual(host.downloaded, [])

    def test_refuses_a_package_without_firmware(self):
        host = self._make_host(4569, _Version(5764, self.URL), _zip("README.txt"))
        with self.assertRaises(_FailJson):
            reolink_firmware._ensure_latest(self._module(), host, {})


if __name__ == "__main__":
    unittest.main()
