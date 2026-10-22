<template>
  <div>
    <h3>Monitoring</h3>
    <b-container class="mt-3">
      <b-row>
        <b-col>Port scan stale window (hours)</b-col>
        <b-col>
          <b-input
            v-model="port_stale_hours"
            type="number"
            min="0.1"
            step="0.5"
            placeholder="12"
          />
        </b-col>
        <b-col cols="2">
          <b-button variant="success" @click="savePortStaleHours()">
            <font-awesome-icon icon="save" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row>
        <b-col class="text-muted small text-left mt-1">
          Open/closed port checks report "No metric received" once the latest
          scan of a host is older than this. Defaults to 12 hours.
        </b-col>
      </b-row>
    </b-container>
  </div>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Monitoring",
  data() {
    return {
      port_stale_hours: "",
    };
  },
  methods: {
    loadPortStaleHours: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiCall("settings", "port_stale_hours", auth)
        .then((res) => {
          this.port_stale_hours = res;
        })
        .catch((e) => {
          if (e.status == undefined || e.status != 481) {
            this.$store.commit("updateError", e);
          }
        });
    },
    savePortStaleHours: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      let formData = new FormData();
      formData.append("name", "port_stale_hours");
      formData.append("value", this.port_stale_hours);

      Helper.apiPost("settings", "", "", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadPortStaleHours();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: function () {
    try {
      this.loadPortStaleHours();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped></style>
