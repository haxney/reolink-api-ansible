# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = """
name: reolink_utils
short_description: Shared utilities for Reolink Ansible modules
description:
  - Provides helpers to connect to a Reolink camera/NVR using the reolink-aio library.
"""

import asyncio
import ssl
import types
import traceback
import xml.etree.ElementTree as ET

REOLINK_IMP_ERR = None
try:
    from reolink_aio.api import Host
    from reolink_aio.exceptions import (
        ReolinkError,
        CredentialsInvalidError,
        LoginError,
        NotSupportedError,
        InvalidParameterError,
    )
    HAS_REOLINK = True
except ImportError:
    HAS_REOLINK = False
    REOLINK_IMP_ERR = traceback.format_exc()

from ansible.module_utils.basic import missing_required_lib  # noqa: E402

CONNECTION_ARGSPEC = dict(
    hostname=dict(type="str", required=True),
    username=dict(type="str", default="admin"),
    password=dict(type="str", required=True, no_log=True),
    port=dict(type="int", default=None),
    use_https=dict(type="bool", default=True),
    timeout=dict(type="int", default=30),
)


def check_reolink_import(module):
    if not HAS_REOLINK:
        module.fail_json(
            msg=missing_required_lib("reolink-aio"),
            exception=REOLINK_IMP_ERR,
        )


_loop = None


def _get_loop():
    """Return a reusable event loop, creating one if needed."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def run_async(coro):
    """Run a coroutine from synchronous Ansible module code."""
    return _get_loop().run_until_complete(coro)


def _endpoint(params):
    """(use_https, port) for params, never None.

    reolink-aio "recovers" from a failed HTTP(s) login by switching services
    on over the Baichuan protocol: HTTPS, RTSP and ONVIF in _login_try_ports(),
    which login() runs whenever the port or protocol is unknown, and RTMP in
    _login_open_port(). A module must not change what it was not asked to, so
    both are always set, and connect() replaces _login_open_port() with a
    plain login. HTTPS on 443 unless told otherwise.
    """
    use_https = params.get("use_https")
    if use_https is None:
        use_https = True
    port = params.get("port")
    if port is None:
        port = 443 if use_https else 80
    return use_https, port


def _login_without_opening_ports(self):
    """Stand-in for Host._login_open_port: log in, and let a failure fail.

    Also fast: a failed login (a 502 while the camera's HTTP service
    restarts, say) raises at once, so Ansible retries instead of waiting
    ~90 s for Baichuan port discovery to time out.
    """
    return self.login()


def connect(module):
    """Create and return a connected reolink_aio Host instance."""
    params = module.params
    use_https, port = _endpoint(params)
    kwargs = dict(
        host=params["hostname"],
        username=params["username"],
        password=params["password"],
        use_https=use_https,
        port=port,
    )

    async def _connect():
        host = Host(**kwargs)
        host._login_open_port = types.MethodType(_login_without_opening_ports, host)
        await host.get_host_data()
        return host

    try:
        return run_async(_connect())
    except CredentialsInvalidError as exc:
        module.fail_json(msg=f"Authentication failed for {params['hostname']}: {exc}")
    except LoginError as exc:
        module.fail_json(msg=f"Login failed for {params['hostname']}: {exc}")
    except ReolinkError as exc:
        module.fail_json(msg=f"Failed to connect to {params['hostname']}: {exc}")
    except Exception as exc:
        module.fail_json(msg=f"Unexpected error connecting to {params['hostname']}: {exc}")


def disconnect(module, host):
    """Log out from a connected Host instance, ignoring errors."""
    try:
        run_async(host.logout())
    except Exception:
        pass


# The Reolink app and web UI call these Flip and Mirror; the ISP block that
# GetIsp returns and SetIsp takes calls them rotation and mirroring.
ISP_ORIENTATION_KEYS = {"flip": "rotation", "mirror": "mirroring"}


