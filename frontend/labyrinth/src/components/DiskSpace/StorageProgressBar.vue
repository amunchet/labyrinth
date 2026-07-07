<template>
  <div class="storage-progress-bar">
    <div class="storage-name text-truncate" :title="storage.name">
      <strong>{{ storage.name }}</strong>
      <small class="text-muted d-block">{{ storage.type }}</small>
    </div>
    <b-progress
      :value="usagePercentage"
      :variant="progressVariant"
      height="10px"
      class="mb-1"
    ></b-progress>
    <small class="text-muted storage-meta d-block">
      {{ formatBytes(storage.used) }} / {{ formatBytes(storage.total) }}
    </small>
    <small class="text-muted d-block">{{ usagePercentage.toFixed(1) }}%</small>
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
    progressVariant() {
      if (this.usagePercentage >= 90) return "danger";
      if (this.usagePercentage >= 75) return "warning";
      return "success";
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
.storage-progress-bar {
  padding: 0.1rem 0;

  .storage-name {
    line-height: 1.1;
    margin-bottom: 0.25rem;
    font-size: 0.78rem;
  }

  .storage-meta {
    line-height: 1.05;
    font-size: 0.72rem;
  }
}
</style>
