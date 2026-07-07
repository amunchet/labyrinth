<template>
  <div class="vm-container-progress-bar">
    <b-row class="mb-2">
      <b-col lg="3">
        <strong>{{ item.name }}</strong>
        <br />
        <small class="text-muted">ID: {{ item.id }} | {{ type.toUpperCase() }}</small>
      </b-col>
      <b-col lg="9">
        <!-- Disk Usage -->
        <div v-if="hasDiskInfo" class="mb-2">
          <small><strong>Disk:</strong></small>
          <b-progress
            :value="diskUsagePercentage"
            :variant="diskProgressVariant"
            class="mb-1"
          ></b-progress>
          <small class="text-muted">
            {{ formatBytes(item.disk) }} / {{ formatBytes(item.maxdisk) }}
            ({{ diskUsagePercentage.toFixed(1) }}%)
          </small>
        </div>

        <!-- Memory Usage -->
        <div v-if="hasMemInfo">
          <small><strong>Memory:</strong></small>
          <b-progress
            :value="memUsagePercentage"
            :variant="memProgressVariant"
            class="mb-1"
          ></b-progress>
          <small class="text-muted">
            {{ formatBytes(item.mem) }} / {{ formatBytes(item.maxmem) }}
            ({{ memUsagePercentage.toFixed(1) }}%)
          </small>
        </div>
      </b-col>
    </b-row>
    <b-row v-if="item.status" class="mt-2">
      <b-col lg="12">
        <small class="text-muted">
          Status:
          <b-badge :variant="statusVariant">{{ item.status }}</b-badge>
        </small>
      </b-col>
    </b-row>
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
  padding: 0.5rem 0;
}
</style>
