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
          <b-icon
            :icon="collapsed ? 'chevron-down' : 'chevron-right'"
            class="pt-1 mr-1"
          ></b-icon>
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
      <div v-if="host.nodes && host.nodes.length > 0" class="nodes-grid mb-2">
        <div v-for="node in sortedNodes" :key="node.name" class="node-card">
          <h6 class="text-secondary mb-2">{{ node.name }}</h6>

          <div class="node-panels">
            <div class="node-panel storage-panel">
              <div
                class="panel-title"
                title="Datastores"
                aria-label="Datastores"
              >
                <font-awesome-icon icon="database" />
              </div>
              <div v-if="visibleStorage(node).length > 0" class="storage-grid">
                <div
                  v-for="storage in visibleStorage(node)"
                  :key="storage.name"
                  class="storage-grid-item"
                >
                  <StorageProgressBar :storage="storage" />
                </div>
              </div>
              <b-alert v-else variant="warning" class="small mb-0 py-1 px-2">
                No datastore information available
              </b-alert>
            </div>

            <div class="node-panel vm-panel">
              <div class="panel-title" title="Instances" aria-label="Instances">
                <font-awesome-icon icon="server" />
              </div>

              <div v-if="runningVMs(node).length" class="mb-2">
                <div class="vm-grid">
                  <div
                    v-for="vm in runningVMs(node)"
                    :key="`vm-${node.name}-${vm.id}`"
                    class="vm-grid-item"
                  >
                    <VMContainerProgressBar
                      :item="{ ...vm, node: node.name }"
                      type="vm"
                    />
                  </div>
                </div>
              </div>

              <div v-if="runningContainers(node).length">
                <div
                  class="instance-subtitle text-secondary"
                  title="LXCs"
                  aria-label="LXCs"
                >
                  <font-awesome-icon icon="cube" />
                </div>
                <div class="vm-grid">
                  <div
                    v-for="container in runningContainers(node)"
                    :key="`container-${node.name}-${container.id}`"
                    class="vm-grid-item"
                  >
                    <VMContainerProgressBar
                      :item="{ ...container, node: node.name }"
                      type="container"
                    />
                  </div>
                </div>
              </div>

              <b-alert
                v-if="
                  !runningVMs(node).length && !runningContainers(node).length
                "
                variant="warning"
                class="small mb-0 py-1 px-2"
              >
                No running VM/LXC information available
              </b-alert>
            </div>
          </div>
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
      return containers.filter(
        (container) => this.normalizeStatus(container) === "running"
      );
    },
  },
  computed: {
    sortedNodes() {
      const nodes = (this.host && this.host.nodes) || [];
      return [...nodes].sort((a, b) =>
        ((a && a.name) || "")
          .toString()
          .localeCompare(((b && b.name) || "").toString())
      );
    },
    hasVMs() {
      return (
        this.host.nodes &&
        this.host.nodes.some((node) => node.vms && node.vms.length > 0)
      );
    },
    hasContainers() {
      return (
        this.host.nodes &&
        this.host.nodes.some(
          (node) => node.containers && node.containers.length > 0
        )
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

  .nodes-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.5rem;
    align-items: start;
  }

  .node-card {
    background-color: #f8f9fa;
    padding: 0.5rem;
    border-radius: 4px;
    min-width: 0;
    text-align: center;
  }

  .node-panels {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .node-panel {
    background: #fff;
    border: 1px solid #e8edf3;
    border-radius: 4px;
    padding: 0.4rem;
    flex: 1 1 150px;
    min-width: 140px;
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
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.25rem;
  }

  .storage-grid-item {
    min-width: 0;
  }

  .vm-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 0.25rem;
  }

  .vm-grid-item {
    min-width: 0;
  }
}
</style>
