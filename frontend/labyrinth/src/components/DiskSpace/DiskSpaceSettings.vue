<template>
  <div class="disk-space-settings">
    <b-tabs pills card>
      <!-- Proxmox Settings -->
      <b-tab title="Proxmox Configuration" lazy>
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

          <!-- Global API Key Section -->
          <b-card class="mb-4 text-start text-left">
            <b-card-title>Global Proxmox API Key</b-card-title>
            <b-card-sub-title>
              Applied to all Proxmox hosts unless overridden at host level
            </b-card-sub-title>

            <b-form @submit.prevent="saveGlobalApiKey">
              <b-form-group
                label="API Key:"
                label-for="global-api-key"
                description="Format: user@pam!token_id=token_secret"
              >
                <b-form-input
                  id="global-api-key"
                  v-model="globalApiKey"
                  type="password"
                  placeholder="Enter API key"
                ></b-form-input>
              </b-form-group>

              <b-button variant="primary" type="submit" :disabled="savingGlobalKey">
                <b-spinner small v-if="savingGlobalKey" class="mr-2"></b-spinner>
                Save Global Key
              </b-button>

              <b-button
                v-if="globalKeyConfigured"
                variant="danger"
                @click="deleteGlobalApiKey"
                :disabled="savingGlobalKey"
                class="ml-2"
              >
                Delete Key
              </b-button>

              <b-alert
                v-if="globalKeyConfigured"
                variant="success"
                class="mt-2 mb-0"
              >
                Global API key is configured
              </b-alert>
            </b-form>
          </b-card>

          <!-- Host-Specific Keys Section -->
          <b-card v-if="proxmoxHosts.length > 0" class="text-start text-left">
            <b-card-title>Host-Specific API Keys</b-card-title>
            <b-card-sub-title>
              Override global key for specific Proxmox hosts
            </b-card-sub-title>

            <b-list-group>
              <b-list-group-item v-for="host in proxmoxHosts" :key="host.mac">
                <b-row class="align-items-start">
                  <b-col lg="4">
                    <strong>{{ host.name }}</strong>
                    <br />
                    <small class="text-muted">{{ host.ip }} | {{ host.mac }}</small>
                  </b-col>
                  <b-col lg="5">
                    <b-form-input
                      v-model="hostApiKeys[host.mac]"
                      type="password"
                      placeholder="Leave empty to use global key"
                      size="sm"
                    ></b-form-input>
                  </b-col>
                  <b-col lg="3" class="text-left">
                    <b-button
                      variant="success"
                      size="sm"
                      @click="saveHostApiKey(host.mac)"
                      :disabled="savingHostKeys[host.mac]"
                      class="mr-2"
                    >
                      <b-spinner small v-if="savingHostKeys[host.mac]"></b-spinner>
                      Save
                    </b-button>
                    <b-button
                      variant="outline-danger"
                      size="sm"
                      @click="deleteHostApiKey(host.mac)"
                      :disabled="savingHostKeys[host.mac]"
                    >
                      Delete
                    </b-button>
                  </b-col>
                </b-row>
              </b-list-group-item>
            </b-list-group>
          </b-card>

          <b-alert v-else variant="info" class="mt-3">
            No Proxmox hosts found. Tag hosts with "Proxmox" to configure API keys.
          </b-alert>
        </div>
      </b-tab>

      <!-- Manual Hosts -->
      <b-tab title="Manual Hosts" lazy>
        <div class="mt-3">
          <!-- Add New Host -->
          <b-card class="mb-4 text-left text-start">
            <b-card-title>Add Manual Host</b-card-title>
            <b-card-sub-title>
              Add AWS EC2, OPNsense, or other custom hosts for disk space monitoring
            </b-card-sub-title>

            <b-form @submit.prevent="addManualHost">
              <b-form-group label="Host Name:" label-for="host-name">
                <b-form-input
                  id="host-name"
                  v-model="newHost.name"
                  placeholder="e.g., my-ec2-instance"
                  required
                ></b-form-input>
              </b-form-group>

              <b-form-group label="IP Address:" label-for="host-ip">
                <b-form-input
                  id="host-ip"
                  v-model="newHost.ip"
                  placeholder="e.g., 192.168.1.100"
                  required
                ></b-form-input>
              </b-form-group>

              <b-form-group label="Host Type:" label-for="host-type">
                <b-form-select
                  id="host-type"
                  v-model="newHost.type"
                  :options="hostTypes"
                  required
                ></b-form-select>
              </b-form-group>

              <b-form-group label="Description (optional):" label-for="host-description">
                <b-form-textarea
                  id="host-description"
                  v-model="newHost.description"
                  placeholder="Optional notes about this host"
                  rows="3"
                ></b-form-textarea>
              </b-form-group>

              <b-button variant="primary" type="submit" :disabled="addingHost">
                <b-spinner small v-if="addingHost" class="mr-2"></b-spinner>
                Add Host
              </b-button>
            </b-form>
          </b-card>

          <!-- Existing Manual Hosts -->
          <b-card v-if="manualHosts.length > 0" class="text-left text-start">
            <b-card-title>Configured Hosts</b-card-title>
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
    <b-alert v-if="successMessage" variant="success" dismissible @dismissed="successMessage = null" class="mt-3">
      {{ successMessage }}
    </b-alert>
    <b-alert v-if="errorMessage" variant="danger" dismissible @dismissed="errorMessage = null" class="mt-3">
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
      globalApiKey: "",
      globalKeyConfigured: false,
      proxmoxHosts: [],
      hostApiKeys: {},
      savingTag: false,
      savingGlobalKey: false,
      savingHostKeys: {},
      manualHosts: [],
      newHost: {
        name: "",
        ip: "",
        type: "generic",
        description: "",
      },
      hostTypes: [
        { value: "ec2", text: "AWS EC2" },
        { value: "azure", text: "Azure VM" },
        { value: "gcp", text: "Google Cloud" },
        { value: "opnsense", text: "OPNsense" },
        { value: "freebsd", text: "FreeBSD" },
        { value: "generic", text: "Generic Linux/Unix" },
      ],
      addingHost: false,
      successMessage: "",
      errorMessage: "",
    };
  },
  mounted() {
    this.loadSettings();
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
        const settingsResponse = await Helper.apiCall("disk-space", "settings", auth);
        const data = this.parseMaybeJSON(settingsResponse);

        this.proxmoxTag = data.proxmox_tag || "Proxmox";
        this.globalKeyConfigured = data.global_api_key_configured;
        this.proxmoxHosts = data.host_specific_keys || [];

        this.proxmoxHosts.forEach((host) => {
          this.$set(this.hostApiKeys, host.mac, "");
          this.$set(this.savingHostKeys, host.mac, false);
        });

        // Load manual hosts
        const manualResponse = await Helper.apiCall("disk-space", "manual", auth);
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

    async saveGlobalApiKey() {
      if (!this.globalApiKey.trim()) {
        this.errorMessage = "API key cannot be empty";
        return;
      }

      this.savingGlobalKey = true;
      try {
        const auth = this.$auth;
        const formData = new FormData();
        formData.append("api_key", this.globalApiKey);
        await Helper.apiPost(
          "disk-space/settings",
          "",
          "proxmox-api-key",
          auth,
          formData
        );

        this.globalApiKey = "";
        this.globalKeyConfigured = true;
        this.successMessage = "Global API key saved successfully!";
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.savingGlobalKey = false;
      }
    },

    async deleteGlobalApiKey() {
      if (!confirm("Delete global Proxmox API key?")) return;

      this.savingGlobalKey = true;
      try {
        const auth = this.$auth;
        await Helper.apiDelete("disk-space/settings", "proxmox-api-key", auth);

        this.globalKeyConfigured = false;
        this.successMessage = "Global API key deleted successfully!";
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.savingGlobalKey = false;
      }
    },

    async saveHostApiKey(mac) {
      this.$set(this.savingHostKeys, mac, true);
      try {
        const auth = this.$auth;
        const formData = new FormData();
        formData.append("api_key", this.hostApiKeys[mac] || "");
        await Helper.apiPost(
          `disk-space/settings/proxmox-api-key/${mac}`,
          "",
          "",
          auth,
          formData
        );

        this.successMessage = `API key saved for host ${mac}`;
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.$set(this.savingHostKeys, mac, false);
      }
    },

    async deleteHostApiKey(mac) {
      if (!confirm("Delete host-specific API key?")) return;

      this.$set(this.savingHostKeys, mac, true);
      try {
        const auth = this.$auth;
        await Helper.apiDelete(
          "disk-space/settings/proxmox-api-key",
          mac,
          auth
        );

        this.hostApiKeys[mac] = "";
        this.successMessage = "Host API key deleted successfully!";
      } catch (err) {
        this.errorMessage = err.message;
      } finally {
        this.$set(this.savingHostKeys, mac, false);
      }
    },

    async addManualHost() {
      if (!this.newHost.name || !this.newHost.ip || !this.newHost.type) {
        this.errorMessage = "Please fill in all required fields";
        return;
      }

      this.addingHost = true;
      try {
        const auth = this.$auth;
        const formData = new FormData();
        formData.append("name", this.newHost.name);
        formData.append("ip", this.newHost.ip);
        formData.append("type", this.newHost.type);
        formData.append("description", this.newHost.description || "");
        await Helper.apiPost("disk-space/manual", "", "", auth, formData);

        this.successMessage = "Manual host added successfully!";
        this.newHost = {
          name: "",
          ip: "",
          type: "generic",
          description: "",
        };
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
