<template>
  <div class="about">
    <hr />

    <Connector
      verticals="10"
      horizontals="4"
      color="green"
      style="top: 20px; left: 20px"
      v-if="false"
    />
    <Connector verticals="10" horizontals="3" color="orange" v-if="false" />

    <div class="outer">
      <div class="left">
        <div class="corner">
          <Host />
        </div>
        <div class="routes">
          <Host />
        </div>
      </div>

      <div class="right">
        <div class="grouped">
          <Host />
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import Connector from "@/components/Connector";
import Host from "@/components/Host";
export default {
  data() {},
  components: {
    Connector,
    Host
  },
};
</script>
<style>
* {
  padding: 0;
  margin: 0;
  background-color: #fffeff;
}

/* Color Theme Swatches in Hex */
.lightblue {
  color: #83d3df;
}
.red {
  color: #db7077;
}
.orange {
  color: #ffab71;
}
.darkblue {
  color: #375775;
}
.superlight {
  color: #d8faff;
}
</style>
