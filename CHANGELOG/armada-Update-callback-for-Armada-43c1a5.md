# Changelog: Update callback for Armada

- Armada session: `Update callback for Armada`
- Branch: `armada/Update-callback-for-Armada-43c1a5`
- Base branch: `master`
- Started: 2026-11-11 04:59 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-10 23:10 CST
Agent conversations now report to Armada. The MCP server reads the session's `X-Armada-Callback` header in `mcp_start_conversation`, `mcp_send_message` and `mcp_prepare_deployment`. It accepts only a `https?://host/api/session-callback/<64 hex>` URL and saves it on the conversation (`armada_callback`, `$set`, so a newer session takes over) before the ask is posted, including when staging creates the conversation. Each agent question or deployment raises an Armada request linking to the same page as the Alertmanager alert. The tool results now carry `armada_request: true|false`, and the docstrings tell the agent to end its turn and wait for "[Armada] Request completed". A human reply, a decline, a run result or any close finishes every outstanding request (a launch alone does not). That includes an agent closing the conversation itself, which the spec didn't cover, since nothing else would ever clear those requests. The request ids are kept with the URL they went to (`armada_requests`), changed through a compare-and-swap on the whole list because the DB adapters support neither `$addToSet` nor `find_one_and_update`. That keeps parallel answers from finishing twice and keeps a racing ask from being lost. Both calls are best effort (10 s timeout, logged without the URL). Neither field is ever returned by `get_conversation`, `list_conversations` or `check_response`. The Alertmanager alert is still sent alongside Armada's. Without the header nothing changes.
