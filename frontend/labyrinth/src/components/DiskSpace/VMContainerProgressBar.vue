<template>
  <div class="vm-container-progress-bar">
    <div class="vm-title text-truncate" :title="item.name">
      <strong>{{ item.name || `ID ${item.id}` }}</strong>
    </div>
    <small class="text-muted d-block mb-1">
      ID: {{ item.id }} | {{ type.toUpperCase() }}
      <span v-if="item.status">
        | <b-badge :variant="statusVariant" class="compact-status">{{ item.status }}</b-badge>
      </span>
    </small>

    <div v-if="hasDiskInfo" class="metric-line mb-1">
      <small class="text-muted d-block">Disk {{ diskUsagePercentage.toFixed(0) }}%</small>
      <b-progress
        :value="diskUsagePercentage"
        :variant="diskProgressVariant"
        height="8px"
        class="mb-1"
      ></b-progress>
    </div>

    <div v-if="hasMemInfo" class="metric-line">
      <small class="text-muted d-block">Mem {{ memUsagePercentage.toFixed(0) }}%</small>
      <b-progress
        :value="memUsagePercentage"
        :variant="memProgressVariant"
        height="8px"
      ></b-progress>
    </div>
  </div>
</template>

<script>
export default {
  name: "VMContainerProgressBar",
  props: {
    item: {
      type: Object,
      required: true,
    },
    type: {
      type: String,
      required: true,
      validator: (value) => ["vm", "container"].includes(value),
    },
  },
  computed: {
    hasDiskInfo() {
      return this.item.disk !== null && this.item.disk !== undefined;
    },
    hasMemInfo() {
      return this.item.mem !== null && this.item.mem !== undefined;
    },
    diskUsagePercentage() {
      if (!this.hasDiskInfo || !this.item.maxdisk || this.item.maxdisk === 0) {
        return 0;
      }
      return (this.item.disk / this.item.maxdisk) * 100;
    },
    memUsagePercentage() {
      if (!this.hasMemInfo || !this.item.maxmem || this.item.maxmem === 0) {
        return 0;
      }
      return (this.item.mem / this.item.maxmem) * 100;
    },
    diskProgressVariant() {
      if (this.diskUsagePercentage >= 90) return "danger";
      if (this.diskUsagePercentage >= 75) return "warning";
      return "success";
    },
    memProgressVariant() {
      if (this.memUsagePercentage >= 90) return "danger";
      if (this.memUsagePercentage >= 75) return "warning";
      return "success";
    },
    statusVariant() {
      if (this.item.status === "running") return "success";
      if (this.item.status === "stopped") return "secondary";
      return "warning";
    },
  },
  methods: {
    formatBytes(bytes) {
      if (bytes === 0 || !bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    },
  },
};
</script>

<style lang="scss" scoped>
.vm-container-progress-bar {
  padding: 0.1rem 0;

  .vm-title {
    font-size: 0.8rem;
    line-height: 1.1;
    margin-bottom: 0.1rem;
  }

  .metric-line {
    line-height: 1.05;
  }

  .compact-status {
    font-size: 0.62rem;
    padding: 0.1rem 0.25rem;
  }
}
</style>
