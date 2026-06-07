#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: reolink_user
short_description: Manage users and passwords on Reolink cameras
version_added: "1.0.0"
description:
  - Creates, modifies, or removes user accounts on Reolink IP cameras and NVRs.
  - The most common use case is changing the C(admin) password after initial setup.
  - Uses the Reolink HTTP API directly since user management is not exposed
    by the C(reolink-aio) higher-level API.
  - Uses the C(reolink-aio) library only for authentication; user modifications
    are performed via direct API calls (C(ModifyUser), C(AddUser), C(DelUser)).
  - B(Security note:) Always change the default admin password before exposing
    a camera to any network.
author:
  - Dan Hackney (@haxney)
requirements:
  - reolink-aio >= 0.9.0
  - Python >= 3.11
notes:
  - Reolink passwords must be 1-31 characters and contain only alphanumeric
    characters and the special characters C(!@#$%^&*()-_+=|[]{};:',.<>?).
  - Reolink supports three user privilege levels: C(admin), C(guest), and C(viewer).
  - Only one C(admin) account is supported on most Reolink devices.
options:
  hostname:
    description: IP address or hostname of the camera or NVR.
    type: str
    required: true
  username:
    description: Username for authentication (must be an admin account).
    type: str
    default: admin
  password:
    description: Current password for authentication.
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
  target_username:
    description:
      - The username of the account to manage.
      - Defaults to the value of C(username) (i.e. change the current user's own password).
    type: str
  new_password:
    description:
      - New password to set for C(target_username).
      - Required when C(state=present) and you want to change a password.
    type: str
    no_log: true
  privilege:
    description:
      - Privilege level for the user account.
      - C(admin) has full access. C(guest) and C(viewer) have read-only access.
      - Only meaningful when C(state=present) and creating a new user, or
        when explicitly changing an existing user's privilege level.
    type: str
    choices: [admin, guest, viewer]
    default: viewer
  state:
    description:
      - C(present) ensures the user exists with the given password and/or privilege.
      - C(absent) removes the user account.
      - The built-in C(admin) account cannot be removed.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Change the admin password (most common use case)
  haxney.reolink.reolink_user:
    hostname: 192.168.1.100
    username: admin
    password: "{{ current_admin_password }}"
    new_password: "{{ new_admin_password }}"

- name: Add a read-only viewer account
  haxney.reolink.reolink_user:
    hostname: 192.168.1.100
    username: admin
    password: "{{ admin_password }}"
    target_username: viewer
    new_password: "{{ viewer_password }}"
    privilege: viewer
    state: present

- name: Remove a user
  haxney.reolink.reolink_user:
    hostname: 192.168.1.100
    username: admin
    password: "{{ admin_password }}"
    target_username: olduser
    state: absent
"""

RETURN = r"""
changed:
  description: Whether any changes were made to user accounts.
  type: bool
  returned: always
action:
  description: The action performed (C(created), C(modified), C(deleted), or C(none)).
  type: str
  returned: always
target_username:
  description: The username that was managed.
  type: str
  returned: always
users:
  description: List of users present on the device after the operation.
  type: list
  elements: dict
  returned: always
  contains:
    userName:
      description: Username.
      type: str
    level:
      description: Privilege level.
      type: str
"""

import json

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


def _get_users(module, host):
    """Return list of user dicts from the device."""
    try:
        run_async(host.get_host_data())
        users = getattr(host, "_users", None)
        if users is None:
            # Fallback: read from the raw host data structure
            users = []
        if isinstance(users, dict):
            users = [users]
        return users if users else []
    except Exception as exc:
        module.fail_json(msg=f"Failed to retrieve user list: {exc}")


def _send_user_cmd(module, host, cmd, user_payload):
    """Send a user management command (ModifyUser, AddUser, DelUser)."""
    body = [{"cmd": cmd, "action": 0, "param": {"User": user_payload}}]
    try:
        run_async(host.send_setting(body))
    except Exception as exc:
        module.fail_json(msg=f"Failed to execute {cmd}: {exc}")


def main():
    module = AnsibleModule(
        argument_spec=dict(
            hostname=dict(type="str", required=True),
            username=dict(type="str", default="admin"),
            password=dict(type="str", required=True, no_log=True),
            port=dict(type="int"),
            use_https=dict(type="bool"),
            timeout=dict(type="int", default=30),
            target_username=dict(type="str"),
            new_password=dict(type="str", no_log=True),
            privilege=dict(type="str", choices=["admin", "guest", "viewer"], default="viewer"),
            state=dict(type="str", choices=["present", "absent"], default="present"),
        ),
        supports_check_mode=True,
    )

    check_reolink_import(module)

    target_username = module.params.get("target_username") or module.params["username"]
    new_password = module.params.get("new_password")
    privilege = module.params["privilege"]
    state = module.params["state"]
    check_mode = module.check_mode

    if state == "absent" and target_username == "admin":
        module.fail_json(msg="The 'admin' account cannot be removed.")

    host = connect(module)
    try:
        users = _get_users(module, host)
        existing = next((u for u in users if u.get("userName") == target_username), None)

        action = "none"
        changed = False

        if state == "present":
            if existing is None:
                # Create new user
                if new_password is None:
                    module.fail_json(msg="new_password is required when creating a new user.")
                changed = True
                action = "created"
                if not check_mode:
                    _send_user_cmd(module, host, "AddUser", {
                        "userName": target_username,
                        "password": new_password,
                        "level": privilege,
                    })
            else:
                # Modify existing user if anything changed
                updates = {}
                if new_password is not None:
                    updates["password"] = new_password
                # Only update privilege when the user explicitly passes it as non-default
                # AND it differs from existing. The API always requires userName.
                current_level = existing.get("level", "")
                if privilege and current_level and privilege != current_level and module.params.get("privilege"):
                    updates["level"] = privilege

                if updates:
                    changed = True
                    action = "modified"
                    if not check_mode:
                        payload = {"userName": target_username}
                        payload.update(updates)
                        _send_user_cmd(module, host, "ModifyUser", payload)

        elif state == "absent":
            if existing is not None:
                changed = True
                action = "deleted"
                if not check_mode:
                    _send_user_cmd(module, host, "DelUser", {"userName": target_username})

        # Re-fetch users for the return value
        if changed and not check_mode:
            users = _get_users(module, host)

        # Sanitize user list for output (never include passwords)
        safe_users = [{"userName": u.get("userName", ""), "level": u.get("level", "")} for u in users]

    finally:
        disconnect(module, host)

    module.exit_json(
        changed=changed,
        action=action,
        target_username=target_username,
        users=safe_users,
    )


if __name__ == "__main__":
    main()
