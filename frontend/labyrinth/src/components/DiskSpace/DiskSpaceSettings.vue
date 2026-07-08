<template>
  <div class="disk-space-settings">
    <b-tabs pills card>
      <!-- Proxmox Clusters Tab -->
      <b-tab title="Proxmox Clusters" lazy>
        <div class="mt-3">
          <!-- Tag Configuration -->
          <b-card class="mb-4 text-left text-start">
            <b-card-title>Proxmox Tag</b-card-title>
            <b-card-sub-title>
              Hosts with this tag are included in disk space monitoring
            </b-card-sub-title>

            <b-form @submit.prevent="saveProxmoxTag">
              <b-form-group
                label="Tag name:"
                label-for="proxmox-tag"
                description="Default tag is Proxmox"
              >
                <b-form-input
                  id="proxmox-tag"
                  v-model="proxmoxTag"
                  placeholder="Proxmox"
                ></b-form-input>
              </b-form-group>

              <b-button variant="primary" type="submit" :disabled="savingTag">
                <b-spinner small v-if="savingTag" class="mr-2"></b-spinner>
                Save Tag
              </b-button>
            </b-form>
          </b-card>

          <!-- Add / Edit Cluster -->
          <b-card class="mb-4 text-left text-start">
            <b-card-title>
              {{ editingClusterId ? `Edit Cluster: ${newCluster.name}` : "Add Proxmox Cluster" }}
            </b-card-title>
            <b-card-sub-title>
              Define Proxmox cluster nodes and their API credentials
            </b-card-sub-title>

            <b-form @submit.prevent="submitClusterForm">
              <b-form-group
                label="Cluster Name:"
                label-for="cluster-name"
                description="Unique identifier for this cluster"
              >
                <b-form-input
                  id="cluster-name"
                  v-model="newCluster.name"
                  placeholder="e.g., production-pve"
                  :readonly="!!editingClusterId"
                  required
                ></b-form-input>
              </b-form-group>

              <b-form-group
                label="Host IP:"
                label-for="cluster-host"
                description="IP address of any cluster node"
              >
                <b-form-input
                  id="cluster-host"
                  v-model="newCluster.host"
                  placeholder="e.g., 10.1.1.1"
                  required
                ></b-form-input>
              </b-form-group>

              <b-form-group
                label="User:"
                label-for="cluster-user"
                description="Proxmox user (e.g., root@pam)"
              >
                <b-form-input
                  id="cluster-user"
                  v-model="newCluster.user"
                  placeholder="root@pam"
                  required
                ></b-form-input>
              </b-form-group>

              <b-form-group
                label="Token ID:"
                label-for="cluster-token-id"
                description="API token ID"
              >
                <b-form-input
                  id="cluster-token-id"
                  v-model="newCluster.token_id"
                  placeholder="e.g., token-1"
                  required
                ></b-form-input>
              </b-form-group>

              <b-form-group
                label="Token Secret:"
                label-for="cluster-token-secret"
                :description="editingClusterId ? 'Leave blank to keep the existing secret' : 'API token secret (keep secure)'"
              >
                <b-form-input
                  id="cluster-token-secret"
                  v-model="newCluster.token_secret"
                  type="password"
                  :placeholder="editingClusterId ? '(unchanged)' : 'e.g., abcd1234...'"
                  :required="!editingClusterId"
                ></b-form-input>
              </b-form-group>

              <b-form-group label="SSL Verification:">
                <b-form-checkbox v-model="newCluster.verify_ssl">
                  Verify SSL certificates
                </b-form-checkbox>
                <small class="text-muted">
                  Recommended for production; disable for self-signed
                  certificates
                </small>
              </b-form-group>

              <b-button
                variant="primary"
                type="submit"
                :disabled="addingCluster"
                class="mr-2"
              >
                <b-spinner small v-if="addingCluster" class="mr-2"></b-spinner>
                {{ editingClusterId ? "Save Changes" : "Add Cluster" }}
              </b-button>
              <b-button
                v-if="editingClusterId"
                variant="secondary"
                @click="cancelEdit"
              >
                Cancel
              </b-button>
            </b-form>
          </b-card>

          <!-- Configured Clusters -->
          <b-card v-if="clusters.length > 0" class="text-left text-start">
            <b-card-title>Configured Clusters</b-card-title>
            <b-list-group>
              <b-list-group-item v-for="cluster in clusters" :key="cluster._id">
                <b-row class="align-items-center">
                  <b-col lg="5">
                    <strong>{{ cluster.name }}</strong>
                    <br />
                    <small class="text-muted">
                      {{ cluster.user }}@{{ cluster.host }}
                    </small>
                  </b-col>
                  <b-col lg="3">
                    <small class="text-muted">
                      {{
                        cluster.verify_ssl ? "SSL verified" : "SSL unverified"
                      }}
                    </small>
                  </b-col>
                  <b-col lg="4" class="text-left">
                    <b-button
                      variant="outline-primary"
                      size="sm"
                      @click="editCluster(cluster)"
                      class="mr-2"
                    >
                      <b-icon icon="pencil"></b-icon>
                      Edit
                    </b-button>
                    <b-button
                      variant="danger"
                      size="sm"
                      @click="deleteCluster(cluster._id)"
                      :disabled="deletingCluster === cluster._id"
                    >
                      <b-spinner
                        small
                        v-if="deletingCluster === cluster._id"
                        class="mr-1"
                      ></b-spinner>
                      Delete
                    </b-button>
                  </b-col>
                </b-row>
              </b-list-group-item>
            </b-list-group>
          </b-card>

          <b-alert v-else variant="info" class="mt-3">
            No clusters configured yet.
          </b-alert>
        </div>
      </b-tab>

      <!-- Manual Hosts -->
      <b-tab title="Manual Hosts" lazy>
        <div class="mt-3">
          <!-- Add Existing Host -->
          <b-card class="mb-4 text-left text-start">
            <b-card-title>Add Existing Host</b-card-title>
            <b-card-sub-title>
              Pick an existing labyrinth host tagged or serviced as disk-check
            </b-card-sub-title>

            <b-form @submit.prevent="addSelectedHost">
              <b-form-group label="Search hosts:" label-for="host-search">
                <b-form-input
                  id="host-search"
                  v-model="hostSearch"
                  placeholder="Filter by name, IP, tag, or service"
                ></b-form-input>
              </b-form-group>

              <b-form-group label="Available Hosts:" label-for="host-select">
                <b-form-select
                  id="host-select"
                  v-model="selectedHostId"
                  :options="availableHostOptions"
                  :disabled="availableHostOptions.length === 0"
                  required
                ></b-form-select>
              </b-form-group>

              <b-alert v-if="availableHostOptions.length === 0" variant="info" class="mb-3">
                No disk-check hosts were found. Showing all hosts is not currently enabled for this environment.
              </b-alert>

              <b-form-group
                v-if="selectedHost"
                label="Selected Host Preview:"
                label-for="host-preview"
              >
                <div id="host-preview" class="text-muted small">
                  <div><strong>{{ selectedHostDisplayName }}</strong></div>
                  <div>{{ selectedHost.ip || "N/A" }}</div>
                  <div v-if="selectedHost.tags">Tags: {{ selectedHost.tags }}</div>
                  <div v-if="selectedHost.services && selectedHost.services.length">
                    Services: {{ selectedHost.services.join(", ") }}
                  </div>
                </div>
              </b-form-group>

              <b-button variant="primary" type="submit" :disabled="addingHost || !selectedHostId">
                <b-spinner small v-if="addingHost" class="mr-2"></b-spinner>
                Add Host
              </b-button>
            </b-form>
          </b-card>

          <!-- Existing Manual Hosts -->
          <b-card v-if="manualHosts.length > 0" class="text-left text-start">
            <b-card-title>Selected Hosts</b-card-title>
            <b-list-group>
              <b-list-group-item v-for="host in manualHosts" :key="host.id">
                <b-row class="align-items-start">
                  <b-col lg="8">
                    <strong>{{ host.name }}</strong>
                    <br />
                    <small class="text-muted">
                      {{ host.ip }} | {{ host.type }}
                    </small>
                    <br />
                    <small v-if="host.description" class="text-muted">
                      {{ host.description }}
                    </small>
                  </b-col>
                  <b-col lg="4" class="text-left">
                    <b-button
                      variant="danger"
                      size="sm"
                      @click="deleteManualHost(host.id)"
                    >
                      <b-icon icon="trash"></b-icon>
                      Delete
                    </b-button>
                  </b-col>
                </b-row>
              </b-list-group-item>
            </b-list-group>
          </b-card>

          <b-alert v-else variant="info" class="mt-3">
            No manual hosts configured yet.
          </b-alert>
        </div>
      </b-tab>

      <!-- Documentation -->
      <b-tab title="Documentation" lazy>
        <div class="mt-3">
          <ProxmoxDocumentation />
        </div>
      </b-tab>
    </b-tabs>

    <!-- Alert Messages -->
    <b-alert
      v-if="successMessage"
      variant="success"
      dismissible
      @dismissed="successMessage = null"
      class="mt-3"
    >
      {{ successMessage }}
    </b-alert>
    <b-alert
      v-if="errorMessage"
      variant="danger"
      dismissible
      @dismissed="errorMessage = null"
      class="mt-3"
    >
      {{ errorMessage }}
    </b-alert>
  </div>
