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
    outbound:
      description:
        - Switches for the device's connections to outside servers, each true
          if on, or null if it could not be read. Push is per channel, under
          C(channels).
      type: dict
      version_added: "0.3.0"
      contains:
        p2p:
          description: P2P relay through Reolink's servers.
          type: bool
        auto_upgrade:
          description: Automatic firmware upgrades from Reolink's servers.
          type: bool
        upnp:
          description: UPnP port mapping on the router.
          type: bool
        ddns:
          description: Dynamic DNS registration.
          type: bool
    net_port:
      description: Whether each network service is enabled, or null if unknown.
      type: dict
      version_added: "0.3.0"
      contains:
        rtsp:
          description: RTSP server.
          type: bool
        onvif:
          description: ONVIF server.
          type: bool
        rtmp:
          description: RTMP server.
          type: bool
    time:
      description: The device clock and its time-zone settings. Null if they could not be read.
      type: dict
      version_added: "0.3.0"
      contains:
        local_time:
          description: The wall-clock time the device shows, as C(YYYY-MM-DDTHH:MM:SS).
          type: str
        utc_offset:
          description:
            - The offset from UTC the device is applying now, DST included, in
              seconds EAST of UTC (e.g. C(-14400) for UTC-4).
            - Note the sign is the reverse of C(timezone_offset).
          type: int
        clock_error:
          description:
            - Seconds the device clock is ahead of the clock of the host running
              the module (negative if behind), compared in UTC.
          type: int
        timezone_offset:
          description: Configured standard-time offset, in Reolink's convention of seconds WEST of UTC.
          type: int
        dst:
          description: Configured DST rule, in the shape of reolink_camera's C(time.dst) option.
          type: dict
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
        flip:
          description: Image flipped vertically (ISP C(rotation)). Null if the camera has no such setting.
          type: bool
          version_added: "0.3.0"
        mirror:
          description: Image mirrored horizontally (ISP C(mirroring)). Null if the camera has no such setting.
          type: bool
          version_added: "0.3.0"
        push_notifications:
          description: Push notifications through Reolink's servers. Null if unknown.
          type: bool
          version_added: "0.3.0"
        stream_sources:
          description: Available stream URLs (RTSP).
          type: dict
"""

from datetime import datetime, timezone

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.haxney.reolink.plugins.module_utils.reolink_utils import (
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        HAS_REOLINK,
        ISP_ORIENTATION_KEYS,
        get_switch,
        push_enabled,
    )
except ImportError:
    from ..module_utils.reolink_utils import (  # type: ignore[no-redef]
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        HAS_REOLINK,
        ISP_ORIENTATION_KEYS,
        get_switch,
        push_enabled,
    )


def _safe_get(fn, *args, default=None):
    try:
        return fn(*args)
    except Exception:
        return default


# Option name -> Reolink Dst key suffix, as in reolink_camera's time.dst.
_DST_TRANSITION_SUFFIXES = {
    "month": "Mon",
    "week": "Week",
    "weekday": "Weekday",
    "hour": "Hour",
    "minute": "Min",
    "second": "Sec",
}


# Host-level switches read with a raw Get<block>, as reolink_camera sets them.
# Fact name -> the API's block name.
_OUTBOUND_SWITCHES = {
    "p2p": "P2p",
    "auto_upgrade": "AutoUpgrade",
    "upnp": "Upnp",
    "ddns": "Ddns",
}


def _orientation(host, ch):
    """flip and mirror for one channel, None where the camera lacks them."""
    run_async(host.get_state(cmd="GetIsp", ch=ch))
    isp = host._isp_settings.get(ch) or {}
    return {name: bool(isp[key]) if key in isp else None for name, key in ISP_ORIENTATION_KEYS.items()}


def _clock(host):
    """The device clock and time-zone settings; see RETURN for the fields."""
    camera_now = run_async(host.async_get_time())
    host_now = datetime.now(timezone.utc)
    settings = host._time_settings
    dst = settings.get("Dst")
    if dst is not None:
        dst = {
            "enabled": bool(dst.get("enable")),
            "offset": dst.get("offset"),
            "start": {name: dst.get("start" + suffix) for name, suffix in _DST_TRANSITION_SUFFIXES.items()},
            "end": {name: dst.get("end" + suffix) for name, suffix in _DST_TRANSITION_SUFFIXES.items()},
        }
    return {
        "local_time": camera_now.replace(tzinfo=None).isoformat(),
        "utc_offset": int(camera_now.utcoffset().total_seconds()),
        "clock_error": round((camera_now - host_now).total_seconds()),
        "timezone_offset": settings["Time"]["timeZone"],
        "dst": dst,
    }


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
            orientation = _safe_get(_orientation, host, ch, default={"flip": None, "mirror": None})

            channels.append({
                "channel": ch,
                "name": _safe_get(host.camera_name, ch, default=""),
                "model": _safe_get(host.camera_model, ch, default=""),
                "ir_lights": _safe_get(host.ir_enabled, ch, default=None),
                "recording": _safe_get(host.recording_enabled, ch, default=None) if hasattr(host, "recording_enabled") else None,
                "audio": _safe_get(host.audio_record, ch, default=None),
                "flip": orientation["flip"],
                "mirror": orientation["mirror"],
                "push_notifications": _safe_get(push_enabled, host, ch, default=None),
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
            "outbound": {name: _safe_get(lambda block=block: bool(get_switch(host, block)["enable"]), default=None) for name, block in _OUTBOUND_SWITCHES.items()},
            "net_port": {
                "rtsp": _safe_get(lambda: host.rtsp_enabled, default=None),
                "onvif": _safe_get(lambda: host.onvif_enabled, default=None),
                "rtmp": _safe_get(lambda: host.rtmp_enabled, default=None),
            },
            "time": _safe_get(_clock, host, default=None),
            "channels": channels,
        }

    finally:
        disconnect(module, host)

    module.exit_json(changed=False, facts=facts)


if __name__ == "__main__":
    main()
