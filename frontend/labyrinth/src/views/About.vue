<template>
  <div class="about">
    <hr />

    <div class="connector">
      <!-- Repeated Top connector -->
      <svg
        height="50"
        width="50"
        style="position: relative; top: 60px; left: 50px"
      >
        <line x1="0" y1="0" x2="100" y2="0" stroke="green" stroke-width="20" />
      </svg>

      <!-- Top turn -->
      <svg
        class="angle-connector float-right"
        width="50"
        height="50"
        fill="transparent"
        stroke-width="10"
        stroke="green"
      >
        <circle cx="50" cy="50" r="35" />
      </svg>

      <!-- Repeated middle connectors -->

      <svg height="50" width="50" style="margin-left: 10px;">
        <line x1="0" y1="0" x2="0" y2="100" stroke="green" stroke-width="20" />
      </svg>
      <svg height="50" width="50" style="margin-left: 10px;">
        <line x1="0" y1="0" x2="0" y2="100" stroke="green" stroke-width="20" />
      </svg>

      <!-- Bottom turn -->
      <svg
        class="angle-connector"
        width="50"
        fill="transparent"
        height="50"
        stroke-width="10"
        stroke="green"
      >
        <circle cx="50" cy="0" r="35" />
      </svg>

      <!-- Repeated Bottom connector -->
      <svg
        height="50"
        width="50"
        style="position: relative; left: 50px; bottom: 20px"
      >
        <line x1="0" y1="0" x2="100" y2="0" stroke="green" stroke-width="20" />
      </svg>
    </div>
  </div>
</template>
<script>
export default {
  data() {},
};
</script>
<style scoped>
* {
  padding: 0;
  margin: 0;
}
/* SVGs */
svg {
}
.angle-connector {
}

.connector {
  width: 100px;
  display: -ms-inline-grid;
  display: -moz-inline-grid;
  display: inline-grid;
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
