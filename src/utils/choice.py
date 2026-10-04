"""❓ choice gate: buttons for fixed options + free-text custom answer.

Used when the planner is genuinely torn between a few concrete options.
Returns (kind, value): ('option', text) | ('custom', text) | (None, None).
"""

import asyncio

import discord


class ChoiceView(discord.ui.View):
    def __init__(self, requester_id: int, options: list[str], timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.result: tuple | None = None
        self._event = asyncio.Event()
        for opt in options[:5]:
            btn = discord.ui.Button(label=str(opt)[:80],
                                    style=discord.ButtonStyle.primary)
            btn.callback = self._make_cb(str(opt))
            self.add_item(btn)

    def _make_cb(self, opt: str):
        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.requester_id:
                await interaction.response.send_message(
                    "เฉพาะคนสั่งเท่านั้นที่เลือกได้", ephemeral=True)
                return
            self.result = ("option", opt)
            self._event.set()
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(
                content=f"✅ เลือก: **{opt}**", view=self)
            self.stop()
        return cb

    async def on_timeout(self):
        self._event.set()


async def request_choice(client: discord.Client, channel,
                         requester_id: int, question: str,
                         options: list[str], timeout: float = 120.0) -> tuple:
    """Ask with buttons; the user may also just type their own answer."""
    view = ChoiceView(requester_id, options, timeout=timeout)
    msg = await channel.send(
        f"❓ **{question}**\n(กดปุ่มข้างล่าง หรือพิมพ์ตอบเองได้เลย)", view=view)

    def msg_check(m: discord.Message) -> bool:
        return (m.author.id == requester_id
                and m.channel.id == channel.id
                and not m.author.bot)

    wait_msg = asyncio.create_task(client.wait_for("message", check=msg_check))
    wait_btn = asyncio.create_task(view._event.wait())
    try:
        done, pending = await asyncio.wait(
            [wait_msg, wait_btn],
            return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
    except Exception:  # noqa: BLE001
        done, pending = set(), {wait_msg, wait_btn}
    for t in pending:
        t.cancel()

    if wait_btn in done and view.result:
        return view.result
    if wait_msg in done:
        try:
            text = wait_msg.result().content.strip()
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            for item in view.children:
                item.disabled = True
            try:
                await msg.edit(content=f"✏️ รับทราบ: **{text[:200]}**", view=view)
            except discord.HTTPException:
                pass
            view.stop()
            return ("custom", text)

    for item in view.children:
        item.disabled = True
    try:
        await msg.edit(content="⏰ **หมดเวลา** — ยกเลิก", view=view)
    except discord.HTTPException:
        pass
    view.stop()
    return (None, None)
