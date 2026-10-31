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
