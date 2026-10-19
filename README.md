# cc-droid

A Claude Code plugin that gives your sessions a little droid voice. It chirps, knocks,
beeps and grumbles so you can tell what Claude is doing without looking at the terminal:
needs your approval, waiting on you, finished, hit an error, launched a subagent.

All 13 sounds are original and synthesized from scratch, so they're short, office-friendly
and free to share.

## Install

In Claude Code:

```
/plugin marketplace add irpepper/cc-droid
/plugin install cc-droid@cc-droid
```

Or from your shell:

```bash
claude plugin marketplace add irpepper/cc-droid
claude plugin install cc-droid@cc-droid
```

Then run `/cc-droid:test` to hear the whole set.

## What plays when

Every sound comes from the same droid, and its mood tells you the category:

| Category | Mood | Signature |
|---|---|---|
| Needs you | eager, curious | knocks or chatter that end on a rise |
| Finished | content, cheerful | a phrase that falls to rest |
| Problems | sad, grumpy, tired | falling, low, growly |
| Lifecycle | waking up, nodding off | long whistle slides; short zips for subagents |

| Sound | Plays when | What you hear |
|---|---|---|
| `attention` | Claude needs permission to use a tool | three excited chirps and a rising whistle: "hey! over here!" |
| `waiting` | Claude has been idle, waiting for your next message | two soft knocks, a pause, a curious "hm-mm?" |
| `query` | Claude asks you a question or shows a form | three firm knocks and a friendly "beep-boop" |
| `done` | Claude finished responding | a falling "dee-doo-doo" and a smiley blip: "done-zo" |
| `task-complete` | a task-list item is completed | a tiny "bip-boop" nod |
| `ratelimit` | a turn stopped on a rate limit | a drooping sigh and two sleepy hums: "need a breather" |
| `error` | a turn stopped on any other API error | a falling "uh-oh" and a grumpy raspberry |
| `tool-failure` | a tool call failed | one short drooping "bwomp" |
| `session-start` | a session starts or resumes | a whistle powering up and a "dee-dee!" hello |
| `session-end` | a session ends | a "doo-dee" goodbye and the whistle sliding down |
| `subagent-start` | a subagent is launched | a quick "zip!" up and a tiny "bip" |
| `subagent-stop` | a subagent finishes | a quick "zoop" down onto a soft "boop" |
| `compact` | the conversation is about to be compacted | a wobble that narrows to nothing: squish |

Sounds that fire constantly (done, compact, subagents) sit a few dB quieter than the rare,
important ones.

## Controls

| Command | What it does |
|---|---|
| `/cc-droid:mute` | silence everything (before a meeting) |
| `/cc-droid:unmute` | turn sounds back on |
| `/cc-droid:volume 0.5` | set the volume, 0 to 1 (no argument shows it) |
| `/cc-droid:test` | play every sound with its name |

The same controls work from your shell through `bin/cc-droid` in the plugin folder
(`cc-droid mute`, `cc-droid volume 0.4`, `cc-droid status`). `CC_DROID_MUTE=1` mutes a single
shell. Settings live in `~/.claude/cc-droid/`, so they survive plugin updates.

Too chatty? Disable the plugin's `PostToolUseFailure` hook first, since some tool calls fail
routinely. To turn the plugin off entirely: `/plugin disable cc-droid@cc-droid`.

## Use your own sounds

Put a WAV named after any sound into `~/.claude/cc-droid/sounds/` and it replaces the
built-in one: `~/.claude/cc-droid/sounds/done.wav`, and so on. No config changes.

`tools/normalize.sh` prepares clips from any format ffmpeg reads: it strips leading silence,
caps the length with a fade, matches loudness to the built-in set, and limits peaks.

```bash
./tools/normalize.sh ~/Downloads/my-clips ~/.claude/cc-droid/sounds
```

Name the source files after the sounds they replace (`done.mp3`, `attention.m4a`).
Options: `-t` loudness target in LUFS (default -20), `-m` max length in seconds (default
1.5). Needs ffmpeg.

## Regenerate or tweak the sounds

Each sound is one small, documented function in `synth/make_sounds.py`.

```bash
pip install numpy scipy
python3 synth/make_sounds.py build/raw
cp synth/offsets.txt build/raw/
./tools/normalize.sh build/raw sounds
python3 synth/distinctness.py build/raw   # flags sounds that drift too close together
```

## Notes

- Playback uses `afplay` on macOS; `pw-play`, `paplay`, `aplay` or `ffplay` on Linux; and
  PowerShell on WSL and Git Bash. Hooks run through `bash`, so native Windows needs Git Bash.
- Every hook except SessionEnd runs in the background, so sounds never slow a session down.
- Playback always exits cleanly, so a missing speaker can never block Claude from stopping.
- Sounds play only for sessions on your own machine; cloud sessions can't reach your speakers.

## License

MIT
