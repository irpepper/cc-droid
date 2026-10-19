---
description: Play every cc-droid sound in turn so you can hear the whole set.
disable-model-invocation: true
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/cc-droid test)
---

Run this command with the Bash tool, exactly as written:

```
${CLAUDE_PLUGIN_ROOT}/bin/cc-droid test
```

It plays each sound and prints its name as it goes. When it finishes, reply with this table and nothing else, marking any sound the output tagged "(custom)":

| Sound | When it plays |
|---|---|
| attention | Claude needs permission to use a tool |
| waiting | Claude has been idle, waiting for your next message |
| query | Claude is asking you a question or showing a form |
| done | Claude finished responding |
| task-complete | a task in the task list was completed |
| ratelimit | a turn stopped because of a rate limit |
| error | a turn stopped because of any other API error |
| tool-failure | a tool call failed |
| session-start | a session started or resumed |
| session-end | a session ended |
| subagent-start | a subagent was launched |
| subagent-stop | a subagent finished |
| compact | the conversation is about to be compacted |
