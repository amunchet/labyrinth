<template>
  <div class="vm-container-progress-bar">
    <div class="vm-title text-truncate" :title="item.name">
      <strong>{{ item.name || `ID ${item.id}` }}</strong>
      <span class="text-muted id-inline">({{ item.id }})</span>
    </div>

    <small v-if="showQemuWarning" class="text-danger d-block mb-1 qemu-warning">
      QEMU guest agent not installed or unavailable
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

    <div v-if="showMemory && hasMemInfo" class="metric-line">
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
    showMemory: {
      type: Boolean,
      default: false,
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
    showQemuWarning() {
      return (
        this.type === "vm" &&
        (
          this.item.qemu_guest_agent_installed === false ||
          this.item.qemu_guest_agent_warning_inferred === true
        )
      );
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

    .id-inline {
      font-weight: 400;
      margin-left: 0.2rem;
    }
  }

  .metric-line {
    line-height: 1.05;
  }

  .qemu-warning {
    font-size: 0.7rem;
    line-height: 1.05;
  }
}
</style>
