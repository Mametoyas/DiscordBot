"""Voice/music skills (9) via Lavalink + wavelink (no FFmpeg/PyNaCl on the bot).

Needs LAVALINK_HOST + LAVALINK_PASSWORD env and the user in a voice channel.
Autoplay is OFF — queue advance is handled by on_wavelink_track_end in bot.py.
"""

import discord
import wavelink

from . import Skill, register
from src import config


def _node_ready() -> bool:
    try:
        nodes = list((wavelink.Pool.nodes or {}).values())
    except AttributeError:
        return False
    for n in nodes:
        try:
            if n.status is wavelink.NodeStatus.CONNECTED:
                return True
        except AttributeError:
            pass
    return False


async def _wait_node(timeout: float = 20.0):
    """รอ node ต่อติด (wavelink reconnect เองเมื่อหลุด) เกินเวลา = error ภาษาคน"""
    import asyncio
    import time as _t

    start = _t.monotonic()
    while _t.monotonic() - start < timeout:
        if _node_ready():
            return
        await asyncio.sleep(0.5)
    raise ValueError("เซิร์ฟเวอร์เพลงกำลังต่อใหม่ — รอ ~30 วิแล้วสั่งอีกที")


def _require_ready():
    if not config.LAVALINK_HOST or not config.LAVALINK_PASSWORD:
        raise ValueError("ระบบเพลงยังไม่ได้ตั้งค่า (LAVALINK_HOST/PASSWORD) — ดู DEPLOY.md")
    if not _node_ready():
        raise ValueError("เซิร์ฟเวอร์เพลงยังไม่พร้อม — รอสักครู่แล้วสั่งอีกที")


def _player(guild: discord.Guild) -> wavelink.Player | None:
    vc = guild.voice_client
    return vc if isinstance(vc, wavelink.Player) else None


async def _ensure_player(guild: discord.Guild, requester: discord.Member,
                          channel_name: str = "") -> wavelink.Player:
    """requester = Member (has .voice). Shared by mention-skills and slash commands."""
    _require_ready()
    await _wait_node()
    player = _player(guild)
    if player:
        return player
    target = None
    if channel_name:
        from src.utils.fuzzy_match import find_channel as _find

        target = _find(guild, channel_name,
                       kinds=(discord.ChannelType.voice, discord.ChannelType.stage_voice))
        if not target:
            raise ValueError(f"ไม่เจอห้องเสียงชื่อ \"{channel_name}\"")
    else:
        voice = getattr(requester, "voice", None)
        if not voice or not voice.channel:
            raise ValueError("เข้าห้องเสียง (voice) ก่อน แล้วสั่งอีกที")
        target = voice.channel
    perms = target.permissions_for(guild.me)
    if not perms.connect or not perms.speak:
        raise ValueError(f"บอทเข้า/พูดในห้อง {target.name} ไม่ได้ (เช็ค permission)")
    player = await target.connect(cls=wavelink.Player)
    player.autoplay = wavelink.AutoPlayMode.disabled
    return player


