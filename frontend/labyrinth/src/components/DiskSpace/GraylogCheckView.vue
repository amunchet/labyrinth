<template>
  <div class="p-3">
    <b-row class="mb-3 align-items-center">
      <b-col class="text-left">
        <h4 class="mb-1">Graylog Check</h4>
        <p class="text-muted mb-0">
          Every Proxmox VM and LXC should report a passing
          <code>{{ settings.metric_name }}</code> Telegraf check (rsyslog
          installed, running, and forwarding to Graylog) within the last
          {{ settings.stale_hours }} hours. Guests can be deferred.
        </p>
      </b-col>
      <b-col cols="12" md="auto" class="mt-2 mt-md-0 text-md-right">
        <b-button
          variant="outline-secondary"
          class="mr-2"
          v-b-toggle.graylog-settings
        >
          Settings
        </b-button>
        <b-button variant="primary" @click="loadGuests" :disabled="loading">
          <span v-if="!loading">Refresh</span>
          <span v-else>Loading...</span>
        </b-button>
      </b-col>
    </b-row>

    <b-collapse id="graylog-settings" class="mb-3">
      <b-card class="text-left">
        <b-form @submit.prevent="saveSettings">
          <b-form-row>
            <b-col md="4">
              <b-form-group
                label="Check metric name"
                label-for="graylog-metric-name"
                description="Telegraf measurement that carries the result (ok=1 passes)."
              >
                <b-form-input
                  id="graylog-metric-name"
                  v-model="settingsForm.metric_name"
                  placeholder="check_graylog"
                />
              </b-form-group>
            </b-col>
            <b-col md="4">
              <b-form-group
                label="Stale after (hours)"
                label-for="graylog-stale-hours"
              >
                <b-form-input
                  id="graylog-stale-hours"
                  v-model.number="settingsForm.stale_hours"
                  type="number"
                  min="1"
                />
              </b-form-group>
            </b-col>
          </b-form-row>
          <b-button type="submit" variant="primary" size="sm">
            Save settings
          </b-button>
        </b-form>
        <hr />
        <div class="small">
          <strong>Setup:</strong> copy
          <code>backend/samples/telegraf/check_graylog.sh</code> to each guest
          as <code>/usr/local/bin/check_graylog.sh</code> (the
          <code>install_check_graylog.yml</code> sample playbook does this),
          then add to the host's Telegraf config:
          <pre class="mt-2 mb-0">
