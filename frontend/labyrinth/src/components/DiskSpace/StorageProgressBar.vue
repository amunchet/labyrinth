<template>
  <div class="storage-tile" :class="usageClass" :title="tooltipText">
    <span class="storage-name text-truncate">{{ storage.name }}</span>
    <span class="storage-percent">{{ usagePercentage.toFixed(0) }}%</span>
  </div>
</template>

<script>
export default {
  name: "StorageProgressBar",
  props: {
    storage: {
      type: Object,
      required: true,
    },
  },
  computed: {
    usagePercentage() {
      if (
        !this.storage.total ||
        this.storage.total === 0 ||
        !this.storage.used
      ) {
        return 0;
      }
      return (this.storage.used / this.storage.total) * 100;
    },
    usageClass() {
      if (this.usagePercentage >= 90) return "usage-danger";
      if (this.usagePercentage >= 75) return "usage-warning";
      return "usage-success";
    },
    tooltipText() {
      const type = this.storage.type ? ` (${this.storage.type})` : "";
      return `${this.storage.name}${type}: ${this.formatBytes(this.storage.used)} / ${this.formatBytes(this.storage.total)} (${this.usagePercentage.toFixed(1)}%)`;
    },
  },
  methods: {
    formatBytes(bytes) {
      if (bytes === 0 || !bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    },
  },
};
</script>

<style lang="scss" scoped>
.storage-tile {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 0.74rem;
  line-height: 1.3;
  cursor: default;

  .storage-name {
    min-width: 0;
    font-weight: 600;
  }

  .storage-percent {
    flex-shrink: 0;
    font-weight: 700;
  }

  &.usage-success {
    background-color: #28a745;
    color: #fff;
  }

  &.usage-warning {
    background-color: #FFA500;
    color: #000;
  }

  &.usage-danger {
    background-color: #dc3545;
    color: #fff;
  }
}
</style>
