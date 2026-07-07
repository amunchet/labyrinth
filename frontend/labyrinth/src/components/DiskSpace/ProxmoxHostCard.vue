<template>
  <div class="proxmox-host-card">
    <!-- Host Header -->
    <b-row class="mb-3 pb-3 border-bottom">
      <b-col lg="6">
        <h5>
          <b-button
            variant="link"
            @click="collapsed = !collapsed"
            class="text-decoration-none"
          >
            <b-icon :icon="collapsed ? 'chevron-right' : 'chevron-down'"></b-icon>
            {{ host.host }}
          </b-button>
        </h5>
        <small class="text-muted">{{ host.ip }}</small>
      </b-col>
      <b-col lg="6" class="text-right">
        <b-badge
          v-if="host.error"
          variant="danger"
        >
          Error: {{ host.error }}
        </b-badge>
        <b-badge v-else variant="success">Connected</b-badge>
      </b-col>
    </b-row>

    <!-- Expandable Content -->
    <b-collapse v-model="collapsed" class="mt-3">
      <!-- Storage Information -->
      <div v-if="host.nodes && host.nodes.length > 0" class="mb-4">
        <h6 class="mb-3">Storage Information</h6>
        <div v-for="node in host.nodes" :key="node.name" class="node-storage mb-3">
          <h6 class="text-secondary">
          {{ node.name }}</h6>
          <b-row v-if="node.storage && node.storage.length > 0" class="storage-grid">
            <b-col
              v-for="storage in node.storage"
              :key="storage.name"
              cols="12"
              md="6"
              xl="4"
              class="mb-2"
            >
              <b-card class="storage-card h-100">
                <StorageProgressBar :storage="storage" />
              </b-card>
            </b-col>
          </b-row>
          <b-alert v-else variant="warning" class="small mb-0">
            No storage information available
          </b-alert>
        </div>
      </div>

      <!-- VMs Section -->
      <div v-if="hasVMs" class="mb-4">
        <h6 class="mb-3">Virtual Machines</h6>
        <b-list-group>
          <b-list-group-item
            v-for="vm in getAllVMs"
            :key="`vm-${vm.node}-${vm.id}`"
          >
            <VMContainerProgressBar :item="vm" type="vm" />
          </b-list-group-item>
        </b-list-group>
      </div>

      <!-- Containers Section -->
      <div v-if="hasContainers">
        <h6 class="mb-3">LXC Containers</h6>
        <b-list-group>
          <b-list-group-item
            v-for="container in getAllContainers"
            :key="`container-${container.node}-${container.id}`"
          >
            <VMContainerProgressBar :item="container" type="container" />
          </b-list-group-item>
        </b-list-group>
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
    padding: 1rem;
    border-radius: 4px;
  }

  .storage-grid {
    margin-left: -0.35rem;
    margin-right: -0.35rem;
  }

  .storage-grid > [class*="col-"] {
    padding-left: 0.35rem;
    padding-right: 0.35rem;
  }

  .storage-card {
    border: 1px solid #eceff3;
  }
}
</style>
