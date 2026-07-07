<template>
  <div class="proxmox-host-card">
    <!-- Host Header -->
    <b-row class="mb-1 pb-1 border-bottom align-items-center">
      <b-col lg="6">
        <b-button
          variant="link"
          @click="collapsed = !collapsed"
          class="text-decoration-none p-0 font-weight-bold"
        >
          <b-icon :icon="collapsed ? 'chevron-down' : 'chevron-right'" class="pt-1 mr-1"></b-icon>
          {{ host.cluster_name || host.host }}
        </b-button>
      </b-col>
      <b-col lg="6" class="text-right">
        <b-badge v-if="host.error" variant="danger">
          Error: {{ host.error }}
        </b-badge>
        <b-badge v-else variant="success">Connected</b-badge>
      </b-col>
    </b-row>

    <!-- Expandable Content -->
    <b-collapse v-model="collapsed" class="mt-2">
      <div v-if="host.nodes && host.nodes.length > 0" class="mb-2">
        <div v-for="node in host.nodes" :key="node.name" class="node-storage mb-3">
          <h6 class="text-secondary mb-2">{{ node.name }}</h6>

          <b-row class="node-layout">
            <b-col cols="12" lg="6" class="mb-2 mb-lg-0">
              <div class="node-panel storage-panel">
                <div class="panel-title">Datastores</div>
                <div v-if="visibleStorage(node).length > 0" class="storage-grid">
                  <div
                    v-for="storage in visibleStorage(node)"
                    :key="storage.name"
                    class="storage-grid-item"
                  >
                    <div class="storage-card">
                      <StorageProgressBar :storage="storage" />
                    </div>
                  </div>
                </div>
                <b-alert v-else variant="warning" class="small mb-0 py-1 px-2">
                  No datastore information available
                </b-alert>
              </div>
            </b-col>

            <b-col cols="12" lg="6">
              <div class="node-panel vm-panel">
                <div class="panel-title">Instances</div>

                <div v-if="runningVMs(node).length" class="mb-2">
                  <div class="instance-subtitle">Virtual Machines</div>
                  <div class="vm-grid">
                    <div
                      v-for="vm in runningVMs(node)"
                      :key="`vm-${node.name}-${vm.id}`"
                      class="vm-grid-item"
                    >
                      <div class="vm-card">
                        <VMContainerProgressBar :item="{ ...vm, node: node.name }" type="vm" />
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="runningContainers(node).length">
                  <div class="instance-subtitle">LXC Containers</div>
                  <div class="vm-grid">
                    <div
                      v-for="container in runningContainers(node)"
                      :key="`container-${node.name}-${container.id}`"
                      class="vm-grid-item"
                    >
                      <div class="vm-card">
                        <VMContainerProgressBar
                          :item="{ ...container, node: node.name }"
                          type="container"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <b-alert
                  v-if="!runningVMs(node).length && !runningContainers(node).length"
                  variant="warning"
                  class="small mb-0 py-1 px-2"
                >
                  No running VM/LXC information available
                </b-alert>
              </div>
            </b-col>
          </b-row>
        </div>
      </div>
    </b-collapse>
  </div>
</template>

<script>
import StorageProgressBar from "./StorageProgressBar";
import VMContainerProgressBar from "./VMContainerProgressBar";

export default {
  name: "ProxmoxHostCard",
  components: {
    StorageProgressBar,
    VMContainerProgressBar,
  },
  props: {
    host: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      collapsed: true,
    };
  },
  methods: {
    toNumber(value) {
      const n = Number(value);
      return Number.isFinite(n) ? n : 0;
    },
    visibleStorage(node) {
      const storage = (node && node.storage) || [];
      return storage.filter((item) => {
        const total = this.toNumber(item.total);
        const used = this.toNumber(item.used);
        return !(total === 0 && used === 0);
      });
    },
    normalizeStatus(item) {
      return ((item && item.status) || "").toString().toLowerCase();
    },
    runningVMs(node) {
      const vms = (node && node.vms) || [];
      return vms.filter((vm) => this.normalizeStatus(vm) === "running");
    },
    runningContainers(node) {
      const containers = (node && node.containers) || [];
      return containers.filter((container) => this.normalizeStatus(container) === "running");
    },
  },
  computed: {
    hasVMs() {
      return (
        this.host.nodes &&
        this.host.nodes.some((node) => node.vms && node.vms.length > 0)
      );
    },
    hasContainers() {
      return (
        this.host.nodes &&
        this.host.nodes.some((node) => node.containers && node.containers.length > 0)
      );
    },
    getAllVMs() {
      const vms = [];
      if (this.host.nodes) {
        this.host.nodes.forEach((node) => {
          if (node.vms) {
            node.vms.forEach((vm) => {
              vms.push({ ...vm, node: node.name });
            });
          }
        });
      }
      return vms;
    },
    getAllContainers() {
      const containers = [];
      if (this.host.nodes) {
        this.host.nodes.forEach((node) => {
          if (node.containers) {
            node.containers.forEach((container) => {
              containers.push({ ...container, node: node.name });
            });
          }
        });
      }
      return containers;
    },
  },
};
</script>

<style lang="scss" scoped>
.proxmox-host-card {
  h6 {
    font-weight: 600;
    margin-bottom: 1rem;
  }

  .node-storage {
    background-color: #f8f9fa;
    padding: 0.5rem;
    border-radius: 4px;
  }

  .node-panel {
    background: #fff;
    border: 1px solid #e8edf3;
    border-radius: 4px;
    padding: 0.4rem;
    height: 100%;
  }

  .storage-panel {
    border-left: 3px solid #17a2b8;
  }

  .vm-panel {
    border-left: 3px solid #6f42c1;
  }

  .panel-title {
    font-size: 0.82rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }

  .instance-subtitle {
    font-size: 0.75rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
  }

  .storage-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(145px, 1fr));
    gap: 0.35rem;
  }

  .storage-grid-item {
    min-width: 0;
  }

  .storage-card {
    background: #fff;
    border: 1px solid #eceff3;
    border-radius: 4px;
    padding: 0.25rem 0.35rem;
  }

  .vm-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 0.35rem;
  }

  .vm-grid-item {
    min-width: 0;
  }

  .vm-card {
    background: #fff;
    border: 1px solid #eceff3;
    border-radius: 4px;
    padding: 0.25rem 0.35rem;
  }
}
</style>
