<template>
  <div class="text-left ai-alerts">
    <h2>AI Alerts</h2>
    <p class="text-muted">
      Controls the hourly AI dashboard summary job: what's sent to the model,
      which model answers, and who gets emailed when it decides to wake up the
      IT director.
    </p>
    <hr />

    <b-form @submit.prevent="save">
      <b-form-group
        label="System prompt:"
        label-for="ai-prompt"
        description="Sent to the model as the system message, followed by the current failing-service data. Controls how criticality is inferred and what wake_up_it_director / summary_email / critical_services should contain."
      >
        <b-form-textarea
          id="ai-prompt"
          v-model="prompt"
          rows="10"
          max-rows="20"
        ></b-form-textarea>
      </b-form-group>

      <b-form-group
        label="Model:"
        label-for="ai-model"
        description="OpenAI model name, e.g. gpt-5-mini"
      >
        <b-form-input id="ai-model" v-model="model"></b-form-input>
      </b-form-group>

      <b-form-group
        label="Alert recipient(s):"
        label-for="ai-recipients"
        description="Comma-separated list of email addresses to notify when the AI decides to wake up the IT director"
      >
        <b-form-textarea
          id="ai-recipients"
          v-model="recipientsText"
          rows="2"
          placeholder="admin@example.com, ops@example.com"
        ></b-form-textarea>
      </b-form-group>

      <b-form-group
        label="Subject line:"
        label-for="ai-subject-template"
        description="{time} is replaced with the current date/hour"
      >
        <b-form-input
          id="ai-subject-template"
          v-model="subjectTemplate"
        ></b-form-input>
      </b-form-group>

      <b-form-group label="From name:" label-for="ai-from-name">
        <b-form-input id="ai-from-name" v-model="fromName"></b-form-input>
      </b-form-group>

      <b-button variant="primary" type="submit" :disabled="saving">
        <b-spinner small v-if="saving" class="mr-2"></b-spinner>
        Save AI Alert Settings
      </b-button>
    </b-form>

    <b-alert
      v-if="successMessage"
      variant="success"
      dismissible
      show
      class="mt-3"
      @dismissed="successMessage = ''"
    >
      {{ successMessage }}
    </b-alert>
    <b-alert
      v-if="errorMessage"
      variant="danger"
      dismissible
      show
      class="mt-3"
      @dismissed="errorMessage = ''"
    >
      {{ errorMessage }}
    </b-alert>
  </div>
</template>

<script>
import Helper from "@/helper";

export default {
  name: "AiAlerts",
  data() {
    return {
      prompt: "",
      model: "",
      recipientsText: "",
      subjectTemplate: "",
      fromName: "",
      saving: false,
      loading: false,
      successMessage: "",
      errorMessage: "",
    };
  },
  mounted() {
    this.loadSettings();
  },
  methods: {
    parseMaybeJSON(payload) {
      if (typeof payload === "string") {
        try {
          return JSON.parse(payload);
        } catch (e) {
          return payload;
        }
      }
      return payload;
    },

    async loadSettings() {
      this.loading = true;
      try {
        const auth = this.$auth;
        const response = await Helper.apiCall("ai", "settings", auth);
        const data = this.parseMaybeJSON(response);

        this.prompt = data.prompt || "";
        this.model = data.model || "";
        this.recipientsText = Array.isArray(data.recipients)
          ? data.recipients.join(", ")
          : "";
        this.subjectTemplate = data.subject_template || "";
        this.fromName = data.from_name || "";
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.loading = false;
      }
    },

    async save() {
      this.saving = true;
      this.successMessage = "";
      this.errorMessage = "";
      try {
        const auth = this.$auth;
        const payload = JSON.stringify({
          prompt: this.prompt,
          model: this.model,
          recipients: this.recipientsText,
          subject_template: this.subjectTemplate,
          from_name: this.fromName,
        });

        const response = await Helper.apiPost(
          "ai/settings",
          "",
          "",
          auth,
          payload
        );
        const data = this.parseMaybeJSON(response);

        this.prompt = data.prompt || "";
        this.model = data.model || "";
        this.recipientsText = Array.isArray(data.recipients)
          ? data.recipients.join(", ")
          : "";
        this.subjectTemplate = data.subject_template || "";
        this.fromName = data.from_name || "";

        this.successMessage = "AI alert settings saved successfully!";
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>
