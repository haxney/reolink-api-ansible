#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: reolink_camera
short_description: Configure Reolink IP cameras and NVRs
version_added: "1.0.0"
description:
  - Manages configuration of Reolink IP cameras and NVR systems via the HTTP API.
  - Supports video stream settings, image adjustments, NTP configuration,
    time/date settings, IR lights, recording, and more.
  - All parameters are optional; only provided parameters are changed.
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
        description: Trigger an immediate NTP synchronization after applying settings.
        type: bool
        default: false
  time:
    description: Time and date settings.
    type: dict
    suboptions:
      date_format:
        description: Date display format (e.g. C(DD/MM/YYYY), C(MM/DD/YYYY), C(YYYY/MM/DD)).
        type: str
      hours_24:
        description: Use 24-hour clock format.
        type: bool
      timezone_offset:
        description: Timezone offset from UTC in seconds (e.g. -18000 for UTC-5).
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
        description: Video bitrate in kbps.
        type: int
      frame_rate:
        description: Video frame rate in fps.
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
      name_position:
        description: Position of the camera name overlay (C(Upper Left), C(Top Center), C(Upper Right), or C(0) to disable).
        type: str
      date_position:
        description: Position of the date/time overlay (C(Upper Left), C(Top Center), C(Upper Right), or C(0) to disable).
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
  spotlight:
    description: Enable or disable the white spotlight LED (if present).
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
    )
except ImportError:
    from ..module_utils.reolink_utils import (  # type: ignore[no-redef]
        check_reolink_import,
        connect,
        disconnect,
        run_async,
        HAS_REOLINK,
        REOLINK_IMP_ERR,
    )


def _apply_ntp(module, host, ntp_params, check_mode, changes):
    if ntp_params is None:
        return
    kwargs = {}
    if ntp_params.get("enabled") is not None:
        kwargs["enable"] = ntp_params["enabled"]
    if ntp_params.get("server") is not None:
        kwargs["server"] = ntp_params["server"]
    if ntp_params.get("port") is not None:
        kwargs["port"] = ntp_params["port"]
    if ntp_params.get("interval") is not None:
        kwargs["interval"] = ntp_params["interval"]

    if not kwargs:
        return

    changes.append("ntp")
    if not check_mode:
        try:
            run_async(host.set_ntp(**kwargs))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set NTP settings: {exc}")

    if ntp_params.get("sync_now") and not check_mode:
        try:
            run_async(host.sync_ntp())
            changes.append("ntp_sync_now")
        except Exception as exc:
            module.warn(f"NTP sync_now failed: {exc}")


def _apply_time(module, host, time_params, check_mode, changes):
    if time_params is None:
        return
    kwargs = {}
    if time_params.get("date_format") is not None:
        kwargs["dateFmt"] = time_params["date_format"]
    if time_params.get("hours_24") is not None:
        kwargs["hours24"] = time_params["hours_24"]
    if time_params.get("timezone_offset") is not None:
        kwargs["tzOffset"] = time_params["timezone_offset"]

    if not kwargs:
        return

    changes.append("time")
    if not check_mode:
        try:
            run_async(host.set_time(**kwargs))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set time settings: {exc}")


def _apply_video(module, host, channel, video_params, check_mode, changes):
    if video_params is None:
        return
    stream = video_params.get("stream", "main")

    if video_params.get("encoding") is not None:
        changes.append("video_encoding")
        if not check_mode:
            try:
                run_async(host.set_encoding(channel, video_params["encoding"], stream))
            except Exception as exc:
                module.fail_json(msg=f"Failed to set video encoding: {exc}")

    if video_params.get("bitrate") is not None:
        changes.append("video_bitrate")
        if not check_mode:
            try:
                run_async(host.set_bit_rate(channel, video_params["bitrate"], stream))
            except Exception as exc:
                module.fail_json(msg=f"Failed to set video bitrate: {exc}")

    if video_params.get("frame_rate") is not None:
        changes.append("video_frame_rate")
        if not check_mode:
            try:
                run_async(host.set_frame_rate(channel, video_params["frame_rate"], stream))
            except Exception as exc:
                module.fail_json(msg=f"Failed to set video frame rate: {exc}")


def _apply_image(module, host, channel, image_params, check_mode, changes):
    if image_params is None:
        return
    kwargs = {}
    if image_params.get("brightness") is not None:
        kwargs["bright"] = image_params["brightness"]
    if image_params.get("contrast") is not None:
        kwargs["contrast"] = image_params["contrast"]
    if image_params.get("saturation") is not None:
        kwargs["saturation"] = image_params["saturation"]
    if image_params.get("hue") is not None:
        kwargs["hue"] = image_params["hue"]
    if image_params.get("sharpen") is not None:
        kwargs["sharpen"] = image_params["sharpen"]

    if not kwargs:
        return

    changes.append("image")
    if not check_mode:
        try:
            run_async(host.set_image(channel, **kwargs))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set image settings: {exc}")


