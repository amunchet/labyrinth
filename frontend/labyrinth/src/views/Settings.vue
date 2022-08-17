<template>
  <b-container class="mt-4">
    <b-card no-body>
      <b-tabs card pills>
        <b-tab title="Icons" lazy>
          <div class="main">
            <Icons />
          </div>
        </b-tab>
        <b-tab title="Telegraf" lazy>
          <div class="main">
            <Telegraf />
          </div>
        </b-tab>
      </b-tabs>
    </b-card>
  </b-container>
</template>
<script>
import Icons from "@/views/Settings/Icons";
import Telegraf from "@/views/Settings/Telegraf";
export default {
  name: "Settings",

  components: {
    Icons,
    Telegraf,
  },
};
</script>
<style lang="scss" scoped>
.main {
  min-height: 400px;
  text-align: center;
}
</style>
