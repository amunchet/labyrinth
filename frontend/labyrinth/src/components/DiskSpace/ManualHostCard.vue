<template>
  <div class="manual-host-card">
    <!-- Host Header -->
    <b-row class="mb-3 pb-3 border-bottom">
      <b-col lg="8">
        <h5>{{ host.name }}</h5>
        <small class="text-muted">
          {{ host.ip }} | Type: <b-badge>{{ host.type }}</b-badge>
        </small>
      </b-col>
      <b-col lg="4" class="text-right">
        <b-button
          variant="danger"
          size="sm"
          @click="confirmDelete"
        >
          <b-icon icon="trash"></b-icon>
          Delete
        </b-button>
      </b-col>
    </b-row>

    <!-- Info Message -->
    <b-alert variant="info" class="small">
      <strong>Note:</strong> Disk space data retrieval for this host type requires
      agent software or custom configuration. See documentation for setup instructions.
    </b-alert>

    <!-- Additional Fields -->
    <b-row class="mt-3">
      <b-col lg="6">
        <small class="text-muted">
          <strong>Added:</strong> {{ formatDate(host.added) }}
        </small>
      </b-col>
      <b-col lg="6">
        <small class="text-muted">
          <strong>Last Updated:</strong> {{ formatDate(host.updated || host.created) }}
        </small>
      </b-col>
    </b-row>
  </div>
</template>

<script>
export default {
  name: "ManualHostCard",
  props: {
    host: {
      type: Object,
      required: true,
    },
  },
  methods: {
    confirmDelete() {
      if (confirm(`Are you sure you want to delete ${this.host.name}?`)) {
        this.$emit("delete", this.host.id);
      }
    },
    formatDate(dateString) {
      if (!dateString) return "N/A";
      const date = new Date(dateString);
      return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    },
  },
};
</script>

<style lang="scss" scoped>
.manual-host-card {
  h5 {
    margin-bottom: 0.5rem;
  }
}
</style>
