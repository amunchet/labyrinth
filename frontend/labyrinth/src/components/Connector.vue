<template>
  <div class="connector">
    <!-- Repeated Top connector -->
    <svg
      height="50"
      :width="50 * horizontals"
      style="position: relative; top: 60px; left: 50px"
    >
      <line x1="0" y1="0" :x2="50 * horizontals" y2="0" :stroke="color" stroke-width="20" />
    </svg>

    <!-- Top turn -->
    <svg
      class="angle-connector float-right"
      width="50"
      height="50"
      fill="transparent"
      stroke-width="10"
      :stroke="color"
    >
      <circle cx="50" cy="50" r="35" />
    </svg>

    <!-- Repeated middle connectors -->

    <svg height="50" width="50" style="margin-left: 10px" v-for="idx in (1 * verticals)" v-bind:key="idx">
      <line x1="0" y1="0" x2="0" y2="100" :stroke="color" stroke-width="20" />
    </svg>

    <!-- Bottom turn -->
    <svg
      class="angle-connector"
      width="50"
      fill="transparent"
      height="50"
      stroke-width="10"
      :stroke="color"
    >
      <circle cx="50" cy="0" r="35" />
    </svg>

    <!-- Repeated Bottom connector -->
    <svg
      height="50"
      :width="50 * horizontals"
      style="position: relative; left: 50px; bottom: 20px"
    >
      <line x1="0" y1="0" :x2="50 * horizontals " y2="0" :stroke="color" stroke-width="20" />
    </svg>
  </div>
</template>
<script>
export default {
  name: "Connector",
  props: ["verticals", "horizontals", "color"]
};
</script>
<style scoped>
/* SVGs */
svg {
}
.angle-connector {
}

.connector {
  display: -ms-inline-grid;
  display: -moz-inline-grid;
  display: inline-grid;
  position: relative;
}
</style>
