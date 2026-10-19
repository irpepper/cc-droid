---
description: Show or set the cc-droid sound volume, from 0 to 1.
argument-hint: "[0-1]"
disable-model-invocation: true
allowed-tools:
  - Bash(${CLAUDE_PLUGIN_ROOT}/bin/cc-droid volume *)
  - Bash(${CLAUDE_PLUGIN_ROOT}/bin/cc-droid volume)
  - Bash(${CLAUDE_PLUGIN_ROOT}/bin/cc-droid play done)
---

The user wants to check or change the cc-droid volume. Their argument: "$ARGUMENTS"

- If the argument is empty, run `${CLAUDE_PLUGIN_ROOT}/bin/cc-droid volume` with the Bash tool and report the current volume in one line.
- If it's a number from 0 to 1, or a percentage you can convert to one (50% is 0.5), run `${CLAUDE_PLUGIN_ROOT}/bin/cc-droid volume <number>` with the Bash tool, then play one sound at the new level with `${CLAUDE_PLUGIN_ROOT}/bin/cc-droid play done`, and confirm the new volume in one line.
- Otherwise, say in one line that the volume is a number from 0 to 1, for example `/cc-droid:volume 0.5`.
