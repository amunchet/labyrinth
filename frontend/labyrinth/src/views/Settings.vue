<template>
  <b-container>
    <h3>Settings</h3>
    <hr />
    <b-row>
      <b-col class="text-left">
        <b-button variant="success" @click="startScan()"
          >Run Manual Scan</b-button
        >
      </b-col>
    </b-row>
    <hr />
    <div v-for="(subnet, idx) in data.split('Starting')" v-bind:key="idx">
      <b-progress
        v-if="idx != 0"
        :max="100"
        show-progress
        class="mb-2"
        height="2rem"
      >
        <b-progress-bar
          :value="((subnet.match(/\*/g) || []).length / 255) * 100"
        >
          <span
            ><strong>
              {{ subnet.split(".")[0].split("*")[0] }}.
              {{ subnet.split(".")[1].split("*")[0] }}.
              {{ subnet.split(".")[2].split("*")[0] }} |
              {{
                (((subnet.match(/\*/g) || []).length / 255) * 100).toFixed(0)
              }}%</strong
            ></span
          >
        </b-progress-bar>
      </b-progress>
    </div>
    <b-textarea ref="textarea_1" disabled v-model="data" />
  </b-container>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Settings",
  data() {
    return {
      data: "",
      subnet: "",
    };
  },
  methods: {
    loadData: /* istanbul ignore next */ async function () {
      var auth = this.$auth;
      await Helper.apiCall("redis", "", auth)
        .then((res) => {
          this.data = res;
          this.$forceUpdate();
          if (res.indexOf("Finished") == -1) {
            var el = this.$refs.textarea_1.$el;
            el.scrollTop = el.scrollHeight + 500;
            this.$forceUpdate();
            el = this.$refs.textarea_1.$el;
            el.scrollTop = el.scrollHeight + 500;
            this.$forceUpdate();
            setTimeout(this.loadData, 1000);
          }
        })
        .catch(() => {
          setTimeout(this.loadData, 1000);
        });
    },
    startScan: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("scan", "", auth)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadData();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadData();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style scoped>
textarea {
  height: 400px;
  padding: 0;
  padding-left: 1rem;
  padding-bottom: -40px;
}
</style>
