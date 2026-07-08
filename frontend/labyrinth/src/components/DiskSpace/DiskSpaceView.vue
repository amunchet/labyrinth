<template>
  <div class="disk-space-view text-left text-start">
    <!-- Error Alert -->
    <b-alert v-if="error" variant="danger" dismissible @dismissed="error = null">
      {{ error }}
    </b-alert>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state text-center py-5">
      <b-spinner variant="primary" style="width: 3rem; height: 3rem;" class="mb-3"></b-spinner>
      <p class="text-muted">Loading disk space data...</p>
    </div>

    <template v-else>
      <!-- Proxmox Hosts Section -->
      <div v-if="proxmoxData.length > 0" class="mb-4">
        <b-row class="align-items-center mb-3">
          <b-col>
            <h4 class="mb-0">
              <b-icon icon="server"></b-icon>
              Proxmox Clusters
            </h4>
          </b-col>
          <b-col cols="auto">
            <b-button
              variant="outline-secondary"
              size="sm"
              @click="refreshData"
              :disabled="loading"
            >
              <font-awesome-icon icon="sync" class="mr-1" />
              Refresh
            </b-button>
          </b-col>
        </b-row>
        <b-card
          v-for="host in proxmoxData"
          :key="`proxmox-${host._id || host.cluster_name}`"
          class="mb-2"
          body-class="py-2 px-3"
        >
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
          <small class="text-muted d-block mb-2">
            Hostname: {{ host.host || host.name || "N/A" }} | IP: {{ host.ip || "N/A" }}
          </small>
          <ManualHostCard :host="host" @delete="deleteManualHost" />
        </b-card>
      </div>

      <!-- Empty State -->
      <b-alert v-if="proxmoxData.length === 0 && manualData.length === 0" variant="info">
        <b-row class="align-items-center">
          <b-col>No disk space data available. Please configure Proxmox clusters in the Settings tab.</b-col>
          <b-col cols="auto">
            <b-button variant="outline-secondary" size="sm" @click="refreshData">
              <font-awesome-icon icon="sync" class="mr-1" />
              Refresh
            </b-button>
          </b-col>
        </b-row>
      </b-alert>
    </template>
  </div>
</template>

<script>
import Helper from "@/helper";
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
      autoRefreshTimer: null,
    };
  },
  mounted() {
    this.startAutoRefresh();
  },
  beforeDestroy() {
    this.stopAutoRefresh();
  },
  activated() {
    this.startAutoRefresh();
  },
  deactivated() {
    this.stopAutoRefresh();
  },
  methods: {
    scheduleNextRefresh() {
      this.stopAutoRefresh();
      this.autoRefreshTimer = window.setTimeout(() => {
        this.refreshData();
      }, 30000);
    },

    startAutoRefresh() {
      this.refreshData();
    },

    stopAutoRefresh() {
      if (this.autoRefreshTimer) {
        window.clearTimeout(this.autoRefreshTimer);
        this.autoRefreshTimer = null;
      }
    },

    parseMaybeJSON(payload) {
      if (typeof payload === "string") {
        try {
          return JSON.parse(payload);
        } catch (e) {
          return payload;
        }
      }
      return payload;
    },

    getHostName(host) {
      return (host && (host.cluster_name || host.host || "")).toString().toLowerCase();
    },

    sortProxmoxHosts(hosts) {
      return [...(hosts || [])].sort((a, b) =>
        this.getHostName(a).localeCompare(this.getHostName(b))
      );
    },

    async refreshData() {
      this.stopAutoRefresh();

      if (this.loading) {
        this.scheduleNextRefresh();
        return;
      }

      this.loading = true;
      this.error = null;

      try {
        const auth = this.$auth;
        // Fetch Proxmox data
        const proxmoxResponse = await Helper.apiCall("disk-space", "proxmox", auth);
        const proxmoxJson = this.parseMaybeJSON(proxmoxResponse);
        this.proxmoxData = this.sortProxmoxHosts(proxmoxJson.proxmox_hosts || []);

        // Fetch manual hosts data
        const manualResponse = await Helper.apiCall("disk-space", "manual", auth);
        const manualJson = this.parseMaybeJSON(manualResponse);
        this.manualData = manualJson.manual_hosts || [];
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
        this.scheduleNextRefresh();
      }
    },

    async deleteManualHost(hostId) {
      if (!confirm("Are you sure you want to delete this host?")) {
        return;
      }

      try {
        const auth = this.$auth;
        await Helper.apiDelete("disk-space/manual", hostId, auth);

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
    padding-bottom: 0.5rem;
  }
}
</style>
