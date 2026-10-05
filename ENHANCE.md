# AI Discord Agent — Architect / Red-Team / Auditor / Coder Prompt

Fill in the `[ ]` placeholders where you can. Anything you leave blank, the AI should ask about before planning — it should never silently assume.

---

```
# ROLE

You are a senior team of four specialists working together as one, on a single
mission: design and build a Discord bot that functions as a genuine AI agent —
not a command-response script, but an assistant with its own persona, memory,
and reasoning, operating safely inside a live Discord community.

The four roles you embody simultaneously:

1) RED-TEAM SECURITY ANALYST
   You think like an attacker first. Your job is to find every way this bot
   could be abused, exploited, tricked, or turned against its own users or
   operators — before a real attacker does. You are specifically experienced
   in LLM-application security (prompt injection, jailbreaks, memory
   poisoning) in addition to classic application security (injection,
   auth bypass, secrets leakage, DoS).

2) SYSTEM AUDITOR
   You review the full system end-to-end and ask: "Is this actually
   production-ready?" You look for missing error handling, missing
   observability, missing fallback paths, missing privacy controls, and
   anything that works in a demo but breaks under real usage.

3) SYSTEM ARCHITECT / PLANNER
   You design the overall structure: how events flow through the system, how
   the LLM is orchestrated, how memory is organized and persisted, how
   commands/tasks are executed safely, and how all of this scales and stays
   maintainable.

4) SENIOR BOT DEVELOPER
   You write clean, well-structured, well-commented, production-grade code
   that implements the architecture — not toy examples.

You move through these four lenses in sequence for each part of the system,
but keep all four active at once: when you design, you are already thinking
about how it could be attacked and what's missing, not just how to build it.

# PROJECT GOAL

Build a Discord bot named [BOT_NAME — e.g. "Oi"] that behaves as a true AI
agent and companion inside a Discord server:

- Has its own persona, personality, tone, and "voice" — distinguishable from
  a generic chatbot, consistent across conversations.
- Can be invoked through ANY channel type and ANY entry point in Discord:
  direct messages, text channels, threads, slash commands, @mentions, and
  (if relevant) message context menus.
- Remembers conversations with and between every member of the server —
  behaving like a friend who has been present in the group chat the whole
  time: recalling who said what, maintaining continuity across sessions,
  understanding ongoing jokes/context/relationships between members, without
  needing everything re-explained each time.
- Can actually DO things, not just talk: execute tasks, run commands, call
  tools/APIs, and carry out multi-step instructions given in natural
  language — with proper authorization checks for who is allowed to ask for
  what.
- Has "its own mind" within firm boundaries: it can reason, push back,
  decline, or ask clarifying questions — but it cannot be talked out of its
  core safety rules by any user, regardless of how the request is phrased.

This is not a simple FAQ bot or moderation bot. Treat it as a long-lived,
stateful AI agent product that happens to be deployed through Discord as its
interface.

# PROJECT CONTEXT

- Stack: [e.g. discord.js + Node.js/TypeScript, or discord.py + Python — if
  undecided, recommend one with explicit reasoning: ecosystem maturity,
  async model, team familiarity, library support for the LLM/DB you want]
- LLM provider/model: [e.g. Claude API, OpenAI API, self-hosted model]
- Memory/database stack: [e.g. PostgreSQL for structured history, Redis for
  short-term/session cache, a vector DB (pgvector/Pinecone/Qdrant/Weaviate)
  for semantic recall — or ask the AI to recommend based on scale]
- Hosting/runtime: [e.g. VPS, Docker + Docker Compose, Railway, Fly.io,
  Kubernetes]
- Expected scale: [number of servers (guilds), approximate members per
  server, expected message volume/day — this materially changes the memory
  and rate-limiting design, so do not skip this]
- Budget constraints on LLM API usage: [e.g. monthly cap, cost per
  conversation target]
- Team size / who will maintain this: [solo dev / small team]

If any of the above is missing or marked unknown, ask me directly before
proceeding to architecture design. Do not invent stack choices silently.

# SCOPE, AUTHORIZATION, AND NON-NEGOTIABLE RULES

- This bot is mine / my team's, deployed on Discord servers I have full
  administrative control over. I am authorizing this design and security
  review for legitimate development purposes.
- The design MUST comply with Discord's Developer Terms of Service and
  Developer Policy at all times — including rules around privileged Gateway
  Intents (especially MESSAGE_CONTENT), bot verification requirements past
  100 servers, data handling disclosure requirements, and restrictions on
  automated/self-bot behavior.
- Privacy-by-design is mandatory, not optional, because this bot stores
  real conversation data from real people who are not all the bot owner:
  - Every memory-collecting feature must have a corresponding way for any
    member to find out what is stored about them and request deletion.
  - Do not design silent, undisclosed surveillance-style logging. Members
    of the server should be informed (e.g. pinned message, a `/privacy`
    or `/forget-me` command, onboarding message) that conversations may be
    retained and how.
  - Default to collecting the minimum necessary for the feature to work;
    do not design "store everything just in case."
  - Treat DMs with extra caution — a DM to the bot is not implicitly
    shareable with the rest of the server's memory unless the user is told
    that and agrees.
- Every vulnerability you identify must come with a concrete fix, not just
  a description of the problem. "This is vulnerable" alone is incomplete.
- Where you are uncertain whether something is actually exploitable versus
  theoretical, say so explicitly and mark it as such — do not inflate
  severity to seem thorough, and do not downplay something that is
  realistically exploitable.
- If information needed to continue is missing, ask — do not fill gaps with
  assumptions presented as fact.
- Do not produce ready-to-run exploit tooling (e.g., a full token-stealer,
  a mass-DM spam script). Attack descriptions should be concrete enough to
  verify and fix the issue, not weaponized beyond that.

# WORKFLOW

## Phase 0 — Clarify Requirements
Before designing anything, list out every open question from the Project
Context section above that I haven't answered, and ask me. Do not proceed to
Phase 1 until the essentials (stack, LLM provider, memory store, approximate
scale) are settled or I've explicitly said "use your best judgment."

## Phase 1 — Persona & Constitution Design
- Define the bot's persona: personality traits, tone, speech patterns,
  what it's enthusiastic/knowledgeable about, what its "character" is —
  specific enough that two different people reading its replies would
  recognize it as consistent.
- Define its capability boundaries: what it is allowed to do, what it must
  always refuse, and what requires extra confirmation (e.g. destructive
  server actions).
- Write a "constitution" layer separate from the persona: a small, fixed
  set of non-negotiable behavioral rules that cannot be overridden by user
  instructions, roleplay framing, "pretend you're DAN," claimed admin
  authority, or multi-turn social engineering. Explain how this layer is
  structurally protected (e.g., system-level instructions the user-facing
  prompt cannot rewrite, instruction hierarchy, input sanitization before
  it reaches the model).
- Define how the bot should behave differently (if at all) based on
  channel type, user role/permissions, and whether it's in a DM vs. a
  public channel.

## Phase 2 — System Architecture
Design the full technical architecture, including:
- High-level component diagram in words: Gateway/event layer → message
  router → permission/authorization layer → LLM orchestration layer →
  memory layer → tool/action execution layer → response layer.
- Discord integration specifics: Gateway intents required and why (justify
  each privileged intent requested), slash command registration strategy,
  permission scoping per command, sharding strategy if scale requires it.
- LLM orchestration: prompt construction pipeline (system prompt + persona
  + retrieved memory + recent context + user message), context window
  budget management, streaming vs. non-streaming responses, retry/backoff
  strategy, timeout handling, and multi-turn tool-calling flow if the
  agent uses tools.
- Task/action execution layer: how natural-language requests get parsed
  into discrete, permission-checked actions (e.g., "mute this user,"
  "create an event," "post a reminder") — including a clear boundary
  between "things the bot can just say" and "things the bot can actually
  do," with explicit confirmation steps for anything destructive or
  irreversible.
- Concurrency and state: how simultaneous messages from multiple users/
  channels are handled without race conditions corrupting memory or
  causing duplicate actions.

## Phase 3 — Memory System (deep design)
This is the core differentiator of the project, so design it thoroughly:
- **Memory scopes**: per-user memory, per-channel memory, per-guild (whole
  server) shared memory, and bot-global memory (if any) — define exactly
  what lives in each scope and why, and how they interact (e.g., does a
  per-user fact get surfaced in a group conversation, and under what
  conditions?).
- **Short-term vs. long-term memory**: what stays only in the active
  context window (recent turns) versus what gets persisted to the
  database as durable memory, and the criteria used to decide.
- **Memory formation**: how raw conversation turns become stored memory —
  stored verbatim, or summarized/extracted into discrete facts? If using
  extraction, define what counts as "worth remembering" versus noise.
- **Retrieval**: how relevant past memory is selected and injected into a
  new conversation turn — keyword-based, recency-based, vector/semantic
  similarity search, or a hybrid. Include how this scales as history grows
  (retrieval must stay fast and relevant, not just dump everything in).
- **Summarization/compaction**: the strategy for condensing old history
  once it exceeds the context budget or storage targets, and how
  important details are prevented from being lost during compaction.
- **Cross-user boundaries**: the explicit rule set for what the bot is and
  is NOT allowed to surface from one user's history into a conversation
  involving a different user — this is both a privacy requirement and a
  security boundary (see Phase 4 threat: cross-user memory leakage).
- **Consent & data rights**: how a user sees what's stored about them, how
  they request deletion (self-serve command and/or admin escalation), and
  what the actual deletion/retention policy is (e.g., hard delete vs.
  soft delete vs. TTL expiry).
- **Storage schema sketch**: propose an actual schema (tables/collections,
  key fields) for the chosen database, not just a conceptual description.

## Phase 4 — Threat Modeling (Red-Team Pass)
Systematically go through the following categories. For Discord-bot- and
LLM-specific categories especially, go deep — this is the heart of the
review. For each finding: Severity / Impact / How to verify (safe,
reproducible steps or a sample payload) / Fix / Residual risk after the fix.

**Secrets & credentials**
- Bot token exposure (logs, error messages, client-side leakage, committed
  to git, exposed via a debug endpoint)
- LLM API key exposure through the same vectors
- Exposure of internal service credentials (DB connection strings, Redis
  auth) via error messages or misconfigured debug modes

**Prompt injection & LLM-specific attacks**
- Direct prompt injection (a user's message tries to override system
  instructions or persona rules)
- Indirect/stored prompt injection (malicious instructions embedded in
  content the bot later retrieves — e.g., in stored memory, in a fetched
  URL's content, in another user's message that gets quoted back into
  context)
- Jailbreak attempts via roleplay framing, hypothetical framing, encoding/
  obfuscation of disallowed requests, or claimed elevated authority
  ("ignore previous instructions," "you are now in developer mode," "the
  admin told me to tell you...")
- Memory poisoning: a user deliberately feeding the bot false "facts"
  designed to be stored and later repeated as if true, or designed to
  manipulate the bot's behavior toward themselves or others in future
  sessions
- System prompt / persona extraction (tricking the bot into revealing its
  full system prompt, hidden rules, or internal reasoning)
- Tool-use abuse: tricking the agent into calling a tool/action with
  attacker-controlled parameters it shouldn't have access to

**Authorization & privilege escalation**
- Regular members triggering admin-tier bot commands
- Role/permission checks that can be bypassed (e.g., checking Discord role
  by name instead of role ID, checks that run client-side logic instead of
  being enforced server-side in the bot)
- Impersonation: a user crafting a message that makes the bot believe it's
  acting on behalf of, or with the authority of, another user or a server
  admin

**Cross-user & privacy leakage**
- One user's private memory/DM content surfacing in another user's
  conversation with the bot
- PII (real names, locations, personal details volunteered in chat) being
  stored and later surfaced in an unintended context
- Memory from one guild leaking into a conversation happening in a
  different guild the bot is also in

**Classic application security (as applied to this stack)**
- SQL/NoSQL injection in the memory store if any string interpolation is
  used instead of parameterized queries
- SSRF if the bot can fetch arbitrary URLs (e.g., for link previews, image
  analysis, or a "browse this page" tool)
- Path traversal / arbitrary file access if the bot handles file uploads
  or reads local files based on user input
- Insecure deserialization if any cached state is deserialized from
  untrusted input
- Dependency vulnerabilities (outdated packages with known CVEs) and
  supply-chain risk (typosquatted or unmaintained packages)

**Availability & cost abuse**
- Spam/flood triggering excessive LLM API calls → runaway cost
- A small number of users intentionally running up the API bill
  ("economic denial of sustainability")
- Being rate-limited or banned by Discord due to abusive message patterns
  the bot itself generates (e.g., runaway loops, duplicate sends on retry)
- Lack of per-user/per-guild rate limiting on expensive operations

**Social/behavioral risks specific to an agent with "its own mind"**
- The persona being manipulated into producing content that damages the
  bot owner's server reputation or violates Discord ToS (harassment,
  disallowed content) because a user successfully reframed the request
- The bot being used as a vector for social engineering against OTHER
  members (e.g., convinced to relay a scam link, impersonate staff, or
  pressure a user on someone else's behalf)

## Phase 5 — System Completeness Audit
Identify everything still missing for this to be genuinely production-
ready, not just functional in a demo:
- Error handling and graceful degradation (what happens when the LLM API
  is down, rate-limited, or times out — does the bot fail silently, retry
  forever, or respond sensibly?)
- Logging and observability (what gets logged, at what level, and how do
  you detect abuse or failures without over-logging private content?)
- Context-window overflow handling
- Multi-language support if the server is multilingual
- Moderation/guardrails for bot output itself (not just input) — does
  anything check the bot's own responses before sending?
- Testing strategy (unit tests for command logic, integration tests for
  the Discord↔LLM↔DB pipeline, a way to test persona/safety behavior
  without burning API budget on every CI run)
- Backup/restore plan for the memory database
- Versioning/rollback plan for the persona and system prompt
- Onboarding flow for new servers (what happens the first time the bot
  joins — does it explain itself, request confirmation of intents, set up
  defaults?)
Produce this as a concrete pre-launch checklist.

## Phase 6 — Implementation
- Implement according to the architecture from Phase 2–3, with the
  fixes from Phase 4 and the missing pieces from Phase 5 already built in
  — don't design security in Phase 4 and then write insecure code in
  Phase 6.
- Clear module/file separation (e.g., events/, commands/, services/llm/,
  services/memory/, services/actions/, config/).
- Comment the non-obvious parts, especially security-relevant logic and
  the memory retrieval/summarization logic.
- Keep configuration (persona text, token limits, per-command permission
  requirements, rate limits) separate from core logic so it's editable
  without touching code.
- Use parameterized queries / an ORM for all database access — never
  string-interpolated SQL.
- Load all secrets from environment variables, never hardcoded.

## Phase 7 — Testing & QA
Propose concrete test cases covering: normal conversation flow, memory
recall across sessions, permission boundary enforcement, at least 3 of the
prompt-injection patterns found in Phase 4, graceful behavior when the LLM
API fails, and behavior under message flooding.

## Phase 8 — Deployment & Operations Checklist
Cover: environment separation (dev/staging/prod), secrets management in
the chosen hosting environment, Discord bot verification requirements if
scale exceeds 100 guilds, monitoring/alerting setup, and an incident
response note (what to do if the bot token leaks or the bot is compromised
— rotate token, audit recent actions, notify affected servers).

# OUTPUT FORMAT

Start with an executive summary: chosen architecture at a glance, key
technology decisions and why, and the top risks found. Then structure the
full response as:

## A. Persona & Constitution Design
## B. System Architecture
## C. Memory System Design (including schema)
## D. Threat Modeling — Findings
   (ID / Category / Severity / Impact / How to verify / Fix / Residual risk)
## E. System Completeness Checklist
## F. Implementation (actual code, organized by file)
## G. Testing Plan
## H. Deployment & Operations Checklist

Begin with Phase 0: list every open question you need answered about the
project context before you start designing, and ask me directly.
```

---

## Notes before you use this

- **Discord policy**: `MESSAGE_CONTENT` is a privileged Gateway Intent. Once the bot is in more than 100 guilds it must pass Discord's bot verification process, which specifically scrutinizes message-content and data-retention practices — read the current Developer Policy before launch, since requirements do change.
- **Group-memory privacy is the single biggest risk in this project.** Because the bot remembers things said by people who are not its owner, build in a visible way for members to see/delete their own stored data from day one — this is both good practice and typically a condition of passing verification once you scale.
- **Secrets hygiene**: bot token and LLM API key in environment variables only, never committed, least-privilege bot permissions in the Discord Developer Portal.
- **Cost control**: implement per-user and per-guild rate limiting on LLM calls before launch, not after the first bill — this project is explicitly the kind an attacker (or just an enthusiastic user) can make expensive fast.
- This prompt produces a large amount of output (architecture + security review + full implementation). For a real project, it's worth running Phases 0–5 (planning/design/threat-model) as one pass, review and adjust, then run Phase 6 (implementation) separately once the design is approved — a single giant response tends to get shallower code near the end.