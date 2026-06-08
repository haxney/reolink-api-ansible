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
    kwargs = dict(
        host=params["hostname"],
        username=params["username"],
        password=params["password"],
    )
    if params.get("port") is not None:
        kwargs["port"] = params["port"]
    kwargs["use_https"] = params["use_https"]

    async def _connect():
        host = Host(**kwargs)
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
