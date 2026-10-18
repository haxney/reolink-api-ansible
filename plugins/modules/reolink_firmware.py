#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: reolink_firmware
short_description: Install the newest firmware Reolink offers for a camera
version_added: "0.5.0"
description:
  - Asks reolink.com for the newest firmware for the camera's model and
    hardware version. If it is newer than the running firmware, downloads it
    to the host running the module and uploads it to the camera, which
    installs it and reboots. The task returns once the camera reports the new
    version, or fails after about five minutes.
  - The camera never contacts Reolink. reolink-aio's update_firmware() first
    asks the camera to fetch the update itself (UpgradeOnline); this module
    only ever uploads.
  - Every request to reolink.com verifies TLS certificates (reolink-aio on its
    own does not), the package must come from a reolink.com or reolink.us
    host, and the bytes uploaded are the bytes hashed in C(package.sha256).
  - Never installs older firmware.
  - In check mode the package is downloaded and unpacked, so a bad link or a
    package without firmware in it shows up, but nothing is sent to the
    camera.
  - Installing reboots the camera, which records nothing for about a minute,
    and an upgrade can reset settings. Re-apply and re-check the camera's
    configuration afterwards.
author:
  - Dan Hackney (@haxney)
requirements:
  - reolink-aio >= 0.9.0
  - Python >= 3.11
options:
  hostname:
    description: IP address or hostname of the camera.
    type: str
    required: true
  username:
    description: Username for authentication. Must be an admin.
    type: str
    default: admin
  password:
    description: Password for authentication.
    type: str
    required: true
  port:
    description: HTTP port. Defaults to 443 (or 80 if use_https is false).
    type: int
  use_https:
    description: Use HTTPS instead of HTTP.
    type: bool
    default: true
  timeout:
    description: Connection timeout in seconds.
    type: int
    default: 30
"""

EXAMPLES = r"""
- name: Install the newest firmware, if there is newer
  haxney.reolink.reolink_firmware:
    hostname: 192.168.1.100
    password: mypassword
  register: fw

- name: Show what happened
  ansible.builtin.debug:
    msg: "{{ fw.previous_version }} -> {{ fw.version }}"
"""

RETURN = r"""
changed:
  description: Whether firmware was installed (in check mode, would be).
  type: bool
  returned: always
previous_version:
  description: Firmware running before the task.
  type: str
  returned: always
latest_version:
  description: Newest firmware reolink.com offers for this model and hardware version.
  type: str
  returned: always
version:
  description: Firmware running after the task.
  type: str
  returned: always
package:
  description: The firmware package, when one was downloaded.
  type: dict
  returned: when newer firmware exists
  contains:
    url:
      description: Where it was downloaded from.
      type: str
    file:
      description: The firmware file inside the downloaded zip.
      type: str
    size:
      description: Size of the downloaded zip, in bytes.
      type: int
    sha256:
      description: SHA-256 of the downloaded zip, which is what was uploaded.
      type: str
"""

import hashlib
import io
import zipfile
from urllib.parse import urlparse

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.haxney.reolink.plugins.module_utils.reolink_utils import (
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        verify_reolink_com,
        HAS_REOLINK,
    )
except ImportError:
    from ..module_utils.reolink_utils import (  # type: ignore[no-redef]
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        verify_reolink_com,
        HAS_REOLINK,
    )

# Hosts Reolink serves firmware from. The lookup that names the URL is
# verified, so this is defence in depth against Reolink's answer itself
# pointing somewhere odd; a new CDN fails loudly here rather than quietly.
_FIRMWARE_HOST_SUFFIXES = (".reolink.com", ".reolink.us")


def _firmware_file(data):
    """The firmware file inside a Reolink download, as reolink-aio finds it."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.endswith((".pak", ".paks")):
                return name
    return None


def _ensure_latest(module, host, downloads):
    """Install the newest firmware if it is newer. Returns the result dict."""
    try:
        latest = run_async(host._check_reolink_firmware(None))
    except Exception as exc:
        module.fail_json(msg=f"Could not look up firmware on reolink.com: {exc}")

    current = str(host.sw_version)
    result = dict(changed=False, previous_version=current, latest_version=latest.version_string, version=current)
    if not latest > host.sw_version_object:
        return result

    url = latest.download_url or ""
    netloc = urlparse(url).hostname or ""
    if urlparse(url).scheme != "https" or not (netloc == "reolink.com" or netloc.endswith(_FIRMWARE_HOST_SUFFIXES)):
        module.fail_json(msg=f"Refusing firmware from {url!r}: not an https URL on a Reolink host", **result)

    try:
        response = run_async(host.send_reolink_com(url, expected_response_type="application/octet-stream"))
        data = run_async(response.read())
        response.release()
    except Exception as exc:
        module.fail_json(msg=f"Could not download {url}: {exc}", **result)
    firmware_file = _firmware_file(data)
    if firmware_file is None:
        module.fail_json(msg=f"{url} holds no .pak firmware file", **result)
    downloads[url] = data
    result["package"] = dict(url=url, file=firmware_file, size=len(data), sha256=hashlib.sha256(data).hexdigest())
    result["changed"] = True
    if module.check_mode:
        return result

    # upload_firmware() waits for the camera to report this version, and
    # reads it from here.
    host._latest_sw_version[None] = latest
    try:
        run_async(host.upload_firmware(None, latest))
    except Exception as exc:
        module.fail_json(msg=f"Firmware upload or install failed: {exc}", **result)

    result["version"] = str(host.sw_version)
    if not host.sw_version_object >= latest:
        module.fail_json(msg=f"The camera reports {result['version']} after installing {latest.version_string}", **result)
    return result


def main():
    module = AnsibleModule(
        argument_spec=dict(
            hostname=dict(type="str", required=True),
            username=dict(type="str", default="admin"),
            password=dict(type="str", required=True, no_log=True),
            port=dict(type="int"),
            use_https=dict(type="bool", default=True),
            timeout=dict(type="int", default=30),
        ),
        supports_check_mode=True,
    )

    check_reolink_import(module)

    host = connect(module)
    downloads = {}
    close = verify_reolink_com(host, downloads)
    try:
        result = _ensure_latest(module, host, downloads)
    finally:
        run_async(close())
        disconnect(module, host)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
