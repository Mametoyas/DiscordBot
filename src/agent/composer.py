"""Merge summarize output with skill results — mirrors agent/composer.js.

(No Components V2 in discord.py: skills return plain text, so compose only
carries reply + optional image URL.)
"""


def compose(summary: dict, results: list | None = None) -> dict:
    results = results or []
    image_hit = next((r for r in results
                      if r.get("status") == "success" and r.get("imageUrl")), None)
    return {
        "reply": summary.get("reply") or "",
        "replyFormat": summary.get("replyFormat") or "text",
        "imageUrl": summary.get("imageUrl") or (image_hit or {}).get("imageUrl"),
        "colorHex": summary.get("colorHex") or "#2B2D31",
        "imageStyle": summary.get("imageStyle"),
    }
