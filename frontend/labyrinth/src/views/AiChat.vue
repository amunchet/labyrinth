<template>
  <b-container fluid class="assistant-page">
    <b-row>
      <b-col>
        <div class="page-heading">
          <div>
            <div class="eyebrow">OPERATIONS COPILOT</div>
            <h2>AI Assistant</h2>
            <p class="text-muted mb-0">
              Investigate the network, review a proposed change, then deploy it
              to explicitly selected hosts. The assistant never chooses the
              deployment inventory.
            </p>
          </div>
          <b-button variant="outline-primary" @click="newSession">
            New session
          </b-button>
        </div>
      </b-col>
    </b-row>

    <b-row class="mt-3">
      <b-col lg="3" class="mb-3">
        <b-card class="session-panel" no-body>
          <div class="panel-title">
            <span>Sessions</span>
            <b-button size="sm" variant="link" @click="loadSessions"
              >Refresh</b-button
            >
          </div>
          <div v-if="sessions.length === 0" class="empty-panel">
            No retained sessions yet.
          </div>
          <button
            v-for="item in sessions"
            :key="item.session_id"
            class="session-item"
            :class="{ selected: item.session_id === session_id }"
            @click="resumeSession(item.session_id)"
          >
            <strong>{{ item.title || item.session_id.slice(0, 8) }}</strong>
            <small>{{ formatSessionDate(item.updated_at) }}</small>
            <small
              >{{ item.message_count || 0 }} messages
              <span v-if="item.deployment_status"
                >&middot; {{ item.deployment_status }}</span
              >
            </small>
          </button>
        </b-card>

        <b-card v-if="!session_id" class="mt-3 start-panel" no-body>
          <div class="panel-title">Start a session</div>
          <b-form @submit.prevent="startSession">
            <b-form-group label="Provider" label-for="assistant-provider">
              <b-form-select
                id="assistant-provider"
                v-model="selected_provider"
                :options="providers"
                :disabled="starting"
              />
            </b-form-group>
            <b-form-group
              label="Become vault file"
              label-for="assistant-become"
            >
              <b-form-select
                id="assistant-become"
                v-model="selected_become"
                :options="files_list.become || []"
                :disabled="starting"
              />
            </b-form-group>
            <b-form-group label="Vault password" label-for="assistant-vault">
              <b-form-input
                id="assistant-vault"
                v-model="vault_password"
                type="password"
                autocomplete="new-password"
                :disabled="starting"
              />
            </b-form-group>
            <b-form-group label="SSH key (optional)" label-for="assistant-ssh">
              <b-form-select
                id="assistant-ssh"
                v-model="selected_ssh"
                :options="['', ...(files_list.ssh || [])]"
                :disabled="starting"
              />
            </b-form-group>
            <b-form-group
              label="Deployment hosts (local only)"
              label-for="assistant-hosts"
              description="Not sent to the assistant. You will confirm these again before deployment."
            >
              <b-form-input
                id="assistant-hosts"
                v-model="host"
                placeholder="10.0.0.5, 10.0.0.6"
                :disabled="starting"
              />
            </b-form-group>
            <b-form-group
              label="Session prompt"
              label-for="assistant-session-prompt"
              description="Customize the guidance for this investigation. It is stored with the session and sent as operator guidance."
            >
              <b-form-textarea
                id="assistant-session-prompt"
                v-model="session_prompt"
                rows="4"
                :disabled="starting"
              />
            </b-form-group>
            <b-button
              type="submit"
              variant="primary"
              block
              :disabled="!canStartSession || starting"
            >
              <b-spinner v-if="starting" small class="mr-1" />
              Start investigation
            </b-button>
          </b-form>
        </b-card>
      </b-col>

      <b-col lg="9">
        <b-card v-if="!session_id" class="welcome-card">
          <div class="welcome-mark">AI</div>
          <h3>Turn network evidence into an actionable change</h3>
          <p class="text-muted">
            Start a session to give the assistant temporary diagnostic access.
            Conversation history and reviewed drafts are retained in the
            management database, while passwords remain ephemeral.
          </p>
          <b-alert show variant="info" class="mb-0">
            Configure the default prompt and available skills from Settings &gt;
            Assistant.
          </b-alert>
        </b-card>

        <template v-else>
          <b-card class="chat-card mb-3" no-body>
            <div class="workspace-bar">
              <div>
                <div class="eyebrow">SESSION</div>
                <h4 class="mb-0">
                  {{ session_title || "Network investigation" }}
                </h4>
              </div>
              <div>
                <b-badge :variant="deploymentBadgeVariant">{{
                  deploymentLabel
                }}</b-badge>
                <b-button
                  size="sm"
                  variant="outline-danger"
                  class="ml-2"
                  @click="discardSession"
                >
                  Delete session
                </b-button>
              </div>
            </div>
            <div class="chat-history" ref="chatHistoryDiv">
              <b-alert v-if="!credentials_active" show variant="warning">
                This session is retained for review, but its temporary
                diagnostic credentials have expired. Start a new session to
                continue chatting or deploy another draft.
              </b-alert>
              <div v-if="messages.length === 0" class="chat-empty">
                Ask about a host, service, metric, or incident. The assistant
                will investigate before drafting anything.
              </div>
              <div
                v-for="(msg, idx) in visibleMessages"
                :key="'msg' + idx"
                class="chat-message"
                :class="'chat-message-' + msg.role"
              >
                <div class="message-role">
                  {{ msg.role === "user" ? "You" : "Assistant" }}
                </div>
                <div class="message-content">{{ msg.content }}</div>
              </div>
              <div v-if="sending" class="working-row">
                <b-spinner small class="mr-2" />
                Investigating<span v-if="turn_step"
                  >, step {{ turn_step }}</span
                >
                <b-button
                  size="sm"
                  variant="outline-danger"
                  class="ml-2"
                  @click="stopTurn"
                >
                  Stop
                </b-button>
              </div>
            </div>
            <div class="composer">
              <b-form-textarea
                v-model="user_message"
                rows="2"
                max-rows="6"
                placeholder="Describe the network problem..."
                :disabled="sending || !credentials_active"
                @keydown.enter.exact.prevent="sendMessage"
              />
              <b-button
                variant="primary"
                class="send-button"
                :disabled="sending || !user_message.trim()"
                @click="sendMessage"
              >
                Send
              </b-button>
            </div>
          </b-card>

          <b-card v-if="draft" class="draft-card mb-3" no-body>
            <div class="card-section-heading">
              <div>
                <div class="eyebrow">REVIEW REQUIRED</div>
                <h4>Proposed Ansible change</h4>
                <p class="text-muted mb-0">{{ draft.description }}</p>
              </div>
              <b-badge variant="warning">Not deployed</b-badge>
            </div>
            <b-form-group label="Playbook filename" label-for="draft-filename">
              <b-form-input id="draft-filename" v-model="draft.filename" />
            </b-form-group>
            <codemirror v-model="draft.yaml" :options="editorOptions" />
            <b-alert show variant="light" class="security-note mt-3 mb-0">
              Deployment hosts and encrypted become vars are attached by the
              controller after you approve this review. They are not generated
              by the model.
            </b-alert>
            <b-row class="mt-3">
              <b-col md="8">
                <b-form-group
                  label="Confirm deployment hosts"
                  label-for="deployment-hosts"
                  description="This is the only inventory used by this deployment."
                >
                  <b-form-input
                    id="deployment-hosts"
                    v-model="deployment_hosts"
                    placeholder="10.0.0.5, 10.0.0.6"
                  />
                </b-form-group>
              </b-col>
              <b-col md="4" class="draft-actions">
                <b-button
                  variant="success"
                  block
                  :disabled="deploying || !deploymentHosts.length"
                  @click="approveAndDeploy"
                >
                  <b-spinner v-if="deploying" small class="mr-1" />
                  Approve and deploy
                </b-button>
                <b-button
                  variant="outline-secondary"
                  block
                  :disabled="deploying"
                  @click="discardDraft"
                >
                  Discard draft
                </b-button>
              </b-col>
            </b-row>
          </b-card>

          <b-card
            v-if="deployment_logs.length || deployment_status"
            class="deployment-card"
            no-body
          >
            <div class="card-section-heading">
              <div>
                <div class="eyebrow">DEPLOYMENT MONITOR</div>
                <h4>Execution progress</h4>
              </div>
              <b-badge :variant="deploymentBadgeVariant">{{
                deploymentLabel
              }}</b-badge>
            </div>
            <b-alert v-if="deployment_error" show variant="danger">{{
              deployment_error
            }}</b-alert>
            <pre v-if="deployment_logs.length" class="deployment-log">{{
              deployment_logs.join("\n")
            }}</pre>
            <p v-else class="text-muted mb-0">Waiting for Ansible output...</p>
          </b-card>
        </template>
      </b-col>
    </b-row>
  </b-container>
