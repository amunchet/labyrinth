<template>
  <b-container>
    <b-tabs content-class="mt-3">
      <b-tab title="First" active>
        <p>I'm the first tab</p>
        <h2>Contact Information</h2>
        <h2>Options</h2>
        <ul>
          <li>Frequency</li>
          <li>Grouping by hosts, services, summary, etc?</li>
        </ul>
      </b-tab>
      <b-tab title="Second">
        <p>I'm the second tab</p>
        <iframe :src="frame_url.replace('api', 'alertmanager')" />
      </b-tab>
      <b-tab title="Disabled" disabled><p>I'm a disabled tab!</p></b-tab>
    </b-tabs>
  </b-container>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Alerts",
  data() {
    return {
      frame_url: "",
    };
  },
  mounted: function () {
    this.frame_url = Helper.getURL();
  },
};
</script>
<style lang="scss" scoped>
iframe {
  width: 100%;
  min-height: 500px;
  overflow-y: scroll;
}
</style>
