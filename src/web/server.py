"""Admin dashboard — implements DESIGN.md (necessary parts only).

Stdlib only (runs in a daemon thread beside the Discord client):
  GET  /              dashboard (single HTML page, DESIGN.md tokens)
  GET  /api/status    {online, model, keys, cooling_down, guilds, latency_ms, uptime}
  GET  /api/logs?after=N   {lines: [...], cursor: N}  (ring buffer, INFO+)
  POST /api/model     {name}   switch backbone at runtime (auth)
  POST /api/keys      {keys}   append API keys at runtime (auth)

Auth: X-Admin-Token header == ADMIN_TOKEN env. No token configured → writes 403.
"""

import json
import logging
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("gemini-bot")

STARTED_AT = time.time()
LOG_BUFFER: deque = deque(maxlen=400)
ADMIN_TOKEN = ""
CLIENT = None  # discord.Client, set by start()

MODEL_CHOICES = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "allam-2-7b",
    "qwen/qwen3.8-27b",
]

# Quota hints from the project's rate-limits page (RPM · RPD), shown in /models list.
# (2.x family removed — Google retired it for new users, points to 3.5-flash-lite.)
MODEL_QUOTAS = {
    "gemini-3.5-flash-lite": "15 RPM · 500 RPD ⭐ highest",
    "gemini-3.1-flash-lite": "15 RPM · 500 RPD",
    "gemini-3.8-flash": "5 RPM · 20 RPD",
    "gemini-3-flash": "5 RPM · 20 RPD",
    "gemini-3.5-flash": "5 RPM · 20 RPD",
    "gemini-3.6-flash": "5 RPM · 20 RPD",
    "gemini-3.7-flash": "5 RPM · 20 RPD",
    "openai/gpt-oss-120b": "Groq · 30 RPM · 1K RPD · needs GROQ_API_KEY",
    "openai/gpt-oss-20b": "Groq · 30 RPM · 1K RPD · needs GROQ_API_KEY",
    "allam-2-7b": "Groq · 30 RPM · 7K RPD · needs GROQ_API_KEY",
    "qwen/qwen3.8-27b": "Groq · 30 RPM · 1K RPD · needs GROQ_API_KEY",
}


class _RingHandler(logging.Handler):
    def emit(self, record):
        try:
            LOG_BUFFER.append(self.format(record))
        except Exception:
            pass


def _uptime() -> str:
    s = int(time.time() - STARTED_AT)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{d}d {h}h {m}m" if d else (f"{h}h {m}m" if h else f"{m}m {s}s")


def _status() -> dict:
    from src.core import llm

    try:
        s = llm.get_client().status()
    except RuntimeError:
        s = {"model": "?", "keys": 0, "cooling_down": 0}
    online = CLIENT is not None and CLIENT.user is not None
    latency = round((CLIENT.latency or 0) * 1000) if online else None
    return {
        "online": online,
        "bot": str(CLIENT.user) if online else None,
        **s,
        "guilds": len(CLIENT.guilds) if online else 0,
        "latency_ms": latency,
        "uptime": _uptime(),
        "deploy": _deploy_info(),
    }


