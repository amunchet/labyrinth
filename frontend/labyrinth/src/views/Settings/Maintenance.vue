<template>
  <div class="text-left">
    <h2>Maintenance</h2>
    <hr />
    <b-row>
      <b-col>Restart Server</b-col>
      <b-col cols="2">
        <b-button @click="restart(0)" variant="warning"
          >Soft Restart</b-button
        > </b-col
      ><b-col cols="2">
        <b-button @click="restart(4)" variant="danger">Full Restart</b-button>
      </b-col>
    </b-row>
  </div>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Maintenance",
  methods: {
    restart: /* istanbul ignore next */ function (code) {
      let auth = this.$auth;
      this.$bvModal
        .msgBoxConfirm("Are you sure you want to restart?")
        .then((res) => {
          if (!res) {
            return;
          }
          Helper.apiCall("settings", `restart/${code}`, auth)
            .then(() => {
              this.$store.commit("updateError", "Restarting...");
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        })
        .catch((e) => this.$store.commit("updateError", e));
    },
  },
};
</script>
