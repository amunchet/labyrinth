# Changelog: MCP Ansible conversation

- Armada session: `MCP Ansible conversation`
- Branch: `armada/MCP-Ansible-conversation-62a37b`
- Base branch: `master`
- Started: 2026-10-31 22:52 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-31 18:06 CDT
Agent conversations, backend and MCP. A conversation (`conversations` table)
records one piece of agent work: its messages and questions, the deployments it
staged, the human's replies/declines, and the results of runs the human
launched. Every MCP-staged deployment now belongs to one, and a run launched
from it posts its outcome back in. New MCP tools `mcp_start_conversation`,
`mcp_send_message` (with `needs_response` for questions),
`mcp_wait_for_response` (returns on the human's turn or a finished run; holds a
DB slot only per 5s check), `mcp_get_conversation`, `mcp_list_conversations`,
`mcp_close_conversation`. A question or staged deployment marks the
conversation as waiting on the human and raises an "Agent needs a response"
Alertmanager alert (best effort). Staging may leave the become file for the
human to pick, and the human may swap it at deploy time. New admin routes:
`/conversations/[waiting]`, `/conversation/<id>` (+ `/reply`, `/close`),
`/ansible_request/<id>/decline`. The agent still never runs anything: it
stages and waits for a person with the vault password. Also commits the
Flagship's move of the Armada session policy out of CLAUDE.md.

## 2026-10-31 18:13 CDT
Conversations UI. New Conversations page (`/conversations`, `/conversations/<id>`):
the history of every agent conversation, and a timeline for each one showing the
agent's messages and questions, staged deployments (status, playbook review,
"Review and deploy" deep link, Decline), launches and run results, with a reply
box and Close. It refreshes every 5s, so agent messages and run results show up
on their own. The nav gets a Conversations item with a badge counting
conversations waiting on you, polled every 30s and refreshed after each action.
The Deploy page's prepared-deployment card now has a become-file picker (preset
to the agent's choice, required when the agent left it open), links back to its
conversation, and notes when you declined it.

## 2026-10-31 18:25 CDT
The Conversations list previews a closed or declined conversation with what was
said, so the agent's closing summary or your decline reason shows, not just
"Closed".

## 2026-10-31 19:04 CDT
Fixes from reviewing PR #84. Conversation alerts now carry their deploy or
conversation link: `watcher.send_alert` had been overwriting its own `url`
parameter with the Alertmanager endpoint, so every alert's source was the
internal API. Its Alertmanager call gets a 10s timeout, since it now runs inside
MCP tool calls whose few DB slots a hung Alertmanager would hold forever. Each
ask is its own alert (`instance` = conversation/message), because a second ask
within Alertmanager's resolve timeout merged into the first and never notified.
`pending` now only changes through atomic `$push`/`$pull`, and `needs_human`
is derived on read: parallel tool calls, a forked run's result and a human
reply landing together could undo each other's changes, dropping a staged
deployment from what the human owes. The Conversations page reports a failing
poll once instead of every 5s, no longer flashes a spinner on an empty list,
says when a conversation can't be loaded, and marks a deployment dropped by
closing the conversation "Not deployed".

## 2026-11-01 01:23 CST
Fixes CodeQL alert #701 (py/reflective-xss, high) on PR #84:
`create_ansible_request` returned the submitted `conversation_id` in its
response. It now looks the conversation up once and uses the stored id from then
on, so no request value is echoed back (the project's error-response rule).
Behavior is unchanged: an unknown id is still refused with a 404 before anything
is staged.