def _deploy_info() -> dict:
    """CI/CD provenance from Railway-injected env (free, no token needed)."""
    import os

    sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")[:7]
    return {
        "provider": "railway" if os.getenv("RAILWAY_ENVIRONMENT_NAME") else "other/local",
        "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "–"),
        "service": os.getenv("RAILWAY_SERVICE_NAME", "–"),
        "commit": sha or "–",
        "deployment": (os.getenv("RAILWAY_DEPLOYMENT_ID", "") or "–")[:12],
    }


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DiscordBot Server</title>
<style>
:root{--tx:#1A1A1A;--tx2:#5F6368;--bg:#fff;--bd:#E0E0E0;--r:8px;--mono:"SF Mono","Fira Code",Consolas,monospace}
*{box-sizing:border-box}body{font-family:Roboto,-apple-system,"Segoe UI",Arial,sans-serif;color:var(--tx);background:var(--bg);margin:0;padding:32px;max-width:1100px}
.hrow{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
h1{font-size:26px;margin:0;display:inline}
.pill{display:inline-block;background:#F1F1F1;border-radius:999px;padding:4px 12px;font-size:13px;font-weight:500;margin-left:12px;vertical-align:middle}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#9AA0A6;margin-right:6px}
.dot.on{background:#188038}.dot.off{background:#D93025}
.btn{background:#fff;color:var(--tx);border:1px solid var(--bd);border-radius:var(--r);padding:8px 14px;font-size:14px;cursor:pointer}
.btn:hover{border-color:var(--tx)}
select.btn,input.txt{appearance:none;-webkit-appearance:none}
input.txt{border:1px solid var(--bd);border-radius:var(--r);padding:8px 10px;font-size:14px;width:280px}
.metrics{display:flex;gap:32px;flex-wrap:wrap;margin:24px 0 8px;padding:0;list-style:none}
.metrics li{min-width:140px}.metrics .k{font-size:13px;color:var(--tx2)}.metrics .v{font-size:16px;font-weight:500}
.sec{font-size:17px;font-weight:700;margin:28px 0 4px}.sub{font-size:13px;color:var(--tx2);margin:0 0 12px}
.term{border:1px solid var(--bd);border-radius:var(--r);overflow:hidden}
.term-h{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid var(--bd);font-size:14px;font-weight:500}
#logbody{background:#0D0D0D;color:#C8C8C8;font-family:var(--mono);font-size:13px;line-height:1.55;height:380px;overflow-y:auto;padding:12px 14px;white-space:pre-wrap;word-break:break-all}
#logbody .cursor{display:inline-block;width:8px;height:15px;background:#C8C8C8;vertical-align:-2px;animation:blink 1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0}
.hint{font-size:13px;color:var(--tx2)}
table.tbl{border-collapse:collapse;font-size:13px;margin:8px 0;width:100%}
table.tbl th,table.tbl td{border:1px solid var(--bd);padding:6px 10px;text-align:left}
table.tbl th{background:#F8F9FA;font-weight:500}
.mono{font-family:var(--mono);font-size:12px}
</style></head><body>
<div class="hrow">
<div><h1>DiscordBot Server</h1><span class="pill"><span id="dot" class="dot"></span><span id="state">…</span></span></div>
<div class="row" style="margin:0">
<select id="model" class="btn"></select>
<button class="btn" onclick="switchModel()">Switch model</button>
</div></div>
<ul class="metrics">
<li><div class="k">Model</div><div class="v" id="mModel">–</div></li>
<li><div class="k">API keys</div><div class="v" id="mKeys">–</div></li>
<li><div class="k">Servers</div><div class="v" id="mGuilds">–</div></li>
<li><div class="k">Latency</div><div class="v" id="mPing">–</div></li>
<li><div class="k">Uptime</div><div class="v" id="mUp">–</div></li>
</ul>
<div class="sec">API key</div>
<p class="sub">Append keys at runtime (rotation picks them up immediately).</p>
<div class="row"><input id="key" class="txt" type="password" placeholder="AIza… (comma-separated for many)">
<button class="btn" onclick="addKey()">Add / Update API key</button></div>
<div class="sec">LLM usage</div>
<p class="sub hint">Counted locally since boot (resets on restart). Keys shown by index only — values never leave the server.</p>
<table class="tbl"><thead><tr><th>Model</th><th>Req</th><th>OK</th><th>Err</th><th>In tok</th><th>Out tok</th><th>Last error</th></tr></thead>
<tbody id="usage"></tbody></table>
<table class="tbl"><thead><tr><th>Key</th><th>Req</th><th>OK</th><th>Err</th></tr></thead>
<tbody id="keys"></tbody></table>
<div class="sec">Deploy</div>
<p class="sub hint">CI/CD provenance from Railway env (commit live now). Metered $/CPU needs a Railway API token — not wired.</p>
<div id="deploy" class="mono"></div>
<div class="sec">Server Log</div>
<p class="sub hint">Live log stream, newest at the bottom.</p>
<div class="term"><div class="term-h"><span>&gt;_ Server Log</span><span id="livedot" class="dot"></span></div>
<div id="logbody"></div></div>
<script>
let token=localStorage.getItem("adm")||"";
function needToken(){if(!token){token=prompt("Admin token:")||"";localStorage.setItem("adm",token);}return token;}
async function api(p,o){o=o||{};o.headers=Object.assign({"X-Admin-Token":token},o.headers||{});
let r=await fetch(p,o);if(r.status===403){token="";localStorage.removeItem("adm");needToken();throw new Error("forbidden");}
return r.json();}
async function status(){let s=await api("/api/status");
document.getElementById("dot").className="dot "+(s.online?"on":"off");
document.getElementById("state").textContent=s.online?("Online • "+(s.bot||"")):"Offline";
document.getElementById("livedot").className="dot "+(s.online?"on":"off");
mModel.textContent=s.model;mKeys.textContent=s.keys+(s.cooling_down?" ("+s.cooling_down+" cooling)":"");
mGuilds.textContent=s.guilds;mPing.textContent=s.latency_ms==null?"–":s.latency_ms+" ms";mUp.textContent=s.uptime;
let ub=document.getElementById("usage");ub.innerHTML="";
Object.entries(s.usage||{}).forEach(([m,u])=>{let tr=document.createElement("tr");
tr.innerHTML="<td></td><td></td><td></td><td></td><td></td><td></td><td></td>";
let c=tr.children;c[0].textContent=m+(m===s.model?" ✓":"");c[1].textContent=u.requests;c[2].textContent=u.ok;
c[3].textContent=u.errors;c[4].textContent=u.in_tokens;c[5].textContent=u.out_tokens;
c[6].textContent=u.last_error||"–";ub.appendChild(tr);});
let kb=document.getElementById("keys");kb.innerHTML="";
(s.key_usage||[]).forEach((k,i)=>{let tr=document.createElement("tr");
tr.innerHTML="<td></td><td></td><td></td><td></td>";let c=tr.children;
c[0].textContent="#"+(i+1);c[1].textContent=k.requests;c[2].textContent=k.ok;c[3].textContent=k.errors;
kb.appendChild(tr);});
let d=s.deploy||{};document.getElementById("deploy").textContent=
"provider: "+(d.provider||"–")+" | env: "+(d.environment||"–")+" | service: "+(d.service||"–")+
" | commit: "+(d.commit||"–")+" | deployment: "+(d.deployment||"–");
let sel=document.getElementById("model");
if(!sel.options.length){MODELS.forEach(m=>{let o=document.createElement("option");o.value=o.textContent=m;sel.appendChild(o);});}
if(MODELS.includes(s.model))sel.value=s.model;}
let cursor=0;
async function logs(){let d=await api("/api/logs?after="+cursor);cursor=d.cursor;
let b=document.getElementById("logbody");
d.lines.forEach(l=>{let div=document.createElement("div");div.textContent=l;b.appendChild(div);});
while(b.children.length>400)b.removeChild(b.firstChild);
b.scrollTop=b.scrollHeight;}
async function switchModel(){needToken();let m=document.getElementById("model").value;
await api("/api/model",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:m})});
status();}
async function addKey(){needToken();let k=document.getElementById("key").value.trim();if(!k)return;
let d=await api("/api/keys",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({keys:k})});
alert(d.added?("Added "+d.added+" key(s), total "+d.total):"Key already exists");
document.getElementById("key").value="";status();}
const MODELS=MODELS_PLACEHOLDER;
status();logs();setInterval(status,5000);setInterval(logs,2000);
</script></body></html>"""

PAGE = PAGE.replace("MODELS_PLACEHOLDER", json.dumps(MODEL_CHOICES))


class _Handler(BaseHTTPRequestHandler):
    server_version = "BotAdmin/1"

    def log_message(self, *a):
        pass

    def _send(self, code: int, obj, ctype="application/json"):
        body = obj.encode() if isinstance(obj, str) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        return bool(ADMIN_TOKEN) and self.headers.get("X-Admin-Token") == ADMIN_TOKEN

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            return self._send(200, PAGE, "text/html")
        if self.path == "/api/status":
            return self._send(200, _status())
        if self.path.startswith("/api/logs"):
            try:
                after = int(self.path.split("after=")[1].split("&")[0])
            except (IndexError, ValueError):
                after = 0
            lines = list(LOG_BUFFER)
            return self._send(200, {"lines": lines[after:], "cursor": len(lines)})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._authed():
            msg = "admin token required" if ADMIN_TOKEN else "set ADMIN_TOKEN env first"
            return self._send(403, {"error": msg})
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "bad json"})
        from src.core import llm

        if self.path == "/api/model":
            name = (data.get("name") or "").strip()
            if not name:
                return self._send(400, {"error": "name required"})
            llm.get_client().set_model(name)
            return self._send(200, {"ok": True, **llm.get_client().status()})
        if self.path == "/api/keys":
            keys = [k.strip() for k in str(data.get("keys", "")).split(",") if k.strip()]
            if not keys:
                return self._send(400, {"error": "keys required"})
            added = llm.get_client().add_keys(keys)
            return self._send(200, {"ok": True, "added": added,
                                   "total": llm.get_client().status()["keys"]})
        return self._send(404, {"error": "not found"})


def start(client, port: int, admin_token: str):
    """Attach log capture + serve dashboard in a daemon thread."""
    global CLIENT, ADMIN_TOKEN
    CLIENT = client
    ADMIN_TOKEN = admin_token or ""
    root = logging.getLogger()
    handler = _RingHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    root.addHandler(handler)
    srv = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True, name="web-admin")
    t.start()
    log.info(f"Admin dashboard on :{port} (auth {'on' if ADMIN_TOKEN else 'OFF — set ADMIN_TOKEN'})")
    return srv
