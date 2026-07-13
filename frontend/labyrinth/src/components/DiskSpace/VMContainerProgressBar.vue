<template>
  <div class="vm-tile" :class="diskUsageClass" :title="tooltipText">
    <font-awesome-icon
      v-if="showQemuWarning"
      icon="exclamation-triangle"
      class="qemu-warning-icon mr-1"
      v-b-tooltip.hover
      title="QEMU Guest Agent not installed or unavailable."
    />
    <span class="vm-name text-truncate">{{
      item.name || `ID ${item.id}`
    }}</span>
    <span class="vm-metrics">
      <span v-if="hasDiskInfo">{{ diskUsagePercentage.toFixed(0) }}%</span>
      <span
        v-if="showMemory && hasMemInfo"
        class="mem-metric"
        :class="memUsageClass"
      >
        · {{ memUsagePercentage.toFixed(0) }}% mem
      </span>
    </span>
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
    diskUsageClass() {
      if (!this.hasDiskInfo) return "usage-unknown";
      if (this.diskUsagePercentage >= 90) return "usage-danger";
      if (this.diskUsagePercentage >= 75) return "usage-warning";
      return "usage-success";
    },
    memUsageClass() {
      if (this.memUsagePercentage >= 90) return "usage-danger-text";
      if (this.memUsagePercentage >= 75) return "usage-warning-text";
      return "";
    },
    showQemuWarning() {
      return (
        this.type === "vm" &&
        (this.item.qemu_guest_agent_installed === false ||
          this.item.qemu_guest_agent_warning_inferred === true)
      );
    },
    tooltipText() {
      const label = this.item.name || `ID ${this.item.id}`;
      const parts = [`${label} (${this.item.id})`];
      if (this.hasDiskInfo) {
        parts.push(
          `Disk: ${this.formatBytes(this.item.disk)} / ${this.formatBytes(
            this.item.maxdisk
          )} (${this.diskUsagePercentage.toFixed(1)}%)`
        );
      }
      if (this.showMemory && this.hasMemInfo) {
        parts.push(
          `Mem: ${this.formatBytes(this.item.mem)} / ${this.formatBytes(
            this.item.maxmem
          )} (${this.memUsagePercentage.toFixed(1)}%)`
        );
      }
      return parts.join(" | ");
    },
  },
  methods: {
    formatBytes(bytes) {
      if (bytes === 0 || !bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return (
        Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
      );
    },
  },
};
</script>

<style lang="scss" scoped>
.vm-tile {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 0.74rem;
  line-height: 1.3;
  cursor: default;

  .vm-name {
    min-width: 0;
    font-weight: 600;
    flex-shrink: 1;
  }

  .vm-metrics {
    flex-shrink: 0;
    margin-left: auto;
    font-weight: 700;
    white-space: nowrap;
  }

  .mem-metric {
    font-weight: 500;
    opacity: 0.9;
  }

  .qemu-warning-icon {
    color: #fff3cd;
    flex-shrink: 0;
  }

  &.usage-success {
    background-color: #28a745;
    color: #fff;
  }

  &.usage-warning {
    background-color: #ffa500;
    color: #000;

    .qemu-warning-icon {
      color: #dc3545;
    }
  }

  &.usage-danger {
    background-color: #dc3545;
    color: #fff;
  }

  &.usage-unknown {
    background-color: #e9ecef;
    color: #495057;

    .qemu-warning-icon {
      color: #dc3545;
    }
  }

  .usage-warning-text {
    color: #fff3cd;
  }

  .usage-danger-text {
    color: #f8d7da;
  }
}
</style>