def get_switch(host, block):
    """Read a host-level setting reolink-aio has no getter for, by Get<block>."""
    data = run_async(host.send([{"cmd": f"Get{block}", "action": 0, "param": {}}], expected_response_type="json"))
    return data[0]["value"][block]


def push_enabled(host, channel):
    """Whether push notifications are on for a channel, read fresh.

    GetPush/GetPushV20 come in three shapes, and reolink-aio's push_enabled()
    only answers for the per-channel ones. The RLC-810A, RLC-822A and P330
    have a single device-wide switch, for which supported(0, "push") is false.
    """
    run_async(host.get_state(cmd="GetPush", ch=channel))
    settings = host._push_settings[channel]
    if "scheduleEnable" in settings:  # per-channel switch (V20)
        return settings["scheduleEnable"] == 1
    if "enable" in settings:  # device-wide switch (V20)
        return settings["enable"] == 1
    return settings["schedule"]["enable"] == 1  # per-channel switch (legacy)


def credentials_work(params, username, password):
    """Whether username/password can log in to the device in params.

    Passwords cannot be read back, so this is how a module tells whether one
    already has the wanted value. A wrong password costs one failed login,
    which counts towards the device's lockout. Calls login() alone, with the
    port and protocol set, which never takes reolink-aio's port-opening
    recovery path (see connect()).
    """
    use_https, port = _endpoint(params)

    async def _try():
        probe = Host(host=params["hostname"], username=username, password=password, use_https=use_https, port=port)
        try:
            await probe.login()
            return True
        except CredentialsInvalidError:
            return False
        finally:
            try:
                await probe.logout()
            except Exception:
                pass

    return run_async(_try())


def switch_target(host, channel, capability):
    """Where to read or switch capability: the channel, or None for the
    device-wide switch on cameras that only have that one.

    Email, FTP and recording come in both shapes, and reolink-aio's per-channel
    calls raise (or read the wrong key) on a device-wide-only camera.
    """
    if host.supported(channel, capability):
        return channel
    if host.supported(None, capability):
        return None
    raise NotSupportedError(f"{capability} is not supported by this camera")


def stream_encoding(host, channel, stream):
    """A stream's encoding, "h264" or "h265".

    HTTP GetEnc's vType where the camera reports one; otherwise Baichuan
    command 56, the channel set_encoding() writes through. HTTP GetEnc on the
    P330 has no vType.
    """
    vtype = host._enc_settings.get(channel, {}).get(f"{stream}Stream", {}).get("vType")
    if vtype:
        return vtype
    root = ET.fromstring(run_async(host.baichuan.send(cmd_id=56, channel=channel)))
    return {"0": "h264", "1": "h265"}[root.find(f".//{stream}Stream/videoEncType").text]


class _Downloaded:
    """Stands in for the aiohttp response that upload_firmware() reads."""

    def __init__(self, data):
        self._data = data

    async def read(self):
        return self._data

    def release(self):
        pass


def verify_reolink_com(host, downloads=None):
    """Send host's requests to reolink.com over a certificate-verifying session.

    reolink-aio sends them on the session it uses for the cameras, which
    accepts any certificate (theirs are self-signed), so a firmware lookup or
    download could be answered by anyone on the path. Downloads already in
    `downloads` (url -> bytes) are served from it, so the bytes a module
    inspected are the bytes reolink-aio uploads.

    Returns a coroutine function that closes the verifying session.
    """
    import aiohttp  # reolink-aio's own dependency, needed only here

    original = host.send_reolink_com
    session = None

    async def send_reolink_com(URL, expected_response_type="application/json", user_agent="reolink_aio"):
        nonlocal session
        if downloads is not None and expected_response_type == "application/octet-stream" and URL in downloads:
            return _Downloaded(downloads[URL])
        if session is None:
            session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context()))
        camera_session = host._aiohttp_session
        host._aiohttp_session = session
        try:
            return await original(URL, expected_response_type, user_agent)
        finally:
            host._aiohttp_session = camera_session

    host.send_reolink_com = send_reolink_com

    async def close():
        if session is not None:
            await session.close()

    return close
