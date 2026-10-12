<template>
  <div class="p-3">
    <b-row class="mb-3 align-items-center">
      <b-col class="text-left">
        <h4 class="mb-1">{{ title }}</h4>
        <p class="text-muted mb-0">
          <slot name="description" :summary="summary" />
        </p>
      </b-col>
      <b-col cols="12" md="auto" class="mt-2 mt-md-0 text-md-right">
        <slot name="actions" />
        <b-button variant="primary" @click="load()" :disabled="loading">
          <span v-if="!loading">Refresh</span>
          <span v-else>Loading...</span>
        </b-button>
      </b-col>
    </b-row>

    <slot />

    <b-alert v-if="errorMessage" show variant="danger">
      {{ errorMessage }}
    </b-alert>

    <b-alert v-if="clusterErrors.length" show variant="warning">
      <div class="font-weight-bold mb-1">
        Some Proxmox clusters could not be queried:
      </div>
      <ul class="mb-0 text-left pl-3">
        <li v-for="err in clusterErrors" :key="err.cluster_name">
          {{ err.cluster_name }}: {{ err.error }}
        </li>
      </ul>
    </b-alert>

    <b-row class="mb-3">
      <b-col
        v-for="card in summaryCards"
        :key="card.status"
        cols="6"
        md="3"
        lg
        class="mb-2"
      >
        <b-card
          :class="['summary-card', `border-${card.variant}`]"
          role="button"
          @click="filter = card.status"
        >
          <div class="text-muted small">{{ card.label }}</div>
          <div :class="['summary-value', `text-${card.variant}`]">
            {{ summary[card.count] || 0 }}
          </div>
        </b-card>
      </b-col>
    </b-row>

    <b-form-radio-group
      v-model="filter"
      :options="filterOptions"
      buttons
      size="sm"
      button-variant="outline-secondary"
      class="mb-2"
    />

    <b-table
      :items="filteredGuests"
      :fields="fields"
      striped
      hover
      small
      responsive
      show-empty
      :busy="loading"
      :empty-text="emptyText"
    >
      <template #table-busy>
        <div class="text-center text-muted my-2">Loading Proxmox guests...</div>
      </template>

      <template #cell(name)="row">
        <div class="text-left">
          <div class="font-weight-bold">{{ row.item.name || row.item.id }}</div>
          <div class="small text-muted">
            {{ row.item.type.toUpperCase() }} {{ row.item.id }}
          </div>
        </div>
      </template>

      <template #cell(node)="row">
        <div class="text-left">
          <div>{{ row.item.node }}</div>
          <div class="small text-muted">{{ row.item.cluster_name }}</div>
        </div>
      </template>

      <template #cell(check_status)="row">
        <b-badge :variant="statusInfo(row.item.check_status).variant">
          {{ statusInfo(row.item.check_status).label }}
        </b-badge>
        <slot name="status-detail" :item="row.item" :status-info="statusInfo" />
      </template>

      <template v-for="slot in cellSlots()" #[slot]="row">
        <slot :name="slot" v-bind="row" />
      </template>
    </b-table>
  </div>
</template>

<script>
import Helper from "@/helper";

// Shared layout for the per-guest Proxmox checks: loads `route`, then shows
// summary cards, a status filter, and one table row per VM/LXC.
export default {
  name: "ProxmoxGuestCheck",
  props: {
    title: { type: String, required: true },
    route: { type: String, required: true },
    statuses: { type: Object, required: true },
    issueStatuses: { type: Array, required: true },
    fields: { type: Array, required: true },
    emptyText: { type: String, default: "No guests to show." },
  },
  data() {
    return {
      loading: false,
      errorMessage: "",
      clusterErrors: [],
      guests: [],
      summary: {},
      filter: "issues",
    };
  },
  computed: {
    filterOptions() {
      return [
        { text: "Issues", value: "issues" },
        { text: "All", value: "all" },
        ...Object.keys(this.statuses).map((value) => ({
          text: this.statuses[value].label,
          value,
        })),
      ];
    },
    summaryCards() {
      return [
        {
          status: "all",
          label: "Guests",
          count: "guest_count",
          variant: "dark",
        },
        ...Object.keys(this.statuses).map((status) => ({
          status,
          label: this.statuses[status].label,
          count: `${status}_count`,
          variant: this.statuses[status].variant,
        })),
      ];
    },
    filteredGuests() {
      if (this.filter === "all") return this.guests;
      if (this.filter === "issues") {
        return this.guests.filter((g) =>
          this.issueStatuses.includes(g.check_status)
        );
      }
      return this.guests.filter((g) => g.check_status === this.filter);
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    statusInfo(status) {
      return this.statuses[status] || { label: status, variant: "secondary" };
    },
    cellSlots() {
      return Object.keys(this.$scopedSlots).filter((s) =>
        s.startsWith("cell(")
      );
    },
    // Reload the check, optionally after a change (e.g. a settings save) that
    // shares the same error banner.
    async load(before) {
      this.loading = true;
      this.errorMessage = "";
      try {
        if (before) await before();
        const response = await Helper.apiCall(
          "disk-space/proxmox",
          this.route,
          this.$auth
        );
        const payload =
          typeof response === "string" ? JSON.parse(response) : response;
        this.guests = payload.guests || [];
        this.summary = payload.summary || {};
        this.clusterErrors = payload.errors || [];
        this.$emit("loaded", payload);
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      } finally {
        this.loading = false;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.summary-card {
  min-height: 96px;
  cursor: pointer;
}

.summary-value {
  font-size: 1.75rem;
  font-weight: 600;
}
</style>
