<template>
  <div class="text-left ai-assistant-settings">
    <h2>AI Assistant</h2>
    <p class="text-muted">
      Configure the guidance and capabilities used by new interactive assistant
      sessions. Existing sessions keep the settings they were created with.
    </p>
    <b-alert show variant="info">
      Credentials are never stored here or sent to the model. They are supplied
      for the active session only and are removed when its Redis session
      expires.
    </b-alert>

    <b-form @submit.prevent="save">
      <b-form-group
        label="Default operator prompt"
        label-for="assistant-prompt"
        description="This is appended to the built-in safety and investigation instructions."
      >
        <b-form-textarea
          id="assistant-prompt"
          v-model="prompt"
          rows="10"
          max-rows="20"
        />
      </b-form-group>

      <b-form-group
        label="Maximum investigation steps"
        label-for="assistant-iterations"
        description="Limits the number of model/tool rounds in one turn. Lower values reduce cost and runaway sessions."
      >
        <b-form-input
          id="assistant-iterations"
          v-model.number="maxIterations"
          type="number"
          min="1"
          max="20"
        />
      </b-form-group>

      <b-form-group
        label="Available skills"
        description="Disable capabilities that should not be offered to the assistant."
      >
        <b-form-checkbox-group v-model="enabledSkills" stacked>
          <b-form-checkbox
            v-for="skill in skills"
            :key="skill.id"
            :value="skill.id"
          >
            <strong>{{ skill.name }}</strong>
            <span class="text-muted d-block">{{ skill.description }}</span>
          </b-form-checkbox>
        </b-form-checkbox-group>
      </b-form-group>

      <b-button variant="primary" type="submit" :disabled="saving">
        <b-spinner v-if="saving" small class="mr-2" />
        Save assistant settings
      </b-button>
    </b-form>

    <b-alert v-if="successMessage" show variant="success" class="mt-3">{{
      successMessage
    }}</b-alert>
    <b-alert v-if="errorMessage" show variant="danger" class="mt-3">{{
      errorMessage
    }}</b-alert>
  </div>
</template>

<script>
import Helper from "@/helper";

export default {
  name: "AiAssistant",
  data() {
    return {
      prompt: "",
      maxIterations: 8,
      skills: [],
      enabledSkills: [],
      saving: false,
      successMessage: "",
      errorMessage: "",
    };
  },
  mounted() {
    this.loadSettings();
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
    async loadSettings() {
      try {
        const [settingsResponse, skillsResponse] = await Promise.all([
          Helper.apiCall("ai_chat/settings", "", this.$auth),
          Helper.apiCall("ai_chat/skills", "", this.$auth),
        ]);
        const settings = this.parseMaybeJSON(settingsResponse);
        const skillData = this.parseMaybeJSON(skillsResponse);
        this.prompt = settings.prompt || "";
        this.maxIterations = settings.max_iterations || 8;
        this.skills = skillData.skills || [];
        this.enabledSkills = skillData.enabled || [];
      } catch (e) {
        this.errorMessage = e.message || String(e);
      }
    },
    async save() {
      this.saving = true;
      this.successMessage = "";
      this.errorMessage = "";
      try {
        const response = await Helper.apiPost(
          "ai_chat/settings",
          "",
          "",
          this.$auth,
          JSON.stringify({
            prompt: this.prompt,
            max_iterations: this.maxIterations,
            skills: this.enabledSkills,
          })
        );
        const settings = this.parseMaybeJSON(response);
        this.prompt = settings.prompt || this.prompt;
        this.maxIterations = settings.max_iterations || this.maxIterations;
        this.enabledSkills = settings.skills || this.enabledSkills;
        this.successMessage = "Assistant settings saved.";
      } catch (e) {
        this.errorMessage = e.message || String(e);
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>
