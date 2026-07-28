<template>
  <b-container>
    <b-row>
      <b-col>
        <h3>AI Assistant <span class="text-muted">(Experimental)</span></h3>
        <p class="text-muted">
          Describe a problem (e.g. "disk usage is high on 10.0.0.5" or
          "the nginx container on webhost isn't responding"). The assistant can
          look at hosts, metrics, and safe read-only diagnostics, then draft an
          Ansible playbook to fix it. Nothing is ever deployed without your
          explicit approval below.
        </p>
      </b-col>
    </b-row>

    <b-row v-if="!session_id">
      <b-col>
        <b-card class="text-left">
          <h4>Start a session</h4>
          <b-row>
            <b-col>
              LLM Provider:
              <b-select
                :state="selected_provider != ''"
                v-model="selected_provider"
                :options="providers"
              />
              <small v-if="providers.length === 0" class="text-danger">
                No LLM providers are configured on the backend yet.
              </small>
            </b-col>
            <b-col>
              Target host(s):
              <b-input
                v-model="host"
                placeholder="e.g. 10.0.0.5 or 10.0.0.5,10.0.0.6"
              />
            </b-col>
          </b-row>
          <b-row class="mt-3">
            <b-col>
              Become Password file:
              <b-select
                v-if="files_list['become'] != undefined"
                :options="files_list['become']"
                v-model="selected_become"
                :state="selected_become != ''"
              />
              <b-spinner v-else class="m-2" />
            </b-col>
            <b-col>
              Vault Password:
              <b-input
                type="password"
                :state="vault_password != ''"
                v-model="vault_password"
              />
            </b-col>
            <b-col>
              SSH Key (optional):
              <b-select
                v-if="files_list['ssh'] != undefined"
                :options="['', ...files_list['ssh']]"
                v-model="selected_ssh"
              />
              <b-spinner v-else class="m-2" />
            </b-col>
          </b-row>
          <b-row class="mt-3">
            <b-col>
              <b-button
                variant="primary"
                :disabled="!canStartSession || starting"
                @click="startSession"
              >
                <b-spinner small v-if="starting" />
                Start Chat
              </b-button>
            </b-col>
          </b-row>
        </b-card>
      </b-col>
    </b-row>

    <b-row v-else>
      <b-col>
        <b-card class="text-left mb-3">
          <div class="chat_history" ref="chatHistoryDiv">
            <div
              v-for="(msg, idx) in messages"
              v-bind:key="'msg' + idx"
              class="chat_message"
              :class="'chat_message_' + msg.role"
            >
              <b>{{ msg.role === "user" ? "You" : "Assistant" }}:</b>
              <span style="white-space: pre-wrap">{{ msg.content }}</span>
            </div>
            <b-spinner small v-if="sending" class="m-2" />
          </div>
          <hr />
          <b-row>
            <b-col>
              <b-textarea
                v-model="user_message"
                placeholder="Describe the problem..."
                rows="2"
                @keydown.enter.exact.prevent="sendMessage"
              />
            </b-col>
            <b-col cols="2">
              <b-button
                variant="primary"
                style="width: 100%"
                :disabled="sending || user_message == ''"
                @click="sendMessage"
              >
                Send
              </b-button>
            </b-col>
          </b-row>
        </b-card>

        <b-card class="text-left mb-3" v-if="draft">
          <h4>Proposed playbook: {{ draft.filename }}</h4>
          <p>{{ draft.description }}</p>
          <codemirror
            :value="draft.yaml"
            :options="{
              tabSize: 4,
              mode: 'text/x-yaml',
              theme: 'default',
              lineNumbers: true,
              readOnly: true,
              line: true,
            }"
          >
          </codemirror>
          <div class="mt-2">
            <b-button
              variant="success"
              :disabled="deploying"
              @click="approveAndDeploy"
            >
              <b-spinner small v-if="deploying" /> Approve &amp; Deploy
            </b-button>
            <b-button
              variant="outline-secondary"
              class="ml-2"
              :disabled="deploying"
              @click="draft = null"
            >
              Discard Draft
            </b-button>
          </div>
          <div class="deploy_result mt-3" v-if="deploy_logs.length > 0">
            <pre
              v-for="(item, idx) in deploy_logs"
              v-bind:key="'deploylog' + idx"
              >{{ (item || "").replace(/^\s+/gm, " ") }}</pre
            >
          </div>
        </b-card>

        <b-button variant="outline-danger" @click="discardSession">
          End Session
        </b-button>
      </b-col>
    </b-row>
  </b-container>
