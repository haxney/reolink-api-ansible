# haxney.reolink — Ansible Collection for Reolink Cameras

Manage Reolink IP cameras and NVR systems with Ansible. Configure video
settings, NTP servers, user passwords, image quality, recording, IR lights, and
more — all idempotently from a playbook.

Built on top of the officially-authorized
[reolink-aio](https://github.com/starkillerOG/reolink_aio) Python library.

---

## Modules

| Module | Description |
|--------|-------------|
| [`reolink_camera`](docs/reolink_camera.md) | Configure camera settings (NTP, video, image, recording, IR, etc.) |
| [`reolink_user`](docs/reolink_user.md) | Manage user accounts and change passwords |
| [`reolink_facts`](docs/reolink_facts.md) | Gather device facts and current settings |

---

## Requirements

- Ansible 2.14+
- Python 3.11+ (on the Ansible controller)
- [`reolink-aio`](https://pypi.org/project/reolink-aio/) ≥ 0.9.0

Install the Python dependencies on the controller:

```bash
pip install haxney-reolink          # installs reolink-aio and its deps
# or, directly from source:
pip install .
# with dev/test extras:
pip install ".[dev]"
```

---

## Installation

### From Ansible Galaxy (once published)

```bash
ansible-galaxy collection install haxney.reolink
```

### From source

```bash
git clone https://github.com/haxney/reolink-api-ansible.git
cd reolink-api-ansible
ansible-galaxy collection build
ansible-galaxy collection install haxney-reolink-*.tar.gz
```

---

## Quick Start

### 1. Secure the admin password

Always change the default password before connecting a camera to your network.

```yaml
- name: Harden Reolink camera
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Change admin password
      haxney.reolink.reolink_user:
        hostname: 192.168.1.100
        username: admin
        password: "{{ old_password }}"
        new_password: "{{ new_password }}"
```

### 2. Configure NTP

```yaml
    - name: Set NTP server
      haxney.reolink.reolink_camera:
        hostname: 192.168.1.100
        password: "{{ admin_password }}"
        ntp:
          enabled: true
          server: pool.ntp.org
          port: 123
          interval: 1440   # sync every 24 hours
          sync_now: true
```

### 3. Configure video encoding

```yaml
    - name: Use H.265 on the main stream
      haxney.reolink.reolink_camera:
        hostname: 192.168.1.100
        password: "{{ admin_password }}"
        video:
          stream: main
          encoding: h265
          bitrate: 2048
          frame_rate: 15
```

### 4. Gather facts

```yaml
    - name: Gather camera facts
      haxney.reolink.reolink_facts:
        hostname: 192.168.1.100
        password: "{{ admin_password }}"
      register: cam

    - ansible.builtin.debug:
        msg: "{{ cam.facts.model }} — {{ cam.facts.num_channels }} channel(s)"
```

---

## Full Example Playbook

See [`docs/example-playbook.yml`](docs/example-playbook.yml) for a complete
camera-provisioning playbook.

---

## Module Reference

### Connection Parameters (common to all modules)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hostname` | str | *required* | Camera/NVR IP address or hostname |
| `username` | str | `admin` | Login username |
| `password` | str | *required* | Login password |
| `port` | int | 443 or 80 | Port, from `use_https` if omitted |

The modules never let reolink-aio "recover" from a failed login by switching
camera services on over the Baichuan protocol, which it otherwise does when the
port or protocol is unknown or an HTTP login fails (HTTPS, RTSP, ONVIF, then
RTMP). A failed login fails the task.
| `use_https` | bool | `true` | HTTPS (port 443) rather than HTTP (port 80) |
| `timeout` | int | `30` | Connection timeout (seconds) |

---

### `reolink_camera`

Configure camera settings. All parameters except `hostname` and `password` are
optional. Only supplied parameters are modified.

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | int | Channel index (0 for standalone cameras) |
| `ntp` | dict | NTP settings (see below) |
| `time` | dict | Date/time display settings |
| `video` | dict | Stream encoding settings |
| `image` | dict | Brightness, contrast, saturation, hue, sharpness |
| `ir_lights` | bool | Enable/disable infrared LEDs |
| `recording` | bool | Enable/disable continuous recording |
| `audio` | bool | Enable/disable audio recording |
| `motion_detection` | bool | Enable/disable motion detection |
| `osd` | dict | On-screen display overlay settings |
| `daynight` | str | `Auto` / `Color` / `Black&White` |
| `backlight` | str | `DynamicRangeControl` / `BackLightControl` / `Off` |
| `spotlight` | bool | Enable/disable white spotlight |
| `flip` | bool | Flip the image vertically (ISP `rotation`) |
| `mirror` | bool | Mirror the image horizontally (ISP `mirroring`); an upside-down mount needs both |
| `push_notifications` | bool | Enable/disable push notifications via Reolink (device-wide where the camera has no per-channel switch) |
| `email_notifications` | bool | Enable/disable email alerts |
| `ftp_upload` | bool | Enable/disable FTP upload on motion |
| `net_port` | dict | Enable/disable the `rtsp`, `onvif` and `rtmp` servers |
| `p2p_enabled` | bool | Enable/disable P2P relay through Reolink's servers |
| `auto_upgrade` | bool | Enable/disable automatic firmware upgrades from Reolink |
| `upnp` | bool | Enable/disable UPnP port mapping on the router |
| `ddns` | bool | Enable/disable dynamic DNS registration |

Every setting is compared with the camera's current value and sent only if it
differs, so `changed` means the camera was changed. The exceptions are
`spotlight` (always sent) and `ntp.sync_now` (an action, never a change).
`flip`, `mirror`, `time`, `push_notifications`, `email_notifications`,
`ftp_upload`, `recording`, `auto_upgrade`, `upnp` and `ddns` also fail the task
if the camera lacks the setting or does not take it. Push, email, FTP and
recording switch per channel where the camera can, and device-wide where that
is all it has.

#### Stopping the camera phoning home

P2P, push notifications, automatic firmware upgrades, UPnP and DDNS all reach
outside servers, and all can be turned off:

```yaml
p2p_enabled: false
push_notifications: false
auto_upgrade: false
upnp: false
ddns: false
```

This stops the camera asking. Only blocking its internet access at the network
stops it succeeding. NTP is the one outbound connection a camera needs; point
`ntp.server` at a local server to keep that inside the LAN too.

#### `time` sub-options

| Key | Type | Description |
|-----|------|-------------|
| `date_format` | str | `DD/MM/YYYY`, `MM/DD/YYYY` or `YYYY/MM/DD` |
| `hours_24` | bool | 24-hour clock |
| `timezone_offset` | int | Standard-time offset in seconds WEST of UTC (`18000` for UTC-5) |
| `dst` | dict | DST rule: `enabled`, `offset` (hours), and `start`/`end`, each `month`, `week` (1-4, 5 = last), `weekday` (0 = Sunday), `hour`, `minute`, `second` |

With a DST rule the camera changes its own clock at the transitions, so give
`timezone_offset` the standard (winter) offset. US Eastern:

```yaml
time:
  timezone_offset: 18000
  dst:
    enabled: true
    offset: 1
    start: {month: 3, week: 2, weekday: 0, hour: 2, minute: 0, second: 0}
    end: {month: 11, week: 1, weekday: 0, hour: 2, minute: 0, second: 0}
```

`time` is applied before `ntp`, so `ntp.sync_now` sets the clock in the new zone.

#### `ntp` sub-options

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | bool | Enable NTP synchronization |
| `server` | str | NTP server hostname or IP |
| `port` | int | NTP port (1–65535, default 123) |
| `interval` | int | Sync interval in minutes (60–65535) |
| `sync_now` | bool | Trigger immediate sync |

#### `video` sub-options

| Key | Type | Description |
|-----|------|-------------|
| `stream` | str | `main`, `sub`, or `ext` |
| `encoding` | str | `h264` or `h265` |
| `bitrate` | int | Bitrate in kbps; must be one the camera offers (sub streams are typically 64-512) |
| `frame_rate` | int | Frame rate in fps; must be one the camera offers |

#### `image` sub-options

All values are integers in the range 0–255.

| Key | Description |
|-----|-------------|
| `brightness` | Image brightness |
| `contrast` | Image contrast |
| `saturation` | Color saturation |
| `hue` | Image hue |
| `sharpen` | Sharpness level |

---

### `reolink_user`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_username` | str | same as `username` | Account to manage |
| `new_password` | str | — | New password to set |
| `privilege` | str | `viewer` | `admin`, `guest`, or `viewer` |
| `state` | str | `present` | `present` or `absent` |

---

### `reolink_facts`

No extra parameters beyond the common connection options. Returns a `facts` dict
containing device info and per-channel state, including what playbooks need to
check that settings took:

- `time`: the clock the camera shows (`local_time`), the UTC offset it is
  applying now with DST included (`utc_offset`, seconds east of UTC), its error
  against the controller's clock (`clock_error`), its date format and 12/24-hour
  setting, and its zone and DST settings
- `outbound`: `p2p`, `auto_upgrade`, `upnp` and `ddns`, each true if on
- `net_port`: whether `rtsp`, `onvif` and `rtmp` are enabled
- per channel: `flip`, `mirror`, `push_notifications`, `email_notifications`,
  `ftp_upload`, `webhooks` (how many are active), and `streams`: each of the
  `main` and `sub` streams' `encoding`, `bitrate`, `frame_rate`, `width` and
  `height`

With `check_firmware: true` it also asks reolink.com for the newest firmware
for the camera's model and hardware version, and reports it under `firmware`
(`current`, `latest`, `update_available`, `download_url`, `release_notes`). The
request comes from the host running the module, not the camera.

---

## Security Considerations

- Always use Ansible Vault or an external secrets manager for passwords.
  Never hardcode credentials in playbooks.
- Change default passwords before connecting cameras to any network segment.
- Consider placing cameras on an isolated VLAN with no internet access and
  routing NTP through a local server.
- Reolink passwords are limited to 31 characters and a restricted character set
  (a–z, A–Z, 0–9, and `!@#$%^&*()-_+=|[]{};:',.<>?`).

---

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
