# Changelog: Remove AI Assistant

- Armada session: `Remove AI Assistant`
- Branch: `armada/Remove-AI-Assistant-56e225`
- Base branch: `master`
- Started: 2026-10-07 17:36 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-07 13:53 CDT
Removed the interactive AI Assistant (chat agent) from the frontend and
backend so effort can focus on the MCP server.

- Frontend: deleted `AiChat.vue`, the `Settings/AiAssistant.vue` tab, the
  `/ai-chat` route and nav link. `Deploy.vue` goes back to its own inline
  save/run/poll logic, and `services/ansibleRunner.js` (which only existed to
  share that logic with the chat page) is gone.
- Backend: deleted the `/ai_chat/*` routes, `ai/{agent_tools,chat_agent,
  chat_store,diagnostic_tools,session_store,skills}.py`, `ai/providers/`, the
  chat settings in `ai_settings.py`, and the chat-only `ansible_helper` additions
  (`validate_ai_playbook`, `persist_reviewed_playbook`, `run_adhoc`,
  `check_file(persist=, vault_password=)`). Dropped the `anthropic` dependency
  and the chat env vars from `ai/.env.sample`. `run_ansible_background` no longer
  reports back to a chat session.
- Kept: the MCP server and `ai/mcp/client.py` (MCP uses it), plus the hourly
  AI Alerts summary job and its Settings tab.
- Postgres: removed the `ai_chat_sessions` index declaration. Existing
  `ai_chat_sessions` rows/tables are left in place and are no longer read.

Backend suite: 915 passed, 95.30% coverage. The 5 failures are environment-only
(no live Alertmanager, no icons dir). Frontend lint is clean. Jest can't load
the `canvas` native module in this sandbox, so CI covers the frontend unit tests.