</template>
<script>
import Helper from "@/helper";
import {
  loadFilesList,
  savePlaybookContents,
  runPlaybookAndPoll,
} from "@/services/ansibleRunner";

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

      starting: false,
      session_id: "",

      messages: [],
      user_message: "",
      sending: false,

      draft: null,
      deploying: false,
      deploy_logs: [],
    };
  },
  computed: {
    canStartSession: /* istanbul ignore next */ function () {
      return (
        this.selected_provider != "" &&
        this.selected_become != "" &&
        this.vault_password != "" &&
        this.host != ""
      );
    },
  },
  methods: {
    loadProviders: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiCall("ai_chat/providers", "", auth)
        .then((res) => {
          this.providers = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadFileList: /* istanbul ignore next */ function (type) {
      let auth = this.$auth;
      loadFilesList(auth, type)
        .then((res) => {
          this.files_list = { ...this.files_list, [type]: res };
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    startSession: /* istanbul ignore next */ async function () {
      this.starting = true;
      let auth = this.$auth;
      let data = {
        provider: this.selected_provider,
        become_file: this.selected_become.replace(/.yml$/, ""),
        ssh_key: this.selected_ssh,
        vault_password: this.vault_password,
      };
      let formData = new FormData();
      formData.append("data", JSON.stringify(data));

      try {
        let response = await Helper.apiPost(
          "ai_chat/session",
          "",
          "",
          auth,
          formData,
          false,
          1
        );
        const resp = await response.json();
        this.session_id = resp.session_id;
        this.messages = [];
      } catch (e) {
        this.$store.commit("updateError", e);
      } finally {
        this.starting = false;
      }
    },
    sendMessage: /* istanbul ignore next */ async function () {
      if (this.user_message == "") {
        return;
      }
      let auth = this.$auth;
      const outgoing = this.user_message;
      this.messages.push({ role: "user", content: outgoing });
      this.user_message = "";
      this.sending = true;
      this.scrollChatToBottom();

      let formData = new FormData();
      formData.append("data", JSON.stringify({ message: outgoing }));

      try {
        let response = await Helper.apiPost(
          "ai_chat/message",
          "",
          this.session_id,
          auth,
          formData,
          false,
          1
        );
        const resp = await response.json();
        this.messages.push({ role: "assistant", content: resp.reply || "" });
        if (resp.draft) {
          this.draft = resp.draft;
          this.deploy_logs = [];
        }
      } catch (e) {
        this.$store.commit("updateError", e);
      } finally {
        this.sending = false;
        this.scrollChatToBottom();
      }
    },
    approveAndDeploy: /* istanbul ignore next */ async function () {
      this.deploying = true;
      this.deploy_logs = [];
      let auth = this.$auth;

      try {
        await savePlaybookContents(
          auth,
          this.draft.filename,
          this.selected_become,
          this.draft.yaml
        );

        await runPlaybookAndPoll(
          auth,
          {
            hosts: this.host,
            playbook: this.draft.filename,
            vaultPassword: this.vault_password,
            becomeFile: this.selected_become,
            sshKey: this.selected_ssh,
          },
          (logs) => {
            this.deploy_logs = logs;
          }
        );

        this.draft = null;
      } catch (e) {
        this.$store.commit("updateError", e);
      } finally {
        this.deploying = false;
      }
    },
    discardSession: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiDelete("ai_chat/session", this.session_id, auth)
        .catch((e) => {
          this.$store.commit("updateError", e);
        })
        .finally(() => {
          this.session_id = "";
          this.messages = [];
          this.draft = null;
          this.deploy_logs = [];
        });
    },
    scrollChatToBottom: /* istanbul ignore next */ function () {
      this.$nextTick(() => {
        const div = this.$refs.chatHistoryDiv;
        if (div) {
          div.scrollTop = div.scrollHeight;
        }
      });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.loadProviders();
    this.loadFileList("become");
    this.loadFileList("ssh");
  },
};
</script>
<style lang="scss" scoped>
.chat_history {
  max-height: 400px;
  overflow-y: auto;
  text-align: left;
}
.chat_message {
  margin-bottom: 0.75rem;
}
.chat_message_user {
  color: #333;
}
.chat_message_assistant {
  color: #145;
}
.deploy_result {
  max-height: 300px;
  overflow-y: auto;
  background-color: lightgrey;
  padding: 1rem;
  text-align: left;
}
::v-deep .CodeMirror {
  min-height: 250px;
  width: 100% !important;
}
</style>
