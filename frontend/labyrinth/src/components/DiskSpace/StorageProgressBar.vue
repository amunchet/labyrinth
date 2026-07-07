<template>
  <div class="storage-progress-bar">
    <b-row class="mb-2">
      <b-col lg="3">
        <strong>{{ storage.name }}</strong>
        <br />
        <small class="text-muted">{{ storage.type }}</small>
      </b-col>
      <b-col lg="9">
        <b-progress
          :value="usagePercentage"
          :variant="progressVariant"
          class="mb-2"
        ></b-progress>
        <small class="text-muted">
          {{ formatBytes(storage.used) }} / {{ formatBytes(storage.total) }}
          ({{ usagePercentage.toFixed(1) }}%)
        </small>
      </b-col>
    </b-row>
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
  padding: 0.5rem 0;
}
</style>
