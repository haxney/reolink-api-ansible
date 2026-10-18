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
import types
import traceback

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


def connect(module):
    """Create and return a connected reolink_aio Host instance."""
    params = module.params
    use_https = params["use_https"]
    kwargs = dict(
        host=params["hostname"],
        username=params["username"],
        password=params["password"],
        use_https=use_https,
        # Set port explicitly so login() skips the slow Baichuan port-detection
        # path (_login_try_ports). Reolink cameras use 443 for HTTPS and 80 for HTTP.
        port=params["port"] if params.get("port") is not None else (443 if use_https else 80),
    )

    async def _connect():
        host = Host(**kwargs)
        # When port and use_https are pre-configured, bypass the slow Baichuan
        # recovery fallback. If login fails (e.g., 502 while camera HTTP service
        # is restarting), raise immediately so Ansible retries quickly instead of
        # waiting ~90s for Baichuan port discovery to time out.
        # Note: this does NOT disable the initial Baichuan path (_login_try_ports)
        # for cameras where port/use_https are not yet known (port=None case).
        async def _fast_login_open_port(self):
            if self._port is None or self._use_https is None:
                await self._login_try_ports()
                return
            await self.login()
        host._login_open_port = types.MethodType(_fast_login_open_port, host)
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
