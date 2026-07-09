<template>
  <div class="p-3">
    <b-row class="mb-3 align-items-center">
      <b-col class="text-left">
        <h4 class="mb-1">EC2 Inventory</h4>
        <p class="text-muted mb-0">
          Review EC2 instances and whether each one already maps to a monitored Labyrinth host.
        </p>
      </b-col>
      <b-col cols="12" md="auto" class="mt-2 mt-md-0 text-md-right">
        <b-button variant="primary" @click="loadInstances" :disabled="loading">
          <span v-if="!loading">Refresh</span>
          <span v-else>Loading...</span>
        </b-button>
      </b-col>
    </b-row>

    <b-alert v-if="errorMessage" show variant="danger">
      {{ errorMessage }}
    </b-alert>

    <b-alert v-if="accountErrors.length" show variant="warning">
      <div class="font-weight-bold mb-1">Some AWS accounts could not be queried:</div>
      <ul class="mb-0 text-left pl-3">
        <li v-for="err in accountErrors" :key="`${err.account_name}-${err.region}`">
          {{ err.account_name }} ({{ err.region }}): {{ err.error }}
        </li>
      </ul>
    </b-alert>

    <b-row class="mb-3">
      <b-col cols="12" md="3" class="mb-2 mb-md-0">
        <b-card class="summary-card">
          <div class="text-muted small">AWS Accounts</div>
          <div class="summary-value">{{ summary.account_count }}</div>
        </b-card>
      </b-col>
      <b-col cols="12" md="3" class="mb-2 mb-md-0">
        <b-card class="summary-card">
          <div class="text-muted small">Instances</div>
          <div class="summary-value">{{ summary.instance_count }}</div>
        </b-card>
      </b-col>
      <b-col cols="12" md="3" class="mb-2 mb-md-0">
        <b-card class="summary-card border-success">
          <div class="text-muted small">Matched</div>
          <div class="summary-value text-success">{{ summary.matched_instance_count }}</div>
        </b-card>
      </b-col>
      <b-col cols="12" md="3">
        <b-card class="summary-card border-warning">
          <div class="text-muted small">Needs Mapping</div>
          <div class="summary-value text-warning">{{ summary.unmatched_instance_count }}</div>
        </b-card>
      </b-col>
    </b-row>

    <b-table
      :items="instances"
      :fields="fields"
      striped
      hover
      small
      responsive
      :busy="loading"
      empty-text="No EC2 instances found. Add an AWS account in Settings to begin."
    >
      <template #table-busy>
        <div class="text-center text-muted my-2">Loading EC2 inventory...</div>
      </template>

      <template #cell(name)="row">
        <div class="text-left">
          <div class="font-weight-bold">{{ row.item.name || row.item.instance_id }}</div>
          <div class="small text-muted">{{ row.item.instance_id }}</div>
        </div>
      </template>

      <template #cell(account)="row">
        <div class="text-left">
          <div>{{ row.item.account_name }}</div>
          <div class="small text-muted">{{ row.item.region }}</div>
        </div>
      </template>

      <template #cell(state)="row">
        <b-badge :variant="stateVariant(row.item.state)">
          {{ row.item.state || "unknown" }}
        </b-badge>
      </template>

      <template #cell(network)="row">
        <div class="text-left small">
          <div><strong>Private:</strong> {{ row.item.private_ip || "—" }}</div>
          <div><strong>Public:</strong> {{ row.item.public_ip || "—" }}</div>
        </div>
      </template>

      <template #cell(match_status)="row">
        <div class="text-left">
          <b-badge :variant="row.item.matched ? 'success' : 'warning'">
            {{ row.item.matched ? "Matched" : "Needs mapping" }}
          </b-badge>
          <div v-if="row.item.labyrinth_matches.length" class="small mt-1">
            <div
              v-for="match in row.item.labyrinth_matches"
              :key="`${row.item.instance_id}-${match.ip}-${match.host}`"
            >
              {{ match.host || match.ip }}
              <span class="text-muted">
                ({{ match.match_reasons.join(", ") }})
              </span>
            </div>
          </div>
        </div>
      </template>

      <template #cell(monitoring)="row">
        <div>
          <b-badge :variant="row.item.monitoring_enabled ? 'success' : 'secondary'">
            {{ row.item.monitoring_enabled ? "Monitored" : "Not monitored" }}
          </b-badge>
          <div v-if="row.item.labyrinth_matches.length" class="small text-muted mt-1">
            {{ monitoringDetails(row.item) }}
          </div>
        </div>
      </template>

      <template #cell(tags)="row">
        <div class="text-left small tags-cell">
          <span
            v-for="tag in formatTags(row.item.tags)"
            :key="`${row.item.instance_id}-${tag.key}`"
            class="tag-pill"
          >
            {{ tag.key }}={{ tag.value }}
          </span>
          <span v-if="!formatTags(row.item.tags).length" class="text-muted">—</span>
        </div>
      </template>
    </b-table>
  </div>
</template>

<script>
import Helper from "@/helper";

export default {
  name: "AwsInstancesView",
  data() {
    return {
      loading: false,
      errorMessage: "",
      accountErrors: [],
      instances: [],
      summary: {
        account_count: 0,
        instance_count: 0,
        matched_instance_count: 0,
        unmatched_instance_count: 0,
      },
      fields: [
        { key: "name", label: "Instance" },
        { key: "account", label: "Account" },
        { key: "state", label: "State" },
        { key: "network", label: "Network" },
        { key: "match_status", label: "Labyrinth Match" },
        { key: "monitoring", label: "Monitoring" },
        { key: "tags", label: "Tags" },
      ],
    };
  },
  mounted() {
    this.loadInstances();
  },
  methods: {
    parseMaybeJSON(payload) {
      return typeof payload === "string" ? JSON.parse(payload) : payload;
    },
    formatTags(tags) {
      return Object.keys(tags || {})
        .sort()
        .map((key) => ({ key, value: tags[key] }));
    },
    stateVariant(state) {
      const normalized = (state || "").toLowerCase();
      if (normalized === "running") return "success";
      if (normalized === "stopped") return "secondary";
      if (normalized === "terminated") return "danger";
      return "info";
    },
    monitoringDetails(instance) {
      const serviceCount = instance.labyrinth_matches.reduce(
        (total, match) => total + (match.service_count || 0),
        0
      );
      return `${instance.labyrinth_matches.length} host match(es), ${serviceCount} service mapping(s)`;
    },
    async loadInstances() {
      this.loading = true;
      this.errorMessage = "";
      try {
        const auth = this.$auth;
        const response = await Helper.apiCall("aws", "ec2-instances", auth);
        const payload = this.parseMaybeJSON(response);
        this.instances = payload.instances || [];
        this.summary = payload.summary || this.summary;
        this.accountErrors = payload.errors || [];
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
}

.summary-value {
  font-size: 1.75rem;
  font-weight: 600;
}

.tags-cell {
  max-width: 320px;
}

.tag-pill {
  display: inline-block;
  margin: 0 0.35rem 0.35rem 0;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  background: #eef2f7;
}
</style>
