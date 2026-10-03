"""Role skills (8): create/delete/edit/permissions/list/info/assign/remove."""

import discord

from . import Skill, register
from src.utils.fuzzy_match import find_member, find_role


def _parse_colour(value) -> discord.Colour | None:
    if value is None:
        return None
    try:
        return discord.Colour.from_str(str(value))
    except ValueError:
        s = str(value).strip().lstrip("#")
        return discord.Colour(int(s, 16))


def _parse_permissions(guild, requester, value) -> discord.Permissions:
    """Comma-separated discord permission flags -> Permissions (starts from none).

    'administrator' is only grantable by the server owner.
    """
    perms = discord.Permissions.none()
    names = [n.strip().lower() for n in str(value).split(",") if n.strip()]
    if not names:
        raise ValueError("No permissions given.")
    valid = set(discord.Permissions.VALID_FLAGS)
    unknown = [n for n in names if n not in valid]
    if unknown:
        raise ValueError(
            f"Unknown permission(s): {', '.join(unknown)}. "
            "Use Discord flag names like kick_members, manage_messages, connect, speak."
        )
    if "administrator" in names and requester.id != guild.owner_id:
        raise ValueError("Only the server owner can grant the administrator permission.")
    for n in names:
        setattr(perms, n, True)
    return perms


async def _create_role(guild, params, message):
    name = params.get("name")
    if not name:
        raise ValueError("I need a name for the role first.")
    kwargs: dict = {
        "name": name,
        "reason": f"Created by AI bot for {message.author}",
    }
    colour = _parse_colour(params.get("color"))
    if colour:
        kwargs["colour"] = colour
    if params.get("hoist") is not None:
        kwargs["hoist"] = bool(params["hoist"])
    if params.get("mentionable") is not None:
        kwargs["mentionable"] = bool(params["mentionable"])
    if params.get("permissions"):
        kwargs["permissions"] = _parse_permissions(guild, message.author, params["permissions"])
    role = await guild.create_role(**kwargs)
    return f"Role **{role.name}** created."


register(Skill(
    name="createRole",
    description="Creates a new role with optional color (hex), hoist, mentionable, and permissions settings.",
    params={
        "name": "string - role name",
        "color": "string (optional) - hex color like #FF0000",
        "hoist": "boolean (optional) - display separately",
        "mentionable": "boolean (optional) - allow mentions",
        "permissions": "string (optional) - comma-separated permission flags e.g. kick_members,manage_messages (or 'administrator')",
        "reason": "string (optional) - audit log reason",
    },
    execute=_create_role,
    required_permissions=["manage_roles"],
))


async def _delete_role(guild, params, message):
    role = find_role(guild, params.get("roleName", ""))
    if not role:
        raise ValueError(f"I couldn't find a role called \"{params.get('roleName')}\" here.")
    if role.is_default() or role.managed:
        raise ValueError(f"I can't delete the role **{role.name}** (system-managed).")
    await role.delete(reason=f"Deleted by AI bot for {message.author}")
    return True


register(Skill(
    name="deleteRole",
    description="Deletes a role from the server.",
    params={"roleName": "string - The name, mention, or ID of the role to delete."},
    execute=_delete_role,
    required_permissions=["manage_roles"],
))


async def _edit_role(guild, params, message):
    role = find_role(guild, params.get("currentName", ""))
    if not role:
        raise ValueError(f"I couldn't find a role called \"{params.get('currentName')}\" here.")
    kwargs: dict = {"reason": f"Edited by AI bot for {message.author}"}
    if params.get("newName"):
        kwargs["name"] = params["newName"]
    colour = _parse_colour(params.get("color"))
    if colour:
        kwargs["colour"] = colour
    if params.get("hoist") is not None:
        kwargs["hoist"] = bool(params["hoist"])
    if params.get("mentionable") is not None:
        kwargs["mentionable"] = bool(params["mentionable"])
    await role.edit(**kwargs)
    return True