</template>

<script>
import Helper from "@/helper";
import ProxmoxDocumentation from "./ProxmoxDocumentation";

export default {
  name: "DiskSpaceSettings",
  components: {
    ProxmoxDocumentation,
  },
  data() {
    return {
      proxmoxTag: "Proxmox",
      clusters: [],
      newCluster: {
        name: "",
        host: "",
        user: "root@pam",
        token_id: "",
        token_secret: "",
        verify_ssl: false,
      },
      editingCluster: null,
      editingClusterId: null,
      addingCluster: false,
      deletingCluster: null,
      savingTag: false,
        availableHosts: [],
        hostSearch: "",
        selectedHostId: "",
      manualHosts: [],
      addingHost: false,
      successMessage: "",
      errorMessage: "",
    };
  },
  mounted() {
    this.loadSettings();
  },
  computed: {
    filteredAvailableHosts() {
      const search = this.hostSearch.trim().toLowerCase();
      if (!search) {
        return this.availableHosts;
      }

      return this.availableHosts.filter((host) => {
        const haystack = [
          host._id,
          host.host,
          host.name,
          host.ip,
          host.mac,
          host.tags,
          Array.isArray(host.services) ? host.services.join(" ") : "",
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        return haystack.includes(search);
      });
    },
    availableHostOptions() {
      return this.filteredAvailableHosts.map((host) => ({
        value: host._id,
        text: this.hostDisplayName(host),
      }));
    },
    selectedHost() {
      return this.availableHosts.find((host) => host._id === this.selectedHostId);
    },
    selectedHostDisplayName() {
      return this.selectedHost ? this.hostDisplayName(this.selectedHost) : "";
    },
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

    async loadSettings() {
      try {
        const auth = this.$auth;
        const settingsResponse = await Helper.apiCall(
          "disk-space",
          "settings",
          auth
        );
        const data = this.parseMaybeJSON(settingsResponse);

        this.proxmoxTag = data.proxmox_tag || "Proxmox";
        this.clusters = data.clusters || [];

        let hostsResponse = await Helper.apiCall("hosts", "disk-check", auth);
        let hostsData = this.parseMaybeJSON(hostsResponse);
        this.availableHosts = Array.isArray(hostsData) ? hostsData : [];

        if (!this.availableHosts.length) {
          hostsResponse = await Helper.apiCall("hosts", "", auth);
          hostsData = this.parseMaybeJSON(hostsResponse);
          this.availableHosts = Array.isArray(hostsData) ? hostsData : [];
        }

        this.selectedHostId = this.availableHostOptions.length > 0 ? this.availableHostOptions[0].value : "";

        // Load manual hosts
        const manualResponse = await Helper.apiCall(
          "disk-space",
          "manual",
          auth
        );
        const manualData = this.parseMaybeJSON(manualResponse);
        this.manualHosts = manualData.manual_hosts || [];
      } catch (err) {
        this.errorMessage = err.message;
      }
    },

    async saveProxmoxTag() {
      if (!this.proxmoxTag.trim()) {
        this.errorMessage = "Tag cannot be empty";
        return;
      }

      this.savingTag = true;
      try {
        const auth = this.$auth;
        const formData = new FormData();
        formData.append("name", "proxmox_tag");
        formData.append("value", this.proxmoxTag);

        await Helper.apiPost("settings", "", "", auth, formData);

        this.successMessage = "Proxmox tag saved successfully!";
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.savingTag = false;
      }
    },

    hostDisplayName(host) {
      const label = host.host || host.name || host.ip || host.mac || host._id || "Unknown host";
      const ip = host.ip ? ` (${host.ip})` : "";
      return `${label}${ip}`;
    },

    async submitClusterForm() {
      if (this.editingClusterId) {
        await this.saveClusterEdit();
      } else {
        await this.addCluster();
      }
    },

    async addCluster() {
      if (
        !this.newCluster.name ||
        !this.newCluster.host ||
        !this.newCluster.token_id ||
        !this.newCluster.token_secret
      ) {
        this.errorMessage = "Please fill in all required fields";
        return;
      }

      this.addingCluster = true;
      try {
        const auth = this.$auth;
        const body = JSON.stringify(this.newCluster);
        await Helper.apiPost("proxmox-clusters", "", "", auth, body);

        this.successMessage = "Proxmox cluster added successfully!";
        this.resetClusterForm();
        await this.loadSettings();
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.addingCluster = false;
      }
    },

    editCluster(cluster) {
      this.editingClusterId = cluster._id;
      this.newCluster = {
        name: cluster.name,
        host: cluster.host,
        user: cluster.user,
        token_id: cluster.token_id,
        token_secret: "",
        verify_ssl: cluster.verify_ssl || false,
      };
      // Scroll up to the form
      this.$nextTick(() => {
        const el = document.getElementById("cluster-name");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    },

    async saveClusterEdit() {
      this.addingCluster = true;
      try {
        const auth = this.$auth;

        const payload = {
          host: this.newCluster.host,
          user: this.newCluster.user,
          token_id: this.newCluster.token_id,
          verify_ssl: this.newCluster.verify_ssl,
        };
        if (this.newCluster.token_secret) {
          payload.token_secret = this.newCluster.token_secret;
        }

        await Helper.apiPut(
          "proxmox-clusters",
          this.editingClusterId,
          auth,
          payload
        );

        this.successMessage = "Cluster updated successfully!";
        this.resetClusterForm();
        await this.loadSettings();
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.addingCluster = false;
      }
    },

    cancelEdit() {
      this.resetClusterForm();
    },

    resetClusterForm() {
      this.editingClusterId = null;
      this.newCluster = {
        name: "",
        host: "",
        user: "root@pam",
        token_id: "",
        token_secret: "",
        verify_ssl: false,
      };
    },

    async deleteCluster(clusterId) {
      if (!confirm("Delete this Proxmox cluster configuration?")) return;

      this.deletingCluster = clusterId;
      try {
        const auth = this.$auth;
        await Helper.apiDelete("proxmox-clusters", clusterId, auth);

        this.successMessage = "Proxmox cluster deleted successfully!";
        await this.loadSettings();
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.deletingCluster = null;
      }
    },

    async addSelectedHost() {
      const selectedHost = this.selectedHost;
      if (!selectedHost) {
        this.errorMessage = "Please select a host";
        return;
      }

      this.addingHost = true;
      try {
        const auth = this.$auth;
        const formData = new FormData();
        formData.append("name", selectedHost.host || selectedHost.name || selectedHost.ip);
        formData.append("ip", selectedHost.ip || "");
        formData.append("type", "disk-check");
        formData.append(
          "description",
          `Selected from existing host${selectedHost.tags ? ` | Tags: ${selectedHost.tags}` : ""}`
        );
        await Helper.apiPost("disk-space", "manual", "", auth, formData);

        this.successMessage = "Manual host added successfully!";
        this.selectedHostId = this.availableHostOptions.length > 0 ? this.availableHostOptions[0].value : "";
        await this.loadSettings();
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.addingHost = false;
      }
    },

    async deleteManualHost(hostId) {
      if (!confirm("Delete this manual host?")) return;

      try {
        const auth = this.$auth;
        await Helper.apiDelete("disk-space/manual", hostId, auth);

        this.successMessage = "Manual host deleted successfully!";
        await this.loadSettings();
      } catch (err) {
        this.errorMessage = err.message;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.disk-space-settings {
  b-card {
    margin-bottom: 1rem;
  }
}
</style>