def _apply_osd(module, host, channel, osd_params, check_mode, changes):
    if osd_params is None:
        return
    kwargs = {}
    if osd_params.get("name_position") is not None:
        kwargs["namePos"] = osd_params["name_position"]
    if osd_params.get("date_position") is not None:
        kwargs["datePos"] = osd_params["date_position"]
    if osd_params.get("watermark") is not None:
        kwargs["enableWaterMark"] = osd_params["watermark"]

    if not kwargs:
        return

    changes.append("osd")
    if not check_mode:
        try:
            run_async(host.set_osd(channel, **kwargs))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set OSD settings: {exc}")


def _apply_bool_setting(module, host, channel, value, setter_name, label, check_mode, changes):
    """Generic helper for boolean channel settings."""
    if value is None:
        return
    changes.append(label)
    if not check_mode:
        setter = getattr(host, setter_name)
        try:
            run_async(setter(channel, value))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set {label}: {exc}")


def _apply_bool_setting_no_channel(module, host, value, setter_name, label, check_mode, changes):
    """Generic helper for boolean host-level settings."""
    if value is None:
        return
    changes.append(label)
    if not check_mode:
        setter = getattr(host, setter_name)
        try:
            run_async(setter(value))
        except Exception as exc:
            module.fail_json(msg=f"Failed to set {label}: {exc}")


def main():
    ntp_spec = dict(
        enabled=dict(type="bool"),
        server=dict(type="str"),
        port=dict(type="int"),
        interval=dict(type="int"),
        sync_now=dict(type="bool", default=False),
    )
    time_spec = dict(
        date_format=dict(type="str"),
        hours_24=dict(type="bool"),
        timezone_offset=dict(type="int"),
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
        name_position=dict(type="str"),
        date_position=dict(type="str"),
        watermark=dict(type="bool"),
    )

    module = AnsibleModule(
        argument_spec=dict(
            hostname=dict(type="str", required=True),
            username=dict(type="str", default="admin"),
            password=dict(type="str", required=True, no_log=True),
            port=dict(type="int"),
            use_https=dict(type="bool"),
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
            daynight=dict(type="str", choices=["Auto", "Color", "Black&White"]),
            backlight=dict(type="str", choices=["DynamicRangeControl", "BackLightControl", "Off"]),
            spotlight=dict(type="bool"),
            push_notifications=dict(type="bool"),
            email_notifications=dict(type="bool"),
            ftp_upload=dict(type="bool"),
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

        _apply_ntp(module, host, module.params.get("ntp"), check_mode, changes)
        _apply_time(module, host, module.params.get("time"), check_mode, changes)
        _apply_video(module, host, channel, module.params.get("video"), check_mode, changes)
        _apply_image(module, host, channel, module.params.get("image"), check_mode, changes)
        _apply_osd(module, host, channel, module.params.get("osd"), check_mode, changes)

        _apply_bool_setting(module, host, channel, module.params.get("ir_lights"), "set_ir_lights", "ir_lights", check_mode, changes)
        _apply_bool_setting(module, host, channel, module.params.get("recording"), "set_recording", "recording", check_mode, changes)
        _apply_bool_setting(module, host, channel, module.params.get("audio"), "set_audio", "audio", check_mode, changes)
        _apply_bool_setting(module, host, channel, module.params.get("motion_detection"), "set_motion_detection", "motion_detection", check_mode, changes)
        _apply_bool_setting(module, host, channel, module.params.get("spotlight"), "set_spotlight", "spotlight", check_mode, changes)
        _apply_bool_setting(module, host, channel, module.params.get("push_notifications"), "set_push", "push_notifications", check_mode, changes)
        _apply_bool_setting(module, host, channel, module.params.get("email_notifications"), "set_email", "email_notifications", check_mode, changes)
        _apply_bool_setting(module, host, channel, module.params.get("ftp_upload"), "set_ftp", "ftp_upload", check_mode, changes)

        if module.params.get("daynight") is not None:
            changes.append("daynight")
            if not check_mode:
                try:
                    run_async(host.set_daynight(channel, module.params["daynight"]))
                except Exception as exc:
                    module.fail_json(msg=f"Failed to set day/night mode: {exc}")

        if module.params.get("backlight") is not None:
            changes.append("backlight")
            if not check_mode:
                try:
                    run_async(host.set_backlight(channel, module.params["backlight"]))
                except Exception as exc:
                    module.fail_json(msg=f"Failed to set backlight mode: {exc}")

        camera_info = {
            "model": host.camera_model(channel) if host.num_channel > 0 else host.nvr_name,
            "is_nvr": host.is_nvr,
            "num_channels": host.num_channel,
            "mac_address": host.mac_address,
            "firmware_version": str(host.firmware_version),
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
