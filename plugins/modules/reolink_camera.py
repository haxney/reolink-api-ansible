#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: reolink_camera
short_description: Configure Reolink IP cameras and NVRs
version_added: "0.1.0"
description:
  - Manages configuration of Reolink IP cameras and NVR systems via the HTTP API.
  - Supports video stream settings, image adjustments, NTP configuration,
    time/date settings, IR lights, recording, and more.
  - All parameters are optional; only provided parameters are changed.
  - Each setting is compared with the camera's current value and sent only if
    it differs, so C(changed) means the camera was changed. The exceptions are
    C(spotlight), which is always sent, and C(ntp.sync_now), which is an
    action and never counts as a change.
  - Uses the C(reolink-aio) Python library (U(https://github.com/starkillerOG/reolink_aio)).
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
    default: true
  timeout:
    description: Connection timeout in seconds.
    type: int
    default: 30
  channel:
    description:
      - Channel index (0-based) to configure. Use 0 for standalone cameras.
      - For NVRs, specify the channel of the camera you want to configure.
    type: int
    default: 0
  ntp:
    description: NTP (Network Time Protocol) settings.
    type: dict
    suboptions:
      enabled:
        description: Enable NTP time synchronization.
        type: bool
      server:
        description: NTP server hostname or IP address.
        type: str
      port:
        description: NTP server port (1-65535).
        type: int
      interval:
        description: Synchronization interval in minutes (60-65535).
        type: int
      sync_now:
        description:
          - Trigger an immediate NTP synchronization after applying settings.
          - It runs on every invocation but does not by itself mark the task
            changed, since it is an action rather than a setting.
        type: bool
        default: false
  time:
    description:
      - Time and date settings, applied with a single SetTime.
      - Only fields that differ from the camera's are changed.
      - Applied before C(ntp), so that C(ntp.sync_now) sets the clock in the
        new time zone.
    type: dict
    suboptions:
      date_format:
        description: Date display format.
        type: str
        choices: ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY/MM/DD"]
      hours_24:
        description: Use 24-hour clock format.
        type: bool
      timezone_offset:
        description:
          - Standard-time offset from UTC in seconds, in Reolink's convention
            of positive values WEST of UTC (e.g. C(18000) for UTC-5).
          - With C(dst) enabled, give the standard (winter) offset; the camera
            adds C(dst.offset) during the DST period itself.
        type: int
      dst:
        description:
          - Daylight saving time rule. The camera applies it on its own, so a
            camera with a rule needs no changes at the transitions.
          - Each transition is given as the Nth C(weekday) of C(month), at a
            local time.
        type: dict
        version_added: "0.3.0"
        suboptions:
          enabled:
            description: Apply the DST rule.
            type: bool
          offset:
            description: Hours added during DST.
            type: int
          start:
            description: When DST begins.
            type: dict
            suboptions:
              month:
                description: Month, 1-12.
                type: int
              week:
                description: Which occurrence of C(weekday) in the month, 1-4, or 5 for the last.
                type: int
              weekday:
                description: Day of the week, 0-6, where 0 is Sunday.
                type: int
              hour:
                description: Hour, 0-23.
                type: int
              minute:
                description: Minute, 0-59.
                type: int
              second:
                description: Second, 0-59.
                type: int
          end:
            description: When DST ends. Same keys as C(start).
            type: dict
            suboptions:
              month:
                description: Month, 1-12.
                type: int
              week:
                description: Which occurrence of C(weekday) in the month, 1-4, or 5 for the last.
                type: int
              weekday:
                description: Day of the week, 0-6, where 0 is Sunday.
                type: int
              hour:
                description: Hour, 0-23.
                type: int
              minute:
                description: Minute, 0-59.
                type: int
              second:
                description: Second, 0-59.
                type: int
  video:
    description: Video stream encoding settings.
    type: dict
    suboptions:
      stream:
        description: Stream to configure (C(main), C(sub), or C(ext)).
        type: str
        default: main
        choices: [main, sub, ext]
      encoding:
        description: Video encoding codec.
        type: str
        choices: [h264, h265]
      bitrate:
        description:
          - Video bitrate in kbps.
          - Must be one the camera offers for the stream, where it publishes
            the list (sub streams typically 64-512).
        type: int
      frame_rate:
        description:
          - Video frame rate in fps.
          - Must be one the camera offers for the stream, where it publishes
            the list.
        type: int
  image:
    description: Image quality and appearance settings.
    type: dict
    suboptions:
      brightness:
        description: Image brightness (0-255).
        type: int
      contrast:
        description: Image contrast (0-255).
        type: int
      saturation:
        description: Image saturation (0-255).
        type: int
      hue:
        description: Image hue (0-255).
        type: int
      sharpen:
        description: Image sharpness (0-255).
        type: int
  ir_lights:
    description: Enable or disable infrared night-vision LEDs.
    type: bool
  recording:
    description: Enable or disable continuous recording to storage.
    type: bool
  audio:
    description: Enable or disable audio recording.
    type: bool
  motion_detection:
    description: Enable or disable motion detection.
    type: bool
  osd:
    description: On-screen display settings.
    type: dict
    suboptions:
      name:
        description: Camera name shown in the overlay.
        type: str
      name_position:
        description: Position of the camera name overlay (C(Upper Left), C(Top Center), C(Upper Right), C(Lower Left), C(Bottom Center), C(Lower Right)), or C(Off) to hide it.
        type: str
      date_position:
        description: Position of the date/time overlay (same values as C(name_position)), or C(Off) to hide it.
        type: str
      watermark:
        description: Enable or disable the Reolink watermark.
        type: bool
  daynight:
    description: >
      Day/night mode. C(Auto) switches automatically, C(Color) forces color,
      C(Black&White) forces monochrome.
    type: str
    choices: ["Auto", "Color", "Black&White"]
  backlight:
    description: >
      Backlight compensation mode. C(DynamicRangeControl) enables HDR/WDR,
      C(BackLightControl) enables BLC, C(Off) disables both.
    type: str
    choices: ["DynamicRangeControl", "BackLightControl", "Off"]
  flip:
    description:
      - Flip the image vertically. The Reolink app's "Flip"; the ISP's C(rotation).
      - An upside-down camera needs C(flip) and C(mirror) together, which is a
        180 degree rotation. C(flip) alone leaves the image upright but mirrored.
      - Fails on a camera that has no such setting.
    type: bool
    version_added: "0.2.0"
  mirror:
    description:
      - Mirror the image horizontally. The Reolink app's "Mirror"; the ISP's C(mirroring).
      - Fails on a camera that has no such setting.
    type: bool
    version_added: "0.2.0"
  spotlight:
    description:
      - Enable or disable the white spotlight LED (if present).
      - Always sent, so it always marks the task changed, because a
        spotlight's schedule, mode and brightness are not readable as one
        on/off state.
    type: bool
  push_notifications:
    description: Enable or disable push notifications to the Reolink app.
    type: bool
  email_notifications:
    description: Enable or disable email notifications.
    type: bool
  ftp_upload:
    description: Enable or disable FTP upload on motion.
    type: bool
  net_port:
    description:
      - Enablement of the device's network service ports.
      - Only provided sub-keys are changed. Toggling a port invalidates the
        current session; the module re-authenticates transparently.
    type: dict
    version_added: "0.2.0"
    suboptions:
      rtsp:
        description: Enable or disable the RTSP streaming port (554). Required for Frigate.
        type: bool
      onvif:
        description: Enable or disable the ONVIF port (8000).
        type: bool
      rtmp:
        description: Enable or disable the RTMP port (1935).
        type: bool
  p2p_enabled:
    description:
      - Enable or disable P2P, the UID-based relay through Reolink's servers
        that the Reolink app uses to reach the camera from outside the LAN.
      - Disabling it restarts the camera's HTTP service, so it is applied last.
    type: bool
    version_added: "0.2.0"
  auto_upgrade:
    description:
      - Enable or disable automatic firmware upgrades, for which the camera
        polls Reolink's update servers.
      - With it off, firmware is only upgraded by hand.
      - Read back after setting; the task fails if the camera did not take it.
    type: bool
    version_added: "0.3.0"
  upnp:
    description:
      - Enable or disable UPnP, by which the camera asks the router to open
        inbound ports to it.
      - Read back after setting; the task fails if the camera did not take it.
    type: bool
    version_added: "0.3.0"
  ddns:
    description:
      - Enable or disable dynamic DNS, by which the camera registers its
        public address with a DDNS provider. Only the switch is changed; the
        provider settings are left as they are.
      - Read back after setting; the task fails if the camera did not take it.
    type: bool
    version_added: "0.3.0"
notes:
  - The camera reaches outside servers through P2P, push notifications,
    automatic firmware upgrades, UPnP, DDNS, email, FTP and NTP. All but NTP
    can be switched off here. Turning these off does not stop a camera from
    trying; blocking its internet access at the network is the only guarantee.
"""

EXAMPLES = r"""
- name: Set NTP server
  haxney.reolink.reolink_camera:
    hostname: 192.168.1.100
    password: mypassword
    ntp:
      enabled: true
      server: pool.ntp.org

- name: Configure main stream encoding
  haxney.reolink.reolink_camera:
    hostname: 192.168.1.100
    password: mypassword
    video:
      stream: main
      encoding: h265
      bitrate: 2048
      frame_rate: 15

- name: Disable IR lights on NVR channel 3
  haxney.reolink.reolink_camera:
    hostname: 192.168.1.50
    password: secretpass
    channel: 3
    ir_lights: false

- name: US Eastern time, following DST on its own
  haxney.reolink.reolink_camera:
    hostname: 192.168.1.100
    password: mypassword
    time:
      timezone_offset: 18000  # EST, UTC-5
      dst:
        enabled: true
        offset: 1
        start: {month: 3, week: 2, weekday: 0, hour: 2, minute: 0, second: 0}
        end: {month: 11, week: 1, weekday: 0, hour: 2, minute: 0, second: 0}
    ntp:
      enabled: true
      server: pool.ntp.org
      sync_now: true

- name: Flip and mirror a ceiling-mounted camera
  haxney.reolink.reolink_camera:
    hostname: 192.168.1.100
    password: mypassword
    flip: true
    mirror: true
"""

RETURN = r"""
changed:
  description: Whether any settings were actually changed on the device.
  type: bool
  returned: always
camera_info:
  description: Basic information about the connected camera or NVR.
  type: dict
  returned: always
  contains:
    model:
      description: Camera/NVR model name.
      type: str
    is_nvr:
      description: True if the device is an NVR.
      type: bool
    num_channels:
      description: Number of channels (cameras).
      type: int
    mac_address:
      description: MAC address of the device.
      type: str
    firmware_version:
      description: Current firmware version.
      type: str
changes:
  description: List of settings that were changed.
  type: list
  elements: str
  returned: always
"""

import traceback

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.haxney.reolink.plugins.module_utils.reolink_utils import (
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        HAS_REOLINK,
        REOLINK_IMP_ERR,
        ISP_ORIENTATION_KEYS,
        get_switch,
        push_enabled,
        switch_target,
        stream_encoding,
    )
except ImportError:
    from ..module_utils.reolink_utils import (  # type: ignore[no-redef]
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        HAS_REOLINK,
        REOLINK_IMP_ERR,
        ISP_ORIENTATION_KEYS,
        get_switch,
        push_enabled,
        switch_target,
        stream_encoding,
    )


def _read(fn):
    """The value fn() reads from reolink-aio's cache, or None if it cannot.

    None never equals a wanted value, so an unreadable setting is sent rather
    than skipped.
    """
    try:
        return fn()
    except Exception:
        return None


def _apply_ntp(module, host, ntp_params, check_mode, changes):
    """Set NTP, sending only the fields that differ.

    sync_now syncs on every run but does not by itself mark the task changed:
    it is an action, and counting it would make every run report a change.
    """
    if ntp_params is None:
        return
    wanted = {
        "enable": ntp_params.get("enabled"),
        "server": ntp_params.get("server"),
        "port": ntp_params.get("port"),
        "interval": ntp_params.get("interval"),
    }
    wanted = {k: v for k, v in wanted.items() if v is not None}

    if wanted:
        try:
            run_async(host.get_state("GetNtp"))
            current = host._ntp_settings["Ntp"]
        except Exception as exc:
            module.fail_json(msg=f"Could not read NTP settings: {exc}")
        kwargs = {
            k: v for k, v in wanted.items()
            if (bool(current.get(k)) if k == "enable" else current.get(k)) != v
        }
        if kwargs:
            changes.append("ntp")
            if not check_mode:
                try:
                    run_async(host.set_ntp(**kwargs))
                except Exception as exc:
                    module.fail_json(msg=f"Failed to set NTP settings: {exc}")

    if ntp_params.get("sync_now") and not check_mode:
        try:
            run_async(host.sync_ntp())
        except Exception as exc:
            module.warn(f"NTP sync_now failed: {exc}")


# Reolink names the two ends of the DST period with flat, prefixed keys
# (startMon ... endSec). Option name -> (key suffix, lowest, highest).
_DST_TRANSITION_FIELDS = {
    "month": ("Mon", 1, 12),
    "week": ("Week", 1, 5),
    "weekday": ("Weekday", 0, 6),
    "hour": ("Hour", 0, 23),
    "minute": ("Min", 0, 59),
    "second": ("Sec", 0, 59),
}


def _desired_time_fields(module, time_params):
    """Translate the time option into the Time and Dst blocks of SetTime.

    Returns the two blocks holding only the fields the caller set.
    """
    time_fields = {}
    if time_params.get("date_format") is not None:
        time_fields["timeFmt"] = time_params["date_format"]
    if time_params.get("hours_24") is not None:
        time_fields["hourFmt"] = 0 if time_params["hours_24"] else 1
    offset = time_params.get("timezone_offset")
    if offset is not None:
        # The range reolink-aio's set_time() enforces.
        if not -43200 <= offset <= 50400:
            module.fail_json(msg=f"timezone_offset {offset} is outside -43200..50400")
        time_fields["timeZone"] = offset

    dst_fields = {}
    dst = time_params.get("dst") or {}
    if dst.get("enabled") is not None:
        dst_fields["enable"] = 1 if dst["enabled"] else 0
    if dst.get("offset") is not None:
        dst_fields["offset"] = dst["offset"]
    for edge in ("start", "end"):
        transition = dst.get(edge) or {}
        for name, (suffix, lowest, highest) in _DST_TRANSITION_FIELDS.items():
            value = transition.get(name)
            if value is None:
                continue
            if not lowest <= value <= highest:
                module.fail_json(msg=f"dst.{edge}.{name} {value} is outside {lowest}..{highest}")
            dst_fields[edge + suffix] = value

    return time_fields, dst_fields


def _apply_time(module, host, time_params, check_mode, changes):
    """Set display formats, time zone and DST rule with one SetTime.

    reolink-aio's set_time() has no DST support, so the GetTime body is edited
    and sent back whole, as set_time() itself does. Only fields that differ
    count as a change, and nothing is sent when none do.
    """
    if time_params is None:
        return
    time_fields, dst_fields = _desired_time_fields(module, time_params)
    if not time_fields and not dst_fields:
        return

    try:
        run_async(host.get_state("GetTime"))
    except Exception as exc:
        module.fail_json(msg=f"Failed to read time settings: {exc}")
    current = host._time_settings
    if not current or "Time" not in current:
        module.fail_json(msg="Camera returned no time settings")
    if dst_fields and "Dst" not in current:
        module.fail_json(msg="Camera has no DST settings")

    time_fields = {k: v for k, v in time_fields.items() if current["Time"].get(k) != v}
    dst_fields = {k: v for k, v in dst_fields.items() if current["Dst"].get(k) != v}
    if not time_fields and not dst_fields:
        return

    changes.append("time")
    if check_mode:
        return

    current["Time"].update(time_fields)
    if dst_fields:
        current["Dst"].update(dst_fields)
    body = [{"cmd": "SetTime", "action": 0, "param": current}]
    try:
        run_async(host.send_setting(body))
    except Exception as exc:
        module.fail_json(msg=f"Failed to set time settings: {exc}")


def _apply_video(module, host, channel, video_params, check_mode, changes):
    """Set encoding, bitrate and frame rate, sending only what differs.

    All three are read before anything is sent: set_encoding() goes over
    Baichuan and leaves reolink-aio's cache stale.
    """
    if video_params is None:
        return
    stream = video_params.get("stream", "main")

    # reolink-aio sends any bitrate or frame rate, and a camera may not reject
    # one it cannot do (the sub stream tops out at 512 kbps on all three
    # models). Refuse those here, wherever the camera publishes its lists.
    for option, offered in (
        ("bitrate", _read(lambda: host.bit_rate_list(channel, stream))),
        ("frame_rate", _read(lambda: host.frame_rate_list(channel, stream))),
    ):
        value = video_params.get(option)
        if value is not None and offered and value not in offered:
            module.fail_json(msg=f"video.{option} {value} is not one the camera offers for its {stream} stream: {offered}")

    enc = _read(lambda: host._enc_settings[channel][f"{stream}Stream"]) or {}
    settings = (
        # (option, label, current value, setter)
        ("encoding", "video_encoding",
         video_params.get("encoding") and _read(lambda: stream_encoding(host, channel, stream)),
         host.set_encoding),
        ("bitrate", "video_bitrate", enc.get("bitRate"), host.set_bit_rate),
        ("frame_rate", "video_frame_rate", enc.get("frameRate"), host.set_frame_rate),
    )
    for option, label, current, setter in settings:
        value = video_params.get(option)
        if value is None or current == value:
            continue
        changes.append(label)
        if check_mode:
            continue
        try:
            run_async(setter(channel, value, stream))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set video {option}: {exc}")


# image option -> (set_image() keyword, key in the GetImage block)
_IMAGE_FIELDS = {
    "brightness": "bright",
    "contrast": "contrast",
    "saturation": "saturation",
    "hue": "hue",
    "sharpen": "sharpen",
}


def _apply_image(module, host, channel, image_params, check_mode, changes):
    """Set image adjustments, sending only the ones that differ."""
    if image_params is None:
        return
    current = _read(lambda: host._image_settings[channel]["Image"]) or {}
    kwargs = {}
    for option, key in _IMAGE_FIELDS.items():
        value = image_params.get(option)
        # The Baichuan fallback stores some of these as strings.
        if value is not None and _read(lambda key=key: int(current[key])) != value:
            kwargs[key] = value

    if not kwargs:
        return

    changes.append("image")
    if not check_mode:
        try:
            run_async(host.set_image(channel, **kwargs))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set image settings: {exc}")


def _apply_osd(module, host, channel, osd_params, check_mode, changes):
    """Set the on-screen name, positions and watermark, if any differ.

    reolink-aio has no setter for the name, so the GetOsd block is edited and
    sent back whole as a raw SetOsd.
    """
    if osd_params is None:
        return
    if not any(osd_params.get(k) is not None for k in ("name", "name_position", "date_position", "watermark")):
        return

    try:
        run_async(host.get_state("GetOsd"))
    except Exception as exc:
        module.fail_json(msg=f"Could not read OSD settings: {exc}")
    if not host._osd_settings.get(channel):
        module.fail_json(msg=f"OSD not available on channel {channel}")

    osd = host._osd_settings[channel]["Osd"]
    wanted = {}  # (block, key) -> value
    if osd_params.get("name") is not None:
        wanted[("osdChannel", "name")] = osd_params["name"]
    for option, block in (("name_position", "osdChannel"), ("date_position", "osdTime")):
        pos = osd_params.get(option)
        if pos == "Off":
            wanted[(block, "enable")] = 0
        elif pos is not None:
            wanted[(block, "enable")] = 1
            wanted[(block, "pos")] = pos
    if osd_params.get("watermark") is not None and "watermark" in osd:
        wanted[(None, "watermark")] = 1 if osd_params["watermark"] else 0

    def _cell(block, key):
        return osd if block is None else osd[block]

    differing = {bk: v for bk, v in wanted.items() if _cell(*bk).get(bk[1]) != v}
    if not differing:
        return

    changes.append("osd")
    if check_mode:
        return

    for (block, key), value in differing.items():
        _cell(block, key)[key] = value
    try:
        run_async(host.send_setting([{"cmd": "SetOsd", "action": 0, "param": host._osd_settings[channel]}]))
    except Exception as exc:
        module.fail_json(msg=f"Failed to set OSD settings: {exc}")


def _apply_flip_mirror(module, host, channel, flip, mirror, check_mode, changes):
    """Set image flip (vertical) and mirror (horizontal) via the ISP settings.

    reolink-aio has no setter for these, so we edit the raw Isp param — the same
    block set_daynight() mutates — and send a single SetIsp. Both are handled
    together so we fetch and send once, avoiding two ISP restarts.
    """
    requested = {name: value for name, value in (("flip", flip), ("mirror", mirror)) if value is not None}
    if not requested:
        return

    # Fetch current ISP state so we can compare (idempotency) and send a
    # complete SetIsp body.
    try:
        run_async(host.get_state(cmd="GetIsp", ch=channel))
    except Exception as exc:
        module.fail_json(msg=f"Could not retrieve ISP settings: {exc}")

    isp = host._isp_settings.get(channel)
    if not isp:
        module.fail_json(msg=f"ISP not available on channel {channel}, cannot set {' or '.join(requested)}")

    # A requested setting the camera lacks is an error, not a warning: 0.2.0
    # skipped these with a warning, and so never set either one on any camera.
    desired = {}
    for name, value in requested.items():
        key = ISP_ORIENTATION_KEYS[name]
        if key not in isp:
            module.fail_json(msg=f"{name} is not supported on channel {channel}: its ISP settings have no '{key}'")
        if bool(isp[key]) != value:
            desired[key] = 1 if value else 0

    if not desired:
        return

    changes.append("flip_mirror")
    if check_mode:
        return

    isp.update(desired)
    body = [{"cmd": "SetIsp", "action": 0, "param": {"Isp": isp}}]
    try:
        run_async(host.send_setting(body))
    except Exception as exc:
        module.fail_json(msg=f"Failed to set flip/mirror settings: {exc}")


def _apply_compared(module, label, value, current, apply, check_mode, changes):
    """Run apply() unless the camera already has value.

    current is what the camera reports (None if unknown, which never matches);
    apply is a no-argument callable returning the setter's coroutine.
    """
    if value is None or current == value:
        return
    changes.append(label)
    if check_mode:
        return
    try:
        run_async(apply())
    except Exception as exc:
        module.fail_json(msg=f"Failed to set {label}: {exc}")


def _apply_channel_or_device(module, host, channel, value, label, capability, read, write, get_cmd, check_mode, changes):
    """Switch a setting per channel where the camera has that, otherwise
    device-wide, and read it back after setting.

    Email, FTP and recording come in per-channel and device-wide shapes.
    reolink-aio's setters raise for a channel the camera only switches
    device-wide (and its device-wide legacy path silently does nothing when
    no channel qualifies), so the target is chosen here.
    """
    if value is None:
        return
    try:
        target = switch_target(host, channel, capability)
    except Exception as exc:
        module.fail_json(msg=f"{label}: {exc}")
    if _read(lambda: read(target)) == value:
        return

    changes.append(label)
    if check_mode:
        return
    try:
        run_async(write(target, value))
        run_async(host.get_state(cmd=get_cmd, ch=channel))
        taken = read(target)
    except Exception as exc:
        module.fail_json(msg=f"Failed to set {label}: {exc}")
    if taken != value:
        module.fail_json(msg=f"{label}: the camera still reports {taken}")


def _apply_push(module, host, channel, value, check_mode, changes):
    """Switch push notifications for the channel, or device-wide on cameras
    that only have a device-wide switch. Read back after setting."""
    if value is None:
        return
    if host.supported(channel, "push"):
        target = channel
    elif host.supported(None, "push"):
        target = None
    else:
        module.fail_json(msg="push_notifications is not supported by this camera")
    try:
        if push_enabled(host, channel) == value:
            return
    except Exception as exc:
        module.fail_json(msg=f"Could not read push_notifications: {exc}")

    changes.append("push_notifications")
    if check_mode:
        return

    try:
        run_async(host.set_push(target, value))
        taken = push_enabled(host, channel)
    except Exception as exc:
        module.fail_json(msg=f"Failed to set push_notifications: {exc}")
    if taken != value:
        module.fail_json(msg=f"push_notifications: the camera still reports {taken}")


# Host-level settings that are a single "enable" flag reolink-aio has no
# setter for. Option name -> the API's block name, which also names the
# commands: Get<block> and Set<block>.
_HOST_SWITCHES = {
    "auto_upgrade": "AutoUpgrade",
    "upnp": "Upnp",
    "ddns": "Ddns",
}


def _apply_host_switch(module, host, option, value, check_mode, changes):
    """Set one of _HOST_SWITCHES with a raw Set, then read it back.

    The block is sent back whole with only "enable" changed, so the rest of
    it (a DDNS provider's settings, say) is kept.
    """
    if value is None:
        return
    block = _HOST_SWITCHES[option]
    try:
        current = get_switch(host, block)
    except Exception as exc:
        module.fail_json(msg=f"Could not read {option} (Get{block}): {exc}")
    if bool(current["enable"]) == value:
        return

    changes.append(option)
    if check_mode:
        return

    current["enable"] = 1 if value else 0
    try:
        run_async(host.send_setting([{"cmd": f"Set{block}", "action": 0, "param": {block: current}}]))
        taken = bool(get_switch(host, block)["enable"])
    except Exception as exc:
        module.fail_json(msg=f"Failed to set {option} (Set{block}): {exc}")
    if taken != value:
        module.fail_json(msg=f"{option}: Set{block} was accepted but the camera still reports enable={int(taken)}")


def _apply_p2p(module, host, value, check_mode, changes):
    """Disable or enable P2P (UID cloud connectivity) via raw API call."""
    if value is None:
        return
    # Check current state to avoid unnecessary SetP2p, which restarts the camera's HTTP service.
    try:
        async def _get_p2p():
            data = await host.send([{"cmd": "GetP2p", "action": 0, "param": {}}], expected_response_type="json")
            return bool(data[0]["value"]["P2p"]["enable"])
        current = run_async(_get_p2p())
        if current == value:
            return
    except Exception:
        pass  # If we can't check, proceed with setting
    changes.append("p2p_enabled")
    if not check_mode:
        body = [{"cmd": "SetP2p", "action": 0, "param": {"P2p": {"enable": 1 if value else 0}}}]
        try:
            run_async(host.send_setting(body))
        except Exception as exc:
            # A 502 response to SetP2p is expected: the camera restarts its HTTP
            # service immediately after processing the command. The command was
            # accepted; the wait_for task that follows will wait for recovery.
            if "502" not in str(exc) and "Bad Gateway" not in str(exc):
                module.fail_json(msg=f"Failed to set p2p_enabled: {exc}")


def _apply_net_port(module, host, net_port_params, check_mode, changes):
    """Enable/disable the RTSP, ONVIF, and RTMP service ports (host-level)."""
    if net_port_params is None:
        return

    desired = {port: net_port_params.get(port) for port in ("rtsp", "onvif", "rtmp")}
    if all(v is None for v in desired.values()):
        return

    # Fetch current port state so we only toggle what actually differs.
    try:
        run_async(host.get_state("GetNetPort"))
    except Exception as exc:
        module.warn(f"Could not retrieve network port settings: {exc}")

    current = {
        "rtsp": host.rtsp_enabled,
        "onvif": host.onvif_enabled,
        "rtmp": host.rtmp_enabled,
    }

    kwargs = {}
    for port, want in desired.items():
        if want is not None and current.get(port) != want:
            kwargs[f"enable_{port}"] = want

    if not kwargs:
        return

    changes.append("net_port")
    if not check_mode:
        try:
            # set_net_port() invalidates the session token; reolink-aio
            # re-authenticates automatically on the next API call.
            run_async(host.set_net_port(**kwargs))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set network port settings: {exc}")


def main():
    ntp_spec = dict(
        enabled=dict(type="bool"),
        server=dict(type="str"),
        port=dict(type="int"),
        interval=dict(type="int"),
        sync_now=dict(type="bool", default=False),
    )
    dst_transition_spec = dict(
        month=dict(type="int"),
        week=dict(type="int"),
        weekday=dict(type="int"),
        hour=dict(type="int"),
        minute=dict(type="int"),
        second=dict(type="int"),
    )
    dst_spec = dict(
        enabled=dict(type="bool"),
        offset=dict(type="int"),
        start=dict(type="dict", options=dst_transition_spec),
        end=dict(type="dict", options=dst_transition_spec),
    )
    time_spec = dict(
        date_format=dict(type="str", choices=["DD/MM/YYYY", "MM/DD/YYYY", "YYYY/MM/DD"]),
        hours_24=dict(type="bool"),
        timezone_offset=dict(type="int"),
        dst=dict(type="dict", options=dst_spec),
    )
    video_spec = dict(
        stream=dict(type="str", default="main", choices=["main", "sub", "ext"]),
        encoding=dict(type="str", choices=["h264", "h265"]),
        bitrate=dict(type="int"),
        frame_rate=dict(type="int"),
    )
    image_spec = dict(
        brightness=dict(type="int"),
        contrast=dict(type="int"),
        saturation=dict(type="int"),
        hue=dict(type="int"),
        sharpen=dict(type="int"),
    )
    osd_spec = dict(
        name=dict(type="str"),
        name_position=dict(type="str"),
        date_position=dict(type="str"),
        watermark=dict(type="bool"),
    )
    net_port_spec = dict(
        rtsp=dict(type="bool"),
        onvif=dict(type="bool"),
        rtmp=dict(type="bool"),
    )

    module = AnsibleModule(
        argument_spec=dict(
            hostname=dict(type="str", required=True),
            username=dict(type="str", default="admin"),
            password=dict(type="str", required=True, no_log=True),
            port=dict(type="int"),
            use_https=dict(type="bool", default=True),
            timeout=dict(type="int", default=30),
            channel=dict(type="int", default=0),
            ntp=dict(type="dict", options=ntp_spec),
            time=dict(type="dict", options=time_spec),
            video=dict(type="dict", options=video_spec),
            image=dict(type="dict", options=image_spec),
            ir_lights=dict(type="bool"),
            recording=dict(type="bool"),
            audio=dict(type="bool"),
            motion_detection=dict(type="bool"),
            osd=dict(type="dict", options=osd_spec),
            net_port=dict(type="dict", options=net_port_spec),
            daynight=dict(type="str", choices=["Auto", "Color", "Black&White"]),
            backlight=dict(type="str", choices=["DynamicRangeControl", "BackLightControl", "Off"]),
            flip=dict(type="bool"),
            mirror=dict(type="bool"),
            spotlight=dict(type="bool"),
            push_notifications=dict(type="bool"),
            email_notifications=dict(type="bool"),
            ftp_upload=dict(type="bool"),
            p2p_enabled=dict(type="bool"),
            auto_upgrade=dict(type="bool"),
            upnp=dict(type="bool"),
            ddns=dict(type="bool"),
        ),
        supports_check_mode=True,
    )

    check_reolink_import(module)

    check_mode = module.check_mode
    channel = module.params["channel"]
    changes = []

    host = connect(module)
    try:
        # Fetch per-channel state for video/image comparisons
        try:
            run_async(host.get_states())
        except Exception as exc:
            module.warn(f"Could not retrieve current camera states: {exc}")

        # Time zone and DST before NTP, so that ntp.sync_now sets the clock
        # in the new zone.
        _apply_time(module, host, module.params.get("time"), check_mode, changes)
        _apply_ntp(module, host, module.params.get("ntp"), check_mode, changes)
        _apply_video(module, host, channel, module.params.get("video"), check_mode, changes)
        _apply_image(module, host, channel, module.params.get("image"), check_mode, changes)
        _apply_osd(module, host, channel, module.params.get("osd"), check_mode, changes)

        params = module.params
        # ir_lights true means "Auto"; an "On" state reads as unknown, so it
        # is set.
        _apply_compared(
            module, "ir_lights", params.get("ir_lights"),
            _read(lambda: {"Auto": True, "Off": False}.get(host._ir_settings[channel]["state"])),
            lambda: host.set_ir_lights(channel, params["ir_lights"]), check_mode, changes)
        _apply_compared(
            module, "audio", params.get("audio"), _read(lambda: host.audio_record(channel)),
            lambda: host.set_audio(channel, params["audio"]), check_mode, changes)
        _apply_compared(
            module, "motion_detection", params.get("motion_detection"),
            _read(lambda: bool(host._md_alarm_settings[channel]["enable"])),
            lambda: host.set_motion_detection(channel, params["motion_detection"]), check_mode, changes)
        # A spotlight is more than on/off (schedule, mode, brightness), and
        # its state alone cannot say whether those match, so it is always sent.
        _apply_compared(
            module, "spotlight", params.get("spotlight"), None,
            lambda: host.set_spotlight(channel, params["spotlight"]), check_mode, changes)
        _apply_push(module, host, channel, params.get("push_notifications"), check_mode, changes)
        for option, capability, read, write, get_cmd in (
            ("recording", "recording", host.recording_enabled, host.set_recording, "GetRec"),
            ("email_notifications", "email", host.email_enabled, host.set_email, "GetEmail"),
            ("ftp_upload", "ftp", host.ftp_enabled, host.set_ftp, "GetFtp"),
        ):
            _apply_channel_or_device(
                module, host, channel, params.get(option), option, capability,
                read, write, get_cmd, check_mode, changes)
        for option in _HOST_SWITCHES:
            _apply_host_switch(module, host, option, module.params.get(option), check_mode, changes)

        _apply_compared(
            module, "daynight", params.get("daynight"), _read(lambda: host.daynight_state(channel)),
            lambda: host.set_daynight(channel, params["daynight"]), check_mode, changes)
        _apply_compared(
            module, "backlight", params.get("backlight"), _read(lambda: host.backlight_state(channel)),
            lambda: host.set_backlight(channel, params["backlight"]), check_mode, changes)

        _apply_flip_mirror(
            module, host, channel,
            module.params.get("flip"), module.params.get("mirror"),
            check_mode, changes,
        )

        # Enable/disable service ports (RTSP etc). Done before P2P because it
        # only invalidates the session token (reolink-aio re-logins), whereas
        # P2P can tear down the HTTP service entirely.
        _apply_net_port(module, host, module.params.get("net_port"), check_mode, changes)

        # Apply P2P last — disabling it can restart the camera's HTTP service,
        # which would break any API calls that follow.
        _apply_p2p(module, host, module.params.get("p2p_enabled"), check_mode, changes)

        camera_info = {
            "model": host.camera_model(channel) if host.num_channels > 0 else host.nvr_name,
            "is_nvr": host.is_nvr,
            "num_channels": host.num_channels,
            "mac_address": host.mac_address,
            "firmware_version": str(host.sw_version),
        }

    finally:
        disconnect(module, host)

    module.exit_json(
        changed=bool(changes),
        camera_info=camera_info,
        changes=changes,
    )


if __name__ == "__main__":
    main()
