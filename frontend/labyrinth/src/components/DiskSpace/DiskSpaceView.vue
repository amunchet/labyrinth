<template>
  <div class="disk-space-view">
    <b-row class="mb-3">
      <b-col>
        <b-button
          variant="primary"
          @click="refreshData"
          :disabled="loading"
        >
          <b-spinner small v-if="loading" class="mr-2"></b-spinner>
          Refresh
        </b-button>
      </b-col>
    </b-row>

    <!-- Error Alert -->
    <b-alert v-if="error" variant="danger" dismissible @dismissed="error = null">
      {{ error }}
    </b-alert>

    <!-- Proxmox Hosts Section -->
    <div v-if="proxmoxData.length > 0" class="mb-4">
      <h4>
        <b-icon icon="server"></b-icon>
        Proxmox Hosts
      </h4>
      <b-card v-for="host in proxmoxData" :key="`proxmox-${host.ip}`" class="mb-3">
        <ProxmoxHostCard :host="host" />
      </b-card>
    </div>

    <!-- Manual Hosts Section -->
    <div v-if="manualData.length > 0" class="mb-4">
      <h4>
        <b-icon icon="cloud"></b-icon>
        Manually Configured Hosts
      </h4>
      <b-card v-for="host in manualData" :key="`manual-${host.id}`" class="mb-3">
        <ManualHostCard :host="host" @delete="deleteManualHost" />
      </b-card>
    </div>

    <!-- Empty State -->
    <b-alert v-if="proxmoxData.length === 0 && manualData.length === 0" variant="info">
      <p>No disk space data available. Please configure hosts in Settings tab.</p>
    </b-alert>
  </div>
</template>

<script>
import ProxmoxHostCard from "./ProxmoxHostCard";
import ManualHostCard from "./ManualHostCard";

export default {
  name: "DiskSpaceView",
  components: {
    ProxmoxHostCard,
    ManualHostCard,
  },
  data() {
    return {
      loading: false,
      error: null,
      proxmoxData: [],
      manualData: [],
    };
  },
  mounted() {
    this.refreshData();
  },
  methods: {
    async refreshData() {
      this.loading = true;
      this.error = null;

      try {
        // Fetch Proxmox data
        const proxmoxResponse = await fetch("/disk-space/proxmox");
        if (!proxmoxResponse.ok) {
          throw new Error("Failed to fetch Proxmox data");
        }
        const proxmoxJson = await proxmoxResponse.json();
        this.proxmoxData = proxmoxJson.proxmox_hosts || [];

        // Fetch manual hosts data
        const manualResponse = await fetch("/disk-space/manual");
        if (!manualResponse.ok) {
          throw new Error("Failed to fetch manual hosts data");
        }
        const manualJson = await manualResponse.json();
        this.manualData = manualJson.manual_hosts || [];
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    async deleteManualHost(hostId) {
      if (!confirm("Are you sure you want to delete this host?")) {
        return;
      }

      try {
        const response = await fetch(`/disk-space/manual/${hostId}`, {
          method: "DELETE",
        });

        if (!response.ok) {
          throw new Error("Failed to delete host");
        }

        await this.refreshData();
      } catch (err) {
        this.error = err.message;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.disk-space-view {
  h4 {
    margin-top: 2rem;
    margin-bottom: 1rem;
    border-bottom: 2px solid #007bff;
    padding-bottom: 0.5rem;
  }
}
</style>
