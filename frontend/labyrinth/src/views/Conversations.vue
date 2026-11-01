<template>
  <b-container class="mt-3 text-left">
    <div v-if="!conversation_id">
      <h3>Conversations</h3>
      <p class="text-muted">
        Work an agent does with you through the MCP server: what it asked, the
        deployments it staged, your answers, and how each run went. The agent
        never runs anything itself. It waits for you here.
      </p>
      <p v-if="load_failed && conversations === null" class="text-muted">
        Conversations could not be loaded.
      </p>
      <b-spinner v-else-if="conversations === null" class="m-2" />
      <p v-else-if="conversations.length == 0" class="text-muted">
        No conversations yet.
      </p>
      <b-list-group v-else>
        <b-list-group-item
          v-for="item in conversations"
          :key="item.conversation_id"
          :to="'/conversations/' + item.conversation_id"
          class="d-flex justify-content-between align-items-start"
        >
          <div class="mr-3 conversation_preview">
            <b>{{ item.title }}</b>
            <div class="small text-muted">
              {{ preview(item.last_message) }}
            </div>
          </div>
          <div class="text-right text-nowrap">
            <b-badge :variant="stateOf(item).variant">
              {{ stateOf(item).label }}
            </b-badge>
            <div class="small text-muted">{{ when(item.updated_at) }}</div>
          </div>
        </b-list-group-item>
      </b-list-group>
    </div>

    <div v-else>
      <router-link to="/conversations">
        <font-awesome-icon icon="arrow-left" size="1x" /> All conversations
      </router-link>
      <p v-if="load_failed && !conversation" class="mt-3 text-muted">
        This conversation could not be loaded.
      </p>
      <b-spinner v-else-if="!conversation" class="m-2 d-block" />
      <div v-else>
        <h3 class="mt-2">
          {{ conversation.title }}
          <b-badge :variant="stateOf(conversation).variant">
            {{ stateOf(conversation).label }}
          </b-badge>
        </h3>
        <div class="small text-muted mb-3">
          Started {{ when(conversation.created_at) }}
        </div>

        <div
          v-for="message in conversation.messages"
          :key="message.id"
          :class="['message', 'from_' + message.author]"
        >
          <div class="small text-muted">
            <b>{{ authorName(message) }}</b> · {{ when(message.at) }}
            <b-badge
              v-if="message.kind == 'question'"
              class="ml-1"
              :variant="isPending('question', message.id) ? 'warning' : 'light'"
            >
              {{
                isPending("question", message.id)
                  ? "Needs your answer"
                  : "Question"
              }}
            </b-badge>
          </div>

          <b-card
            v-if="message.kind == 'deploy'"
            class="mt-1"
            :border-variant="
              isPending('deploy', message.request_id) ? 'warning' : ''
            "
          >
            <div class="d-flex justify-content-between">
              <h5 class="mb-1">
                <font-awesome-icon icon="rocket" size="1x" /> Deploy
                {{ message.playbook }}.yml
                <small v-if="message.generated" class="text-muted">
                  (written by the agent)</small
                >
              </h5>
              <b-badge
                class="align-self-start"
                :variant="requestState(message.request_id).variant"
              >
                {{ requestState(message.request_id).label }}
              </b-badge>
            </div>
            <p v-if="message.text" class="mb-2 pre_line">{{ message.text }}</p>
            <div class="small">
              Hosts: <b>{{ message.hosts.join(", ") }}</b
              ><br />
              Become file:
              <b>{{
                message.become_file
                  ? message.become_file + ".yml"
                  : "you choose when deploying"
              }}</b>
            </div>
            <b-button
              v-if="staged(message.request_id).generated"
              variant="link"
              class="p-0 mt-1"
              v-b-toggle="'playbook_' + message.id"
            >
              Review playbook
            </b-button>
            <b-collapse :id="'playbook_' + message.id">
              <pre class="playbook">{{
                staged(message.request_id).playbook_content
              }}</pre>
            </b-collapse>
            <div class="mt-2" v-if="isPending('deploy', message.request_id)">
              <b-button
                variant="primary"
                :to="'/deploy?request=' + message.request_id"
              >
                <font-awesome-icon icon="key" size="1x" /> Review and deploy
              </b-button>
              <b-button
                variant="outline-secondary"
                class="ml-2"
                :disabled="sending"
                @click="decline(message.request_id)"
              >
                Decline
              </b-button>
              <span class="small text-muted ml-2">
                (any reply typed below is sent as the reason)
              </span>
            </div>
          </b-card>

          <div v-else-if="message.kind == 'launched'" class="mt-1">
            <font-awesome-icon icon="play" size="1x" /> Launched the run with
            {{ message.become_file }}.yml
            <span class="small text-muted">({{ message.job_id }})</span>
          </div>

          <b-alert
            v-else-if="message.kind == 'run'"
            show
            class="mt-1 mb-0"
            :variant="message.outcome == 'success' ? 'success' : 'danger'"
          >
            <b>{{ message.text }}</b>
            <span v-if="message.error"> - {{ message.error }}</span>
            <div class="small" v-if="message.stats">
              {{ statsSummary(message.stats) }}
            </div>
            <ul class="mb-0 small" v-if="message.failures.length > 0">
              <li
                v-for="(failure, idx) in message.failures"
                :key="message.id + '_failure' + idx"
              >
                {{ failure.host }} - {{ failure.task }}: {{ failure.msg }}
              </li>
            </ul>
          </b-alert>

          <div v-else-if="message.kind == 'declined'" class="mt-1">
            <font-awesome-icon icon="ban" size="1x" /> Declined the
            deployment<span v-if="message.text">: {{ message.text }}</span>
          </div>

          <div v-else-if="message.kind == 'closed'" class="mt-1">
            <font-awesome-icon icon="check" size="1x" /> Closed the
            conversation<span v-if="message.text">: {{ message.text }}</span>
          </div>

          <div v-else class="mt-1 pre_line">{{ message.text }}</div>
        </div>

        <b-form class="mt-4" @submit.prevent="sendReply()">
          <b-textarea
            v-model="reply"
            rows="3"
            placeholder="Reply to the agent (Ctrl+Enter sends)"
            @keydown.ctrl.enter="sendReply()"
          />
          <div class="mt-2 overflow-hidden">
            <b-button
              type="submit"
              variant="primary"
              class="float-right"
              :disabled="sending || !reply.trim()"
            >
              <font-awesome-icon icon="paper-plane" size="1x" /> Send
            </b-button>
            <b-button
              v-if="conversation.status != 'closed'"
              variant="outline-secondary"
              class="float-right mr-2"
              :disabled="sending"
              @click="closeConversation()"
            >
              Close conversation
            </b-button>
          </div>
        </b-form>
      </div>
    </div>
  </b-container>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Conversations",
  data() {
    return {
      // null until the first answer arrives
      conversations: null,
      conversation: null,
      load_failed: false,
      reply: "",
      sending: false,
      timer: null,
    };
  },
  computed: {
    conversation_id() {
      return this.$route.params.id || "";
    },
  },
  watch: {
    conversation_id: /* istanbul ignore next */ function () {
      this.conversation = null;
      this.load_failed = false;
      this.reply = "";
      this.load();
    },
  },
  methods: {
    // Badge for a conversation (or conversation summary)
    stateOf(item) {
      if (item.status == "closed") {
        return { label: "Closed", variant: "secondary" };
      }
      if (item.needs_human) {
        return { label: "Needs you", variant: "warning" };
      }
      return { label: "Open", variant: "info" };
    },
    isPending(type, id) {
      return (this.conversation.pending || []).some(
        (x) => x.type == type && x.id == id
      );
    },
    staged(request_id) {
      return (this.conversation.requests || {})[request_id] || { runs: [] };
    },
    // Where a staged deployment stands, from its latest run
    requestState(request_id) {
      const staged = this.staged(request_id);
      const run = staged.runs[staged.runs.length - 1];
      if (!run) {
        if (staged.declined_at) {
          return { label: "Declined", variant: "secondary" };
        }
        // Closing a conversation drops its unlaunched deployments
        return this.isPending("deploy", request_id)
          ? { label: "Waiting for your vault password", variant: "warning" }
          : { label: "Not deployed", variant: "secondary" };
      }
      if (run.status == "queued" || run.status == "running") {
        return { label: "Running", variant: "info" };
      }
      return run.outcome == "success"
        ? { label: "Succeeded", variant: "success" }
        : { label: "Failed", variant: "danger" };
    },
    authorName(message) {
      return { agent: "Agent", human: "You", system: "Ansible" }[
        message.author
      ];
    },
    preview(message) {
      if (!message) {
        return "";
      }
      // The label for an action, then whatever was said with it (notes, a reason, a summary)
      const label = {
        deploy: "Staged deploy of " + message.playbook + ".yml",
        launched: "Run launched",
        declined: "Declined the deployment",
        closed: "Closed",
      }[message.kind];
      const text = [label, message.text].filter((x) => x).join(": ");
      return this.authorName(message) + ": " + text;
    },
    // "3 ok, 1 changed, 1 failed" across all hosts
    statsSummary(stats) {
      const count = (key) =>
        Object.values(stats[key] || {}).reduce((a, b) => a + b, 0);
      return [
        [count("ok"), "ok"],
        [count("changed"), "changed"],
        [count("failures"), "failed"],
        [count("dark"), "unreachable"],
        [count("skipped"), "skipped"],
      ]
        .filter((x) => x[0] > 0)
        .map((x) => x.join(" "))
        .join(", ");
    },
    when(iso) {
      return iso ? new Date(iso).toLocaleString() : "";
    },

    load: /* istanbul ignore next */ async function () {
      try {
        if (this.conversation_id) {
          this.conversation = await Helper.apiCall(
            "conversation",
            this.conversation_id,
            this.$auth
          );
        } else {
          this.conversations = await Helper.apiCall(
            "conversations",
            "",
            this.$auth
          );
        }
        this.load_failed = false;
      } catch (e) {
        // Polls repeat every 5s; report a failure once, not on every poll
        if (!this.load_failed) {
          this.$store.commit("updateError", e);
        }
        this.load_failed = true;
      }
    },
    // POSTs a human action, then refreshes this page and the nav badge
    post: /* istanbul ignore next */ async function (
      service,
      id,
      action,
      data
    ) {
      this.sending = true;
      try {
        let formData = new FormData();
        formData.append("data", JSON.stringify(data));
        await Helper.apiPost(service, id, action, this.$auth, formData);
        await this.load();
        this.$root.$emit("conversations-changed");
        return true;
      } catch (e) {
        this.$store.commit("updateError", e);
        return false;
      } finally {
        this.sending = false;
      }
    },
    sendReply: /* istanbul ignore next */ async function () {
      if (!this.reply.trim() || this.sending) {
        return;
      }
      if (
        await this.post("conversation/", this.conversation_id, "reply", {
          text: this.reply,
        })
      ) {
        this.reply = "";
      }
    },
    decline: /* istanbul ignore next */ async function (request_id) {
      if (
        await this.post("ansible_request/", request_id, "decline", {
          text: this.reply.trim(),
        })
      ) {
        this.reply = "";
      }
    },
    closeConversation: /* istanbul ignore next */ async function () {
      if (
        await this.post("conversation/", this.conversation_id, "close", {
          text: this.reply.trim(),
        })
      ) {
        this.reply = "";
      }
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.load();
    // Agent messages and run results arrive on their own
    this.timer = setInterval(() => {
      if (!this.sending) {
        this.load();
      }
    }, 5000);
  },
  beforeDestroy: /* istanbul ignore next */ function () {
    clearInterval(this.timer);
  },
};
</script>
<style lang="scss" scoped>
.message {
  border-left: 3px solid lightgrey;
  padding: 0.25rem 0 0.25rem 0.75rem;
  margin-bottom: 0.75rem;
}
.from_agent {
  border-left-color: #17a2b8;
}
.from_human {
  border-left-color: #007bff;
}
.from_system {
  border-left-color: #6c757d;
}
.pre_line {
  white-space: pre-line;
}
.playbook {
  white-space: pre;
  max-height: 400px;
  overflow: auto;
  background-color: lightgrey;
  padding: 1rem;
}
.conversation_preview {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