</template>

<script>
import Helper from "@/helper";
import { loadFilesList } from "@/services/ansibleRunner";

export default {
  name: "AiChat",
  data() {
    return {
      providers: [],
      selected_provider: "",
      host: "",
      files_list: {},
      selected_become: "",
      selected_ssh: "",
      vault_password: "",
      sessions: [],
      starting: false,
      session_id: "",
      session_title: "",
      session_prompt: "",
      credentials_active: true,
      messages: [],
      user_message: "",
      sending: false,
      draft: null,
      deploying: false,
      deployment_hosts: "",
      deployment_status: "",
      deployment_job_id: "",
      deployment_logs: [],
      deployment_error: "",
      turn_step: "",
      editorOptions: {
        tabSize: 2,
        mode: "text/x-yaml",
        theme: "default",
        lineNumbers: true,
        line: true,
      },
    };
  },
  computed: {
    canStartSession() {
      return (
        this.selected_provider !== "" &&
        this.selected_become !== "" &&
        this.vault_password !== "" &&
        this.host !== ""
      );
    },
    deploymentHosts() {
      return this.deployment_hosts
        .split(",")
        .map((host) => host.trim())
        .filter((host) => host.length > 0);
    },
    visibleMessages() {
      return this.messages.filter(
        (message) =>
          message.role === "user" ||
          (message.role === "assistant" && message.content)
      );
    },
    deploymentLabel() {
      return this.deployment_status || "No deployment";
    },
    deploymentBadgeVariant() {
      if (["error", "failed"].includes(this.deployment_status)) return "danger";
      if (["completed", "success"].includes(this.deployment_status))
        return "success";
      if (["queued", "running", "deploying"].includes(this.deployment_status))
        return "warning";
      return "secondary";
    },
  },
  methods: {
    parseMaybeJSON(payload) {
      if (typeof payload !== "string") return payload;
      try {
        return JSON.parse(payload);
      } catch (e) {
        return payload;
      }
    },
    formatSessionDate(value) {
      if (!value) return "";
      return new Date(Number(value) * 1000).toLocaleString();
    },
    async loadProviders() {
      try {
        this.providers = await Helper.apiCall(
          "ai_chat/providers",
          "",
          this.$auth
        );
        if (!this.selected_provider && this.providers.length)
          this.selected_provider = this.providers[0];
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    async loadFileList(type) {
      try {
        this.$set(this.files_list, type, await loadFilesList(this.$auth, type));
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    async loadSessions() {
      try {
        this.sessions =
          this.parseMaybeJSON(
            await Helper.apiCall("ai_chat/sessions", "", this.$auth)
          ) || [];
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    async loadAssistantSettings() {
      try {
        const response = await Helper.apiCall(
          "ai_chat/settings",
          "",
          this.$auth
        );
        const settings = this.parseMaybeJSON(response);
        this.session_prompt = settings.prompt || "";
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    async startSession() {
      this.starting = true;
      try {
        const data = {
          provider: this.selected_provider,
          become_file: this.selected_become.replace(/\.yml$/, ""),
          ssh_key: this.selected_ssh,
          vault_password: this.vault_password,
          prompt: this.session_prompt,
          target_hosts: this.host
            .split(",")
            .map((host) => host.trim())
            .filter((host) => host.length > 0),
        };
        const formData = new FormData();
        formData.append("data", JSON.stringify(data));
        const response = await Helper.apiPost(
          "ai_chat/session",
          "",
          "",
          this.$auth,
          formData,
          false,
          1
        );
        const result = await response.json();
        await this.resumeSession(result.session_id);
        await this.loadSessions();
      } catch (e) {
        this.$store.commit("updateError", e);
      } finally {
        this.starting = false;
      }
    },
    async resumeSession(sessionId) {
      try {
        const metadata = this.parseMaybeJSON(
          await Helper.apiCall("ai_chat/session", sessionId, this.$auth)
        );
        const history = this.parseMaybeJSON(
          await Helper.apiCall("ai_chat/history", sessionId, this.$auth)
        );
        this.session_id = sessionId;
        this.credentials_active = metadata.credentials_active !== false;
        this.session_title = metadata.title || "";
        this.session_prompt = metadata.prompt || this.session_prompt;
        this.messages = history || [];
        this.draft = metadata.draft || null;
        const targetHosts = metadata.target_hosts || [];
        if (targetHosts.length) this.host = targetHosts.join(", ");
        this.deployment_hosts = (metadata.deployment_hosts || this.host || [])
          .join
          ? (metadata.deployment_hosts || this.host || []).join(", ")
          : metadata.deployment_hosts || this.host || "";
        this.deployment_status =
          metadata.deployment_status || metadata.status || "";
        this.deployment_job_id = metadata.deployment_job_id || "";
        this.deployment_logs = metadata.deployment_logs || [];
        this.deployment_error = metadata.deployment_error || "";
        window.localStorage.setItem("ai_chat_session_id", sessionId);
        if (
          this.deployment_job_id &&
          ["queued", "running"].includes(this.deployment_status)
        ) {
          this.pollDeployment();
        }
        const turn = await Helper.apiCall(
          "ai_chat/turn",
          sessionId,
          this.$auth
        ).catch(() => null);
        if (turn && ["queued", "running"].includes(turn.status))
          this.pollTurn();
        this.scrollChatToBottom();
      } catch (e) {
        window.localStorage.removeItem("ai_chat_session_id");
        this.session_id = "";
      }
    },
    async sendMessage() {
      const outgoing = this.user_message.trim();
      if (!outgoing || this.sending || !this.credentials_active) return;
      this.messages.push({ role: "user", content: outgoing });
      this.user_message = "";
      this.sending = true;
      try {
        const formData = new FormData();
        formData.append("data", JSON.stringify({ message: outgoing }));
        await Helper.apiPost(
          "ai_chat/message",
          "",
          this.session_id,
          this.$auth,
          formData,
          false,
          1
        );
        await this.pollTurn();
        await this.loadSessions();
      } catch (e) {
        this.$store.commit("updateError", e);
        this.sending = false;
      }
    },
    async pollTurn() {
      this.sending = true;
      try {
        let polling = true;
        while (polling) {
          const turn = await Helper.apiCall(
            "ai_chat/turn",
            this.session_id,
            this.$auth
          );
          this.turn_step = turn.step || "";
          if (["queued", "running"].includes(turn.status)) {
            await new Promise((resolve) => setTimeout(resolve, 1500));
            continue;
          }
          if (turn.status === "error")
            this.$store.commit(
              "updateError",
              turn.error || "Assistant turn failed"
            );
          if (turn.reply)
            this.messages.push({ role: "assistant", content: turn.reply });
          if (turn.draft) {
            this.draft = turn.draft;
            this.deployment_hosts = this.host;
          }
          polling = false;
        }
      } catch (e) {
        this.$store.commit("updateError", e);
      } finally {
        this.sending = false;
        this.turn_step = "";
        this.scrollChatToBottom();
      }
    },
    async stopTurn() {
      try {
        await Helper.apiDelete("ai_chat/turn", this.session_id, this.$auth);
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    async approveAndDeploy() {
      if (!this.credentials_active) return;
      this.deploying = true;
      this.deployment_status = "queued";
      this.deployment_logs = [];
      this.deployment_error = "";
      try {
        const formData = JSON.stringify({
          hosts: this.deploymentHosts,
          filename: this.draft.filename,
          yaml: this.draft.yaml,
        });
        const response = await Helper.apiPost(
          "ai_chat/deploy",
          "",
          this.session_id,
          this.$auth,
          formData,
          false,
          1
        );
        const result = await response.json();
        this.deployment_job_id = result.job_id;
        this.draft = null;
        await this.pollDeployment();
      } catch (e) {
        this.deployment_status = "error";
        this.deployment_error = e.message || String(e);
        this.$store.commit("updateError", e);
      } finally {
        this.deploying = false;
      }
    },
    async pollDeployment() {
      if (!this.deployment_job_id) return;
      while (["queued", "running"].includes(this.deployment_status)) {
        try {
          const result = await Helper.apiCall(
            `ansible_status/${this.deployment_job_id}`,
            "",
            this.$auth
          );
          this.deployment_status = result.status;
          this.deployment_logs = result.logs || [];
          if (result.error) this.deployment_error = result.error;
          if (["queued", "running"].includes(result.status)) {
            await new Promise((resolve) => setTimeout(resolve, 1500));
          }
        } catch (e) {
          this.deployment_error = e.message || String(e);
          break;
        }
      }
      await this.loadSessions();
    },
    discardDraft() {
      this.draft = null;
    },
    newSession() {
      this.session_id = "";
      this.session_prompt = "";
      this.credentials_active = true;
      this.messages = [];
      this.draft = null;
      this.deployment_status = "";
      this.deployment_logs = [];
      this.deployment_job_id = "";
      window.localStorage.removeItem("ai_chat_session_id");
    },
    async discardSession() {
      try {
        await Helper.apiDelete("ai_chat/session", this.session_id, this.$auth);
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      this.newSession();
      await this.loadSessions();
    },
    scrollChatToBottom() {
      this.$nextTick(() => {
        const div = this.$refs.chatHistoryDiv;
        if (div) div.scrollTop = div.scrollHeight;
      });
    },
  },
  async mounted() {
    await Promise.all([
      this.loadProviders(),
      this.loadAssistantSettings(),
      this.loadFileList("become"),
      this.loadFileList("ssh"),
      this.loadSessions(),
    ]);
    const stored = window.localStorage.getItem("ai_chat_session_id");
    if (stored) await this.resumeSession(stored);
  },
};
</script>

<style lang="scss" scoped>
.assistant-page {
  max-width: 1500px;
  padding-top: 1.5rem;
}
.page-heading,
.workspace-bar,
.card-section-heading,
.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.eyebrow {
  color: #718096;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.session-panel,
.start-panel,
.welcome-card,
.chat-card,
.draft-card,
.deployment-card {
  border: 0;
  box-shadow: 0 8px 24px rgba(31, 45, 61, 0.08);
}
.panel-title {
  padding: 1rem;
  font-weight: 700;
  border-bottom: 1px solid #edf2f7;
}
.empty-panel {
  padding: 1.25rem;
  color: #718096;
  font-size: 0.9rem;
}
.session-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  border: 0;
  border-left: 3px solid transparent;
  background: white;
  padding: 0.8rem 1rem;
  text-align: left;
}
.session-item:hover,
.session-item.selected {
  background: #f7fafc;
  border-left-color: #4299e1;
}
.session-item small {
  color: #718096;
  margin-top: 0.15rem;
}
.start-panel {
  padding: 1rem;
}
.start-panel .panel-title {
  margin: -1rem -1rem 1rem;
}
.welcome-card {
  min-height: 250px;
  padding: 2rem;
}
.welcome-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
  height: 3rem;
  border-radius: 12px;
  background: #2c5282;
  color: white;
  font-weight: 800;
  margin-bottom: 1rem;
}
.workspace-bar {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #edf2f7;
}
.chat-history {
  height: 430px;
  overflow-y: auto;
  padding: 1.25rem;
}
.chat-empty {
  color: #718096;
  text-align: center;
  padding: 7rem 2rem;
}
.chat-message {
  max-width: 82%;
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 12px;
}
.chat-message-user {
  margin-left: auto;
  background: #ebf8ff;
}
.chat-message-assistant {
  background: #f7fafc;
}
.message-role {
  color: #718096;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}
.message-content {
  white-space: pre-wrap;
}
.working-row {
  color: #718096;
  padding: 0.5rem;
}
.composer {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid #edf2f7;
}
.composer textarea {
  flex: 1;
}
.send-button {
  align-self: flex-end;
  min-width: 5rem;
}
.draft-card,
.deployment-card {
  padding: 1.25rem;
}
.draft-actions {
  padding-top: 1.8rem;
}
.security-note {
  border-left: 3px solid #4299e1;
}
.deployment-log {
  max-height: 300px;
  overflow-y: auto;
  background: #1a202c;
  color: #e2e8f0;
  padding: 1rem;
  white-space: pre-wrap;
}
::v-deep .CodeMirror {
  min-height: 280px;
  width: 100% !important;
  border: 1px solid #e2e8f0;
}
@media (max-width: 768px) {
  .page-heading,
  .workspace-bar,
  .card-section-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .chat-message {
    max-width: 96%;
  }
  .composer {
    flex-direction: column;
  }
  .send-button {
    align-self: stretch;
  }
}
</style>
