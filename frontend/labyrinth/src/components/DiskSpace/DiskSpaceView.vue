<template>
  <div class="disk-space-view text-left text-start">
    <b-row class="mb-3">
      <b-col class="text-left text-start">
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
        <small class="text-muted d-block mb-2">
          Hostname: {{ host.host || host.name || "N/A" }} | IP: {{ host.ip || "N/A" }}
        </small>
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
      <p>No disk space data available. Please configure hosts in Settings tab.</p>
    </b-alert>
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
    };
  },
  mounted() {
    this.refreshData();
  },
  methods: {
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

    async refreshData() {
      this.loading = true;
      this.error = null;

      try {
        const auth = this.$auth;
        // Fetch Proxmox data
        const proxmoxResponse = await Helper.apiCall("disk-space", "proxmox", auth);
        const proxmoxJson = this.parseMaybeJSON(proxmoxResponse);
        this.proxmoxData = proxmoxJson.proxmox_hosts || [];

        // Fetch manual hosts data
        const manualResponse = await Helper.apiCall("disk-space", "manual", auth);
        const manualJson = this.parseMaybeJSON(manualResponse);
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
    border-bottom: 2px solid #007bff;
    padding-bottom: 0.5rem;
  }
}
</style>
