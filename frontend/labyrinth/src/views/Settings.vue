<template>
  <b-container>
    <h3>Settings</h3>
    <hr />
    <b-row>
      <b-col class="text-left">
        <b-button variant="success" @click="startScan()">Run Manual Scan</b-button>
      </b-col>
    </b-row>
    <hr />
    <b-progress  :max="100" show-progress class="mb-2" height="2rem">
    <b-progress-bar :value="(((data.match(/\./g) || []).length)/255)*100">
    <span><strong>{{ ((data.match(/\./g) || []).length / 255 * 100).toFixed(1) }}%</strong></span>
    </b-progress-bar>
    </b-progress>
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
    loadData: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "", auth).then((res) => {
        this.data = res;
        this.$forceUpdate();
        if (res.indexOf("Finished") == -1) {
          var el = this.$refs.textarea_1.$el;
          el.scrollTop = el.scrollHeight + 500;
          this.$forceUpdate();
          el = this.$refs.textarea_1.$el;
          el.scrollTop = el.scrollHeight + 500;
          this.$forceUpdate();
        }
      });
    },
    startScan: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", this.subnet);
      Helper.apiPost("scan", "", "", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: function () {
    try {
      this.loadData()
      setInterval(this.loadData, 2000);
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
