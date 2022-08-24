<template>
  <b-container class="mt-4">
    <b-card no-body>
      <b-tabs card pills>
        <b-tab title="Visuals" lazy>
          <div class="main">
            <Icons :time="set_time" @reload="() => (set_time = Date.now())" />
          </div>
        </b-tab>
        <b-tab title="Telegraf" lazy>
          <div class="main">
            <Telegraf />
          </div>
        </b-tab>
        <b-tab title="Custom Dashboards" lazy>
          <div class="main">
            <CustomDashboards />
          </div>
        </b-tab>
      </b-tabs>
    </b-card>
  </b-container>
</template>
<script>
import Icons from "@/views/Settings/Icons";
import Telegraf from "@/views/Settings/Telegraf";
import CustomDashboards from "@/views/Settings/CustomDashboards";
export default {
  name: "Settings",
  data() {
    return {
      set_time: Date.now(),
    };
  },
  components: {
    Icons,
    Telegraf,
    CustomDashboards,
  },
};
</script>
<style lang="scss" scoped>
.main {
  min-height: 400px;
  text-align: center;
}
</style>
