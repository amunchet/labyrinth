<template>
  <div class="text-left">
    <h3>Ansible</h3>
    <b-container class="mt-3">
      <b-row>
        <b-col>Ansible verbosity</b-col>
        <b-col>
          <b-select v-model="ansible_verbosity" :options="verbosity_options" />
        </b-col>
        <b-col cols="2">
          <b-button variant="success" @click="saveVerbosity()">
            <font-awesome-icon icon="save" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row class="mt-3">
        <b-col>Automatically manage become <code>vars_files</code></b-col>
        <b-col cols="3">
          <b-form-checkbox v-model="manage_vars_files" switch>
            Enabled
          </b-form-checkbox>
        </b-col>
        <b-col cols="2">
          <b-button variant="success" @click="saveVarsFiles()">
            <font-awesome-icon icon="save" size="1x" />
          </b-button>
        </b-col>
      </b-row>
    </b-container>
  </div>
</template>
<script>
import Helper from "@/helper";

export default {
  name: "SettingsAnsible",
  data() {
    return {
      ansible_verbosity: "5",
      manage_vars_files: true,
      verbosity_options: [
        { value: "0", text: "0 - quiet" },
        { value: "1", text: "1 - -v" },
        { value: "2", text: "2 - -vv" },
        { value: "3", text: "3 - -vvv" },
        { value: "4", text: "4 - -vvvv" },
        { value: "5", text: "5 - -vvvvv" },
      ],
    };
  },
  methods: {
    loadSettings: /* istanbul ignore next */ async function () {
      let auth = this.$auth;
      try {
        this.ansible_verbosity = await Helper.apiCall(
          "settings",
          "ansible_verbosity",
          auth
        );
      } catch (e) {
        if (e.status === undefined || e.status !== 481) {
          this.$store.commit("updateError", e);
        }
      }

      try {
        let value = await Helper.apiCall(
          "settings",
          "ansible_manage_vars_files",
          auth
        );
        this.manage_vars_files = ["1", "true", "yes", "on"].includes(
          (value || "").toString().toLowerCase()
        );
      } catch (e) {
        if (e.status === undefined || e.status !== 481) {
          this.$store.commit("updateError", e);
        }
      }
    },
    saveVerbosity: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      let formData = new FormData();
      formData.append("name", "ansible_verbosity");
      formData.append("value", this.ansible_verbosity);

      Helper.apiPost("settings", "", "", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadSettings();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    saveVarsFiles: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      let formData = new FormData();
      formData.append("name", "ansible_manage_vars_files");
      formData.append("value", this.manage_vars_files ? "1" : "0");

      Helper.apiPost("settings", "", "", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadSettings();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: function () {
    this.loadSettings();
  },
};
</script>
