"""✅/❌ confirmation gate for destructive skills.

Ported from discord-agent's tools_permissions.ConfirmationView: only the
original requester can confirm, 60s timeout, result awaited by the executor.
"""

import asyncio

import discord


class ConfirmView(discord.ui.View):
    def __init__(self, requester_id: int, description: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.description = description
        self.confirmed: bool | None = None
        self._event = asyncio.Event()

    @discord.ui.button(label="✅ ยืนยัน", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("เฉพาะคนสั่งเท่านั้นที่กดได้", ephemeral=True)
            return
        self.confirmed = True
        self._event.set()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"✅ **ยืนยันแล้ว**: {self.description}", view=self)
        self.stop()

    @discord.ui.button(label="❌ ยกเลิก", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("เฉพาะคนสั่งเท่านั้นที่กดได้", ephemeral=True)
            return
        self.confirmed = False
        self._event.set()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"❌ **ยกเลิกแล้ว**: {self.description}", view=self)
        self.stop()

    async def on_timeout(self):
        self.confirmed = None
        self._event.set()


async def request_confirm(channel, requester_id: int, description: str,
                          timeout: float = 60.0) -> bool:
    """Post a confirm prompt, wait for the requester's answer. Timeout = False."""
    view = ConfirmView(requester_id, description, timeout=timeout)
    msg = await channel.send(f"⚠️ **ต้องยืนยันก่อน**: {description}", view=view)
    await view._event.wait()
    if view.confirmed is None:
        for item in view.children:
            item.disabled = True
        try:
            await msg.edit(content=f"⏰ **หมดเวลา** — ยกเลิก: {description}", view=view)
        except discord.HTTPException:
            pass
    return view.confirmed is True


def _short(v) -> str:
    s = str(v)
    return s if len(s) <= 40 else s[:37] + "..."


def describe_action(name: str, params: dict) -> str:
    params = params or {}
    target = params.get("memberId") or params.get("channelName") or "?"
    pretty = {
        "createRole": lambda p: f"สร้างยศ **{p.get('name', '?')}**"
            + (f" สี {p['color']}" if p.get("color") else "")
            + (f" สิทธิ์: {p['permissions']}" if p.get("permissions") else ""),
        "addRoleToMember": lambda p: f"ให้ยศ **{p.get('roleName', '?')}** กับ {p.get('memberId', '?')}",
        "removeRoleFromMember": lambda p: f"ถอดยศ **{p.get('roleName', '?')}** จาก {p.get('memberId', '?')}",
        "setRolePermissions": lambda p: f"ตั้งสิทธิ์ยศ **{p.get('roleName', '?')}**: {p.get('permissions', '?')}",
        "createChannel": lambda p: f"สร้างห้อง **{p.get('name', '?')}**",
        "createCategory": lambda p: f"สร้างหมวด **{p.get('name', '?')}**",
        "moveAllMembers": lambda p: f"ย้ายทุกคนจาก **{p.get('fromChannel', '?')}** → **{p.get('toChannel', '?')}**",
        "moveMember": lambda p: f"ย้าย {p.get('memberId', '?')} → {p.get('channelId') or 'ตัดสาย'}",
        "timeoutMember": lambda p: f"timeout {p.get('memberId', '?')} {p.get('durationMinutes', '?')} นาที",
        "setNickname": lambda p: f"ตั้งฉายา {p.get('memberId', '?')} = {p.get('nickname', '?')}",
        "rememberFact": lambda p: f"จำไว้ว่า **{p.get('key', '?')}**",
        "setMemberAlias": lambda p: f"จำชื่อ **{p.get('alias', '?')}** = {p.get('memberId', '?')}",
        "createThread": lambda p: f"สร้างเธรด **{p.get('name', '?')}**",
        "archiveThread": lambda p: f"{'เก็บ' if p.get('archived', True) else 'เปิด'}เธรด **{p.get('threadName', '?')}**",
        "createInvite": lambda p: "สร้างลิงก์เชิญ",
        "sendMessage": lambda p: f"ส่งข้อความไป #{p.get('channelName', '?')}",
        "removeMember": lambda p: f"เตะ **{p.get('memberId', '?')}** ออกจาก server",
        "blockMember": lambda p: f"แบน **{p.get('memberId', '?')}**",
        "clearMessages": lambda p: f"ลบข้อความ (limit {p.get('limit', '?')})",
        "deleteChannel": lambda p: f"ลบห้อง **{p.get('channelName', '?')}**",
        "deleteThread": lambda p: f"ลบเธรด **{p.get('threadName', '?')}**",
    }
    if name in pretty:
        try:
            return pretty[name](params)
        except Exception:  # noqa: BLE001
            pass
    rest = ", ".join(f"{k}={_short(v)}" for k, v in params.items() if v not in (None, ""))
    return f"รัน `{name}`" + (f" ({rest})" if rest else "")