register(Skill(
    name="editRole",
    description="Edits the name, color, hoist, or mentionable setting of a role.",
    params={
        "currentName": "string - The current name, mention, or ID of the role.",
        "newName": "string (optional) - New role name.",
        "color": "string (optional) - New hex color.",
        "hoist": "boolean (optional).",
        "mentionable": "boolean (optional).",
    },
    execute=_edit_role,
    required_permissions=["manage_roles"],
))


async def _set_role_permissions(guild, params, message):
    role = find_role(guild, params.get("roleName", ""))
    if not role:
        raise ValueError(f"I couldn't find a role called \"{params.get('roleName')}\" here.")
    if role.is_default() or role.managed:
        raise ValueError(f"I can't change permissions of **{role.name}** (system-managed).")
    if role.position >= guild.me.top_role.position:
        raise ValueError(
            f"I can't edit **{role.name}** — it sits above my highest role."
        )
    perms = _parse_permissions(guild, message.author, params.get("permissions", ""))
    await role.edit(permissions=perms, reason=f"Permissions set by AI bot for {message.author}")
    on = [n for n in discord.Permissions.VALID_FLAGS if getattr(perms, n)]
    return f"Role **{role.name}** now has: {', '.join(on)}"


register(Skill(
    name="setRolePermissions",
    description="Sets what a role is allowed to do (replaces its permission flags).",
    params={
        "roleName": "string - The name, mention, or ID of the role.",
        "permissions": "string - comma-separated permission flags e.g. kick_members,manage_messages (or 'administrator', owner-only)",
    },
    execute=_set_role_permissions,
    required_permissions=["manage_roles"],
))


async def _list_roles(guild, params, message):
    roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
    lines = [
        f"- {r.name} ({len(r.members)} members) {r.mention}" for r in roles if not r.is_default()
    ]
    return "\n".join(lines) or "This server has no custom roles."


async def _list_roles_raw(guild, message):
    return {"total": len(guild.roles), "names": [r.name for r in guild.roles[:50]]}


register(Skill(
    name="listRoles",
    description="Lists all roles in the server with member counts.",
    params={"format": "string (optional) - reserved, currently ignored."},
    execute=_list_roles,
    fetch_raw=_list_roles_raw,
))


async def _get_role_info(guild, params, message):
    role = find_role(guild, params.get("roleName", ""))
    if not role:
        raise ValueError(f"I couldn't find a role called \"{params.get('roleName')}\" here.")
    return (
        f"**{role.name}**\nID: {role.id} | Mention: {role.mention}\n"
        f"Color: {role.colour} | Hoist: {role.hoist} | Mentionable: {role.mentionable}\n"
        f"Position: {role.position} | Members: {len(role.members)}"
    )


register(Skill(
    name="getRoleInfo",
    description="Shows detailed info about one role (color, position, member count).",
    params={"roleName": "string - The name, mention, or ID of the role."},
    execute=_get_role_info,
))


async def _add_role(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    role = find_role(guild, params.get("roleName", ""))
    if not role:
        raise ValueError(f"I couldn't find a role called \"{params.get('roleName')}\" here.")
    await member.add_roles(role, reason=f"Added by AI bot for {message.author}")
    return True


register(Skill(
    name="addRoleToMember",
    description="Gives a role to a member.",
    params={
        "memberId": "string - The ID, mention, or username of the member.",
        "roleName": "string - The name, mention, or ID of the role.",
    },
    execute=_add_role,
    required_permissions=["manage_roles"],
    targets_member=True,
))


async def _remove_role(guild, params, message):
    member = await find_member(guild, params.get("memberId", ""))
    if not member:
        raise ValueError(f"I couldn't find anyone matching \"{params.get('memberId')}\" here.")
    role = find_role(guild, params.get("roleName", ""))
    if not role:
        raise ValueError(f"I couldn't find a role called \"{params.get('roleName')}\" here.")
    await member.remove_roles(role, reason=f"Removed by AI bot for {message.author}")
    return True


register(Skill(
    name="removeRoleFromMember",
    description="Removes a role from a member.",
    params={
        "memberId": "string - The ID, mention, or username of the member.",
        "roleName": "string - The name, mention, or ID of the role.",
    },
    execute=_remove_role,
    required_permissions=["manage_roles"],
    targets_member=True,
))
