<template>
  <div
    class="connector"
    :style="
      'top: ' +
      1 * smaller +
      'px; left: ' +
      left +
      'px; position: absolute; float: left;'
    "
  >
    <!-- Repeated Top connector -->
    <svg
      height="50"
      :width="horizontal_width"
      style="position: relative; top: 66.5px; left: 50px"
    >
      <line
        x1="0"
        y1="0"
        :x2="horizontal_width"
        y2="0"
        :stroke="set_color"
        stroke-width="10"
      />
    </svg>

    <!-- Top turn -->
    <svg
      class="angle-connector float-right"
      width="50"
      height="50"
      fill="transparent"
      stroke-width="5"
      :stroke="set_color"
    >
      <circle cx="50" cy="50" r="30" />
    </svg>

    <!-- Repeated middle connectors -->

    <svg
      height="50"
      width="40"
      style="margin-left: 16.5px"
      v-for="idx in 1 * Math.floor((larger - smaller - 50) / 50)"
      v-bind:key="idx"
    >
      <line
        x1="0"
        y1="0"
        x2="0"
        y2="100"
        :stroke="set_color"
        stroke-width="10"
      />
    </svg>

    <!-- Bottom turn -->
    <svg
      class="angle-connector"
      width="50"
      fill="transparent"
      height="47.5"
      stroke-width="5"
      :stroke="set_color"
    >
      <circle cx="50" cy="0" r="30" />
    </svg>

    <!-- Repeated Bottom connector -->
    <svg
      height="50"
      :width="horizontal_width"
      style="position: relative; left: 50px; bottom: 20px"
    >
      <line
        x1="0"
        y1="0"
        :x2="horizontal_width"
        y2="0"
        :stroke="set_color"
        stroke-width="10"
      />
    </svg>
  </div>
</template>
<script>
import styles from "@/assets/variables.scss";
export default {
  name: "Connector",
  props: [
    "verticals",
    "horizontals",
    "color",

    "horizontal_width",
    "left",
    "top_1",
    "top_2",
  ],
  computed: {
    larger: function () {
      if (this.top_1 != undefined && this.top_2 != undefined) {
        return this.top_1 > this.top_2 ? this.top_1 : this.top_2;
      }
      return 0;
    },
    smaller: function () {
      if (this.top_1 != undefined && this.top_2 != undefined) {
        return this.top_1 < this.top_2 ? this.top_1 : this.top_2;
      }
      return 0;
    },
  },
  data() {
    return {
      set_color: "",
    };
  },
  created() {
    this.set_color = styles[this.color];
  },
};
</script>
<style scoped lang="scss">
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
