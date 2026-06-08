#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: reolink_facts
short_description: Gather facts from a Reolink camera or NVR
version_added: "0.1.0"
description:
  - Connects to a Reolink IP camera or NVR and returns detailed device information,
    current settings, and per-channel state.
  - All returned data is read-only; this module never modifies the device.
author:
  - Dan Hackney (@haxney)
requirements:
  - reolink-aio >= 0.9.0
  - Python >= 3.11
options:
  hostname:
    description: IP address or hostname of the camera or NVR.
    type: str
    required: true
  username:
    description: Username for authentication.
    type: str
    default: admin
  password:
    description: Password for authentication.
    type: str
    required: true
  port:
    description: HTTP port. Defaults to 80 (or 443 if use_https is true).
    type: int
  use_https:
    description: Use HTTPS instead of HTTP.
    type: bool
  timeout:
    description: Connection timeout in seconds.
    type: int
    default: 30
"""

EXAMPLES = r"""
- name: Gather facts from a camera
  haxney.reolink.reolink_facts:
    hostname: 192.168.1.100
    password: mypassword
  register: cam_facts

- name: Show camera model
  ansible.builtin.debug:
    msg: "Camera model: {{ cam_facts.facts.model }}"

- name: Show all channel names on an NVR
  ansible.builtin.debug:
    msg: "Channel {{ item.channel }}: {{ item.name }}"
  loop: "{{ cam_facts.facts.channels }}"
"""

RETURN = r"""
changed:
  description: Always false; this module is read-only.
  type: bool
  returned: always
facts:
  description: Device facts.
  type: dict
  returned: always
  contains:
    model:
      description: Model name of the device.
      type: str
    is_nvr:
      description: True if the device is an NVR.
      type: bool
    num_channels:
      description: Number of camera channels.
      type: int
    mac_address:
      description: MAC address.
      type: str
    serial:
      description: Serial number.
      type: str
    firmware_version:
      description: Firmware version string.
      type: str
    hardware_version:
      description: Hardware version string.
      type: str
    local_ip:
      description: Configured IP address of the device.
      type: str
    rtmp_port:
      description: RTMP streaming port.
      type: int
    rtsp_port:
      description: RTSP streaming port.
      type: int
    onvif_port:
      description: ONVIF port.
      type: int
    channels:
      description: Per-channel information.
      type: list
      elements: dict
      contains:
        channel:
          description: Channel index (0-based).
          type: int
        name:
          description: Camera name.
          type: str
        model:
          description: Camera model (may differ from NVR model).
          type: str
        ir_lights:
          description: IR lights enabled state.
          type: bool
        motion_detection:
          description: Motion detection enabled.
          type: bool
        recording:
          description: Recording enabled.
          type: bool
        audio:
          description: Audio recording enabled.
          type: bool
        stream_sources:
          description: Available stream URLs (RTSP).
          type: dict
"""

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.haxney.reolink.plugins.module_utils.reolink_utils import (
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        HAS_REOLINK,
    )
except ImportError:
    from ..module_utils.reolink_utils import (  # type: ignore[no-redef]
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        HAS_REOLINK,
    )


def _safe_get(fn, *args, default=None):
    try:
        return fn(*args)
    except Exception:
        return default


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
    try:
        try:
            run_async(host.get_states())
        except Exception as exc:
            module.warn(f"Could not retrieve channel states: {exc}")

        channels = []
        for ch in range(host.num_channels):
            stream_sources = {}
            for stream in ("main", "sub"):
                src = _safe_get(lambda ch=ch, stream=stream: run_async(host.get_rtsp_stream_source(ch, stream)), default=None)
                if src:
                    stream_sources[stream] = src

            channels.append({
                "channel": ch,
                "name": _safe_get(host.camera_name, ch, default=""),
                "model": _safe_get(host.camera_model, ch, default=""),
                "ir_lights": _safe_get(host.ir_enabled, ch, default=None),
                "recording": _safe_get(host.recording_enabled, ch, default=None) if hasattr(host, "recording_enabled") else None,
                "audio": _safe_get(host.audio_record, ch, default=None),
                "stream_sources": stream_sources,
            })

        facts = {
            "model": _safe_get(lambda: host.nvr_name, default=""),
            "is_nvr": host.is_nvr,
            "num_channels": host.num_channels,
            "mac_address": _safe_get(lambda: host.mac_address, default=""),
            "serial": _safe_get(lambda: host.serial(), default=""),
            "firmware_version": str(_safe_get(lambda: host.sw_version, default="")),
            "hardware_version": str(_safe_get(lambda: host.hardware_version, default="")) if hasattr(host, "hardware_version") else "",
            "local_ip": _safe_get(lambda: host.local_ip, default="") if hasattr(host, "local_ip") else "",
            "rtmp_port": _safe_get(lambda: host.rtmp_port, default=None),
            "rtsp_port": _safe_get(lambda: host.rtsp_port, default=None),
            "onvif_port": _safe_get(lambda: host.onvif_port, default=None),
            "channels": channels,
        }

    finally:
        disconnect(module, host)

    module.exit_json(changed=False, facts=facts)


if __name__ == "__main__":
    main()