[[inputs.exec]]
  commands = ["/usr/local/bin/check_graylog.sh"]
  timeout = "15s"
  data_format = "influx"</pre
          >
          Append <code>graylog.lan:1514</code> to the command to require a
          specific target; otherwise any rsyslog forwarding target counts.
        </div>
      </b-card>
    </b-collapse>

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
      empty-text="No guests to show."
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

      <template #cell(result)="row">
        <div class="text-left small">
          <div v-if="row.item.graylog_last_seen">
            {{ row.item.graylog_fields.status || "—" }}
            <span v-if="row.item.graylog_target" class="text-muted">
              → {{ row.item.graylog_target }}
            </span>
          </div>
          <div class="text-muted">
            {{ row.item.graylog_last_seen || "No check reported" }}
          </div>
        </div>
      </template>

      <template #cell(check_status)="row">
        <b-badge :variant="statusInfo(row.item.check_status).variant">
          {{ statusInfo(row.item.check_status).label }}
        </b-badge>
        <div v-if="row.item.deferral" class="small text-muted mt-1">
          {{
            row.item.deferral.until
              ? `until ${row.item.deferral.until}`
              : "permanently"
          }}
          <span v-if="row.item.deferral.reason">
            — {{ row.item.deferral.reason }}</span
          >
          <div v-if="row.item.check_status === 'deferred'">
            (actual: {{ statusInfo(row.item.result_status).label }})
          </div>
        </div>
      </template>

      <template #cell(actions)="row">
        <b-button
          v-if="row.item.deferral"
          size="sm"
          variant="outline-secondary"
          @click="removeDeferral(row.item)"
        >
          Undefer
        </b-button>
        <b-button
          v-else-if="!['ok', 'stopped'].includes(row.item.check_status)"
          size="sm"
          variant="outline-primary"
          @click="openDefer(row.item)"
        >
          Defer
        </b-button>
      </template>
    </b-table>

    <b-modal
      id="graylog-defer-modal"
      v-model="deferModal.show"
      :title="`Defer Graylog check for ${
        deferModal.guest && deferModal.guest.name
      }`"
      ok-title="Defer"
      @ok="saveDeferral"
    >
      <b-form-group label="Defer for" label-for="graylog-defer-days">
        <b-form-select
          id="graylog-defer-days"
          v-model="deferModal.days"
          :options="deferOptions"
        />
      </b-form-group>
      <b-form-group label="Reason (optional)" label-for="graylog-defer-reason">
        <b-form-input
          id="graylog-defer-reason"
          v-model="deferModal.reason"
          placeholder="e.g. appliance, no rsyslog available"
        />
      </b-form-group>
    </b-modal>
  </div>
</template>

<script>
import Helper from "@/helper";

const STATUSES = {
  ok: { label: "OK", variant: "success" },
  failing: { label: "Failing", variant: "danger" },
  stale: { label: "Stale", variant: "warning" },
  not_deployed: { label: "Check not deployed", variant: "warning" },
  unmatched: { label: "No Labyrinth host", variant: "warning" },
  deferred: { label: "Deferred", variant: "info" },
  stopped: { label: "Stopped", variant: "secondary" },
};

const ISSUE_STATUSES = ["failing", "stale", "not_deployed", "unmatched"];

export default {
  name: "GraylogCheckView",
  data() {
    return {
      loading: false,
      errorMessage: "",
      clusterErrors: [],
      guests: [],
      deferrals: [],
      summary: {},
      settings: { metric_name: "check_graylog", stale_hours: 24 },
      settingsForm: { metric_name: "check_graylog", stale_hours: 24 },
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
        { key: "result", label: "Graylog Check Result" },
        { key: "check_status", label: "Status", sortable: true },
        { key: "actions", label: "" },
      ],
      deferOptions: [
        { text: "1 day", value: 1 },
        { text: "1 week", value: 7 },
        { text: "30 days", value: 30 },
        { text: "90 days", value: 90 },
        { text: "Permanently (exempt)", value: null },
      ],
      deferModal: { show: false, guest: null, days: 7, reason: "" },
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
        return this.guests.filter((g) =>
          ISSUE_STATUSES.includes(g.check_status)
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
          "graylog-check",
          this.$auth
        );
        const payload =
          typeof response === "string" ? JSON.parse(response) : response;
        this.guests = payload.guests || [];
        this.summary = payload.summary || {};
        this.clusterErrors = payload.errors || [];
        this.deferrals = payload.deferrals || [];
        this.settings = payload.settings || this.settings;
        this.settingsForm = { ...this.settings };
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      } finally {
        this.loading = false;
      }
    },
    async saveSetting(name, value) {
      const formData = new FormData();
      formData.append("name", name);
      formData.append("value", JSON.stringify(value));
      await Helper.apiPost("settings", "", "", this.$auth, formData);
    },
    async saveSettings() {
      try {
        await this.saveSetting("proxmox_graylog_check", {
          metric_name: this.settingsForm.metric_name.trim() || "check_graylog",
          stale_hours: Number(this.settingsForm.stale_hours) || 24,
        });
        await this.loadGuests();
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      }
    },
    openDefer(guest) {
      this.deferModal = { show: true, guest, days: 7, reason: "" };
    },
    // Store deferrals without the given guest's entry (and any expired ones)
    async persistDeferrals(guest, extra) {
      const today = new Date().toISOString().slice(0, 10);
      const kept = this.deferrals.filter(
        (d) =>
          !(
            String(d.cluster_name) === String(guest.cluster_name) &&
            String(d.id) === String(guest.id)
          ) &&
          (!d.until || d.until >= today)
      );
      try {
        await this.saveSetting(
          "proxmox_graylog_deferrals",
          extra ? [...kept, extra] : kept
        );
        await this.loadGuests();
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      }
    },
    async saveDeferral() {
      const { guest, days, reason } = this.deferModal;
      let until = null;
      if (days) {
        const date = new Date();
        date.setDate(date.getDate() + days);
        until = date.toISOString().slice(0, 10);
      }
      await this.persistDeferrals(guest, {
        cluster_name: guest.cluster_name,
        id: guest.id,
        name: guest.name,
        until,
        reason: reason.trim(),
      });
    },
    async removeDeferral(guest) {
      await this.persistDeferrals(guest, null);
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
