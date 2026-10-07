<template>
  <div class="p-3">
    <b-row class="mb-3 align-items-center">
      <b-col class="text-left">
        <h4 class="mb-1">Telegraf Check</h4>
        <p class="text-muted mb-0">
          Every Proxmox VM and LXC should map to a monitored Labyrinth host that
          is reporting Telegraf metrics (within the last
          {{ summary.stale_minutes }} minutes).
        </p>
      </b-col>
      <b-col cols="12" md="auto" class="mt-2 mt-md-0 text-md-right">
        <b-button variant="primary" @click="loadGuests" :disabled="loading">
          <span v-if="!loading">Refresh</span>
          <span v-else>Loading...</span>
        </b-button>
      </b-col>
    </b-row>

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
        md="2"
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
      empty-text="No guests to show. Add a Proxmox cluster in Settings to begin."
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

      <template #cell(labyrinth_host)="row">
        <div class="text-left small">
          <div
            v-for="match in row.item.labyrinth_matches"
            :key="`${row.item.cluster_name}-${row.item.id}-${match.ip}`"
          >
            {{ match.host || match.ip }}
            <span class="text-muted">({{ match.ip }})</span>
          </div>
          <span v-if="!row.item.labyrinth_matches.length" class="text-muted"
            >—</span
          >
        </div>
      </template>

      <template #cell(telegraf)="row">
        <div class="small">
          {{ row.item.telegraf_last_seen || "Never" }}
        </div>
      </template>

      <template #cell(check_status)="row">
        <b-badge :variant="statusInfo(row.item.check_status).variant">
          {{ statusInfo(row.item.check_status).label }}
        </b-badge>
      </template>
    </b-table>
  </div>
</template>

<script>
import Helper from "@/helper";

const STATUSES = {
  ok: { label: "OK", variant: "success" },
  unmatched: { label: "No Labyrinth host", variant: "danger" },
  not_monitored: { label: "Not monitored", variant: "warning" },
  no_telegraf: { label: "No Telegraf", variant: "danger" },
  stopped: { label: "Stopped", variant: "secondary" },
};

export default {
  name: "TelegrafCheckView",
  data() {
    return {
      loading: false,
      errorMessage: "",
      clusterErrors: [],
      guests: [],
      summary: { stale_minutes: 15 },
      filter: "issues",
      filterOptions: [
        { text: "Issues", value: "issues" },
        { text: "All", value: "all" },
        ...Object.keys(STATUSES).map((value) => ({
          text: STATUSES[value].label,
          value,
        })),
      ],
      fields: [
        { key: "name", label: "Guest", sortable: true },
        { key: "node", label: "Node", sortable: true },
        { key: "labyrinth_host", label: "Labyrinth Host" },
        { key: "telegraf", label: "Last Telegraf Metric" },
        { key: "check_status", label: "Status", sortable: true },
      ],
    };
  },
  computed: {
    summaryCards() {
      return [
        {
          status: "all",
          label: "Guests",
          count: "guest_count",
          variant: "dark",
        },
        ...Object.keys(STATUSES).map((status) => ({
          status,
          label: STATUSES[status].label,
          count: `${status}_count`,
          variant: STATUSES[status].variant,
        })),
      ];
    },
    filteredGuests() {
      if (this.filter === "all") return this.guests;
      if (this.filter === "issues") {
        return this.guests.filter(
          (g) => !["ok", "stopped"].includes(g.check_status)
        );
      }
      return this.guests.filter((g) => g.check_status === this.filter);
    },
  },
  mounted() {
    this.loadGuests();
  },
  methods: {
    statusInfo(status) {
      return STATUSES[status] || { label: status, variant: "secondary" };
    },
    async loadGuests() {
      this.loading = true;
      this.errorMessage = "";
      try {
        const response = await Helper.apiCall(
          "disk-space/proxmox",
          "telegraf-check",
          this.$auth
        );
        const payload =
          typeof response === "string" ? JSON.parse(response) : response;
        this.guests = payload.guests || [];
        this.summary = payload.summary || this.summary;
        this.clusterErrors = payload.errors || [];
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
