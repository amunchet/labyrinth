<template>
  <div>
    <h3>Telegraf</h3>
    <b-container class="mt-3">
      <b-row>
        <b-col>Default Template file: </b-col>
        <b-col><b-select /></b-col>
        <b-col cols="2">
          <b-button variant="primary">
            <font-awesome-icon icon="sync-alt" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row class="mt-3">
        <b-col>Default Backend server location</b-col>
        <b-col>
          <b-input
            v-model="default_backend"
            placeholder="Default Telegraf Server Backend (e.g. backend)"
          />
        </b-col>
        <b-col cols="2">
          <b-button variant="success" @click="saveDefaultBackend()">
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
  name: "Settings",
  data() {
    return {
      default_backend: "",
    };
  },
  methods: {
    loadDefaultBackend: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiCall("settings", "default_telegraf_backend", auth)
        .then((res) => {
          this.default_backend = res;
        })
        .catch((e) => {
          if (e.status == undefined || e.status != 481) {
            this.$store.commit("updateError", e);
          }
        });
    },
    saveDefaultBackend: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      let formData = new FormData();
      formData.append("name", "default_telegraf_backend");
      formData.append("value", this.default_backend);

      Helper.apiPost("settings", "", "", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadDefaultBackend();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: function () {
    try {
      this.loadDefaultBackend();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped></style>
