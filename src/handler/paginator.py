"""Button pagination for long replies — mirrors the paginated Components V2
UIs in discord-bot-agents (utils/uiBuilder.js), adapted to discord.py Views.

Only the command author can flip pages; buttons disable after timeout.
"""

import discord

PAGE_LIMIT = 1900
BUTTON_TIMEOUT = 120.0


def split_pages(text: str, limit: int = PAGE_LIMIT) -> list[str]:
    """Split on line boundaries so list rows never break mid-line."""
    pages, cur = [], ""
    for line in (text or "").split("\n"):
        if len(cur) + len(line) + 1 > limit and cur:
            pages.append(cur)
            cur = ""
        cur += line + "\n"
        while len(cur) > limit:  # single over-long line: hard cut
            pages.append(cur[:limit])
            cur = cur[limit:]
    if cur.strip():
        pages.append(cur)
    return pages or ["(ว่างเปล่า)"]


class Paginator(discord.ui.View):
    def __init__(self, pages: list[str], author_id: int):
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.pages = pages
        self.author_id = author_id
        self.index = 0
        self._sync_labels()

    def _sync_labels(self):
        self.prev_btn.disabled = self.index == 0
        self.next_btn.disabled = self.index == len(self.pages) - 1
        self.page_btn.label = f"{self.index + 1}/{len(self.pages)}"

    def _content(self) -> str:
        return self.pages[self.index]

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "ปุ่มนี้ของคนสั่งเท่านั้น", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _btn):
        if not await self._guard(interaction):
            return
        self.index = max(0, self.index - 1)
        self._sync_labels()
        await interaction.response.edit_message(content=self._content(), view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_btn(self, interaction: discord.Interaction, _btn):
        pass  # page indicator, not clickable (stays disabled)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _btn):
        if not await self._guard(interaction):
            return
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._sync_labels()
        await interaction.response.edit_message(content=self._content(), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


async def reply_paginated(message: discord.Message, text: str):
    """Reply with plain text, or a button paginator when it spans pages."""
    pages = split_pages(text)
    if len(pages) == 1:
        await message.reply(pages[0], mention_author=False)
        return
    view = Paginator(pages, message.author.id)
    await message.reply(pages[0], view=view, mention_author=False)