def _fmt(ms: int) -> str:
    s = max(0, int(ms or 0) // 1000)
    return f"{s // 60}:{s % 60:02d}"


def _title(t) -> str:
    name = getattr(t, "title", None) or str(t)
    author = getattr(t, "author", None)
    return f"{name} — {author}" if author else name


async def _join(guild, params, message):
    return await do_join(guild, message.author, params.get("channelName", ""))


register(Skill(
    name="joinVoice",
    description="Joins a voice channel (named, or the requester's current one).",
    params={"channelName": "string (optional) - Voice channel name/mention/ID."},
    execute=_join,
    required_permissions=["connect", "speak"],
))


async def _leave(guild, params, message):
    return await do_leave(guild)


register(Skill(
    name="leaveVoice",
    description="Leaves the voice channel and clears the queue.",
    params={},
    execute=_leave,
))


async def _play(guild, params, message):
    return await do_play(guild, message.author, params.get("query", ""))


register(Skill(
    name="playMusic",
    description="Searches YouTube and plays audio (queues if something is playing).",
    params={"query": "string - Song name or YouTube/playlist URL."},
    execute=_play,
    required_permissions=["connect", "speak"],
))


async def _stop(guild, params, message):
    return await do_stop(guild)


register(Skill(
    name="stopMusic",
    description="Stops playback and clears the queue.",
    params={},
    execute=_stop,
))


async def _skip(guild, params, message):
    return await do_skip(guild)


register(Skill(
    name="skipTrack",
    description="Skips to the next track in the queue.",
    params={},
    execute=_skip,
))


async def _queue(guild, params, message):
    return await do_queue(guild)


register(Skill(
    name="musicQueue",
    description="Shows the current track and queued songs.",
    params={},
    execute=_queue,
))


async def _now(guild, params, message):
    player = _player(guild)
    if not player or not player.current:
        return "ตอนนี้ไม่มีเพลงเล่นอยู่"
    t = player.current
    return f"🎵 **{_title(t)}** [{_fmt(player.position)}/{_fmt(t.length)}]"


register(Skill(
    name="nowPlaying",
    description="Shows the currently playing track and position.",
    params={},
    execute=_now,
))


async def _pause(guild, params, message):
    player = _player(guild)
    if not player or (not player.playing and not player.paused):
        raise ValueError("ตอนนี้ไม่มีเพลงเล่นอยู่")
    pause = params.get("pause", True)
    pause = pause if isinstance(pause, bool) else str(pause).lower() not in ("false", "0", "no")
    await player.pause(pause)
    return "⏸️ หยุดชั่วคราว" if pause else "▶️ เล่นต่อ"


register(Skill(
    name="pauseMusic",
    description="Pauses or resumes playback (pause:false resumes).",
    params={"pause": "boolean (optional) - true = pause, false = resume (default true)."},
    execute=_pause,
))


async def _volume(guild, params, message):
    player = _player(guild)
    if not player:
        raise ValueError("บอทไม่ได้อยู่ในห้องเสียง")
    try:
        vol = int(params.get("volume", 100))
    except (TypeError, ValueError):
        raise ValueError("ระดับเสียงต้องเป็นตัวเลข 0-150")
    vol = max(0, min(150, vol))
    try:
        await player.set_volume(vol)
    except (AttributeError, TypeError):
        raise ValueError("เซิร์ฟเวอร์เพลงไม่รองรับการปรับเสียง")
    return f"🔊 เสียง {vol}%"


register(Skill(
    name="musicVolume",
    description="Sets playback volume (0-150).",
    params={"volume": "number - 0 to 150."},
    execute=_volume,
))


# ---------------------------------------------------------------------------
# Public core — shared by mention-skills (above) and slash commands (bot.py)
# ---------------------------------------------------------------------------

async def do_join(guild: discord.Guild, requester: discord.Member, channel_name: str = "") -> str:
    player = await _ensure_player(guild, requester, channel_name)
    return f"เข้าห้อง {player.channel.name} แล้ว"


async def do_leave(guild: discord.Guild):
    player = _player(guild)
    if not player:
        return "บอทไม่ได้อยู่ในห้องเสียงอยู่แล้ว"
    try:
        player.queue.clear()
    except Exception:
        pass
    await player.disconnect()
    return "👋 ออกจากห้องเสียงแล้ว"


async def do_play(guild: discord.Guild, requester: discord.Member, query: str) -> str:
    query = (query or "").strip()
    if not query:
        raise ValueError("บอกชื่อเพลงหรือลิงก์มาก่อน")
    player = await _ensure_player(guild, requester)
    try:
        tracks = await wavelink.Playable.search(query, source="ytsearch")
    except Exception:
        raise ValueError("ค้นหาเพลงไม่สำเร็จ — เซิร์ฟเวอร์เพลงอาจมีปัญหา ลองอีกที")
    if not tracks:
        raise ValueError(f"หาเพลง \"{query}\" ไม่เจอ ลองคำอื่น")
    if isinstance(tracks, wavelink.Playlist):
        added = await player.queue.put_wait(tracks)
        names = f"เพลย์ลิสต์ **{tracks.name}** ({added} เพลง)"
    else:
        await player.queue.put_wait(tracks[0])
        names = f"**{_title(tracks[0])}**"
    if not player.playing and not player.paused:
        await player.play(player.queue.get())
        return f"▶️ กำลังเล่น {names}"
    return f"➕ เพิ่ม {names} ลงคิวแล้ว"


async def do_stop(guild: discord.Guild):
    player = _player(guild)
    if not player:
        return "บอทไม่ได้อยู่ในห้องเสียงอยู่แล้ว"
    try:
        player.queue.clear()
    except Exception:
        pass
    await player.stop()
    return "⏹️ หยุดเพลง + ล้างคิวแล้ว"


async def do_skip(guild: discord.Guild) -> str:
    player = _player(guild)
    if not player or (not player.playing and not player.paused):
        raise ValueError("ตอนนี้ไม่มีเพลงเล่นอยู่")
    try:
        nxt = player.queue.get()
    except Exception:
        await player.stop()
        return "⏭️ ข้ามแล้ว — คิวหมดแล้ว"
    await player.play(nxt)
    return f"⏭️ ข้ามไป **{_title(nxt)}**"


async def do_queue(guild: discord.Guild) -> str:
    player = _player(guild)
    if not player:
        return "บอทไม่ได้อยู่ในห้องเสียง"
    try:
        upcoming = list(player.queue)[:10]
        total = len(player.queue)
    except TypeError:
        return "คิวว่าง"
    lines = []
    if player.current:
        lines.append(f"▶️ {_title(player.current)}")
    for i, t in enumerate(upcoming, 1):
        lines.append(f"{i}. {_title(t)}")
    if total > len(upcoming):
        lines.append(f"…และอีก {total - len(upcoming)} เพลง")
    return "\n".join(lines) or "คิวว่าง"


async def search_choices(query: str, limit: int = 8) -> list[tuple[str, str]]:
    """(label, value) pairs for /play autocomplete. Empty on any failure."""
    if len(query.strip()) < 2:
        return []
    try:
        await _wait_node(timeout=3.0)  # autocomplete ต้องตอบใน 3 วิ
    except Exception:
        return []
    try:
        tracks = await wavelink.Playable.search(query.strip(), source="ytsearch")
    except Exception:
        return []
    if isinstance(tracks, wavelink.Playlist):
        tracks = tracks.tracks[:limit]
    out = []
    for t in (tracks or [])[:limit]:
        label = _title(t)[:100]
        uri = getattr(t, "uri", "") or ""
        value = uri if 0 < len(uri) <= 100 else getattr(t, "title", label)[:100]
        out.append((label, value))
    return out
