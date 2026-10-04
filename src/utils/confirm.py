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


def describe_action(name: str, params: dict) -> str:
    target = params.get("memberId") or params.get("channelName") or "?"
    return {
        "removeMember": f"เตะ **{target}** ออกจาก server",
        "blockMember": f"แบน **{target}**",
        "clearMessages": f"ลบข้อความ (limit {params.get('limit', '?')})",
        "deleteChannel": f"ลบห้อง **{target}**",
        "deleteThread": f"ลบเธรด **{target}**",
    }.get(name, f"รัน `{name}`")
