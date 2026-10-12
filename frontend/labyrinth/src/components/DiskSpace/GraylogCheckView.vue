<template>
  <ProxmoxGuestCheck
    ref="check"
    title="Graylog Check"
    route="graylog-check"
    :statuses="statuses"
    :issue-statuses="issueStatuses"
    :fields="fields"
    @loaded="onLoaded"
  >
    <template #description>
      Every Proxmox VM and LXC should report a passing
      <code>{{ settings.metric_name }}</code> Telegraf check (rsyslog installed,
      running, and forwarding to Graylog) within the last
      {{ settings.stale_hours }} hours. Guests can be deferred.
    </template>

    <template #actions>
      <b-button
        variant="outline-secondary"
        class="mr-2"
        v-b-toggle.graylog-settings
      >
        Settings
      </b-button>
    </template>

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

    <template #status-detail="{ item, statusInfo }">
      <div v-if="item.deferral" class="small text-muted mt-1">
        {{
          item.deferral.until ? `until ${item.deferral.until}` : "permanently"
        }}
        <span v-if="item.deferral.reason"> — {{ item.deferral.reason }}</span>
        <div v-if="item.check_status === 'deferred'">
          (actual: {{ statusInfo(item.result_status).label }})
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
  </ProxmoxGuestCheck>
</template>

<script>
import Helper from "@/helper";
import ProxmoxGuestCheck from "@/components/DiskSpace/ProxmoxGuestCheck";

export default {
  name: "GraylogCheckView",
  components: { ProxmoxGuestCheck },
  data() {
    return {
      statuses: {
        ok: { label: "OK", variant: "success" },
        failing: { label: "Failing", variant: "danger" },
        stale: { label: "Stale", variant: "warning" },
        not_deployed: { label: "Check not deployed", variant: "warning" },
        unmatched: { label: "No Labyrinth host", variant: "warning" },
        deferred: { label: "Deferred", variant: "info" },
        stopped: { label: "Stopped", variant: "secondary" },
      },
      issueStatuses: ["failing", "stale", "not_deployed", "unmatched"],
      fields: [
        { key: "name", label: "Guest", sortable: true },
        { key: "node", label: "Node", sortable: true },
        { key: "result", label: "Graylog Check Result" },
        { key: "check_status", label: "Status", sortable: true },
        { key: "actions", label: "" },
      ],
      deferrals: [],
      settings: { metric_name: "check_graylog", stale_hours: 24 },
      settingsForm: { metric_name: "check_graylog", stale_hours: 24 },
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
  methods: {
    onLoaded(payload) {
      this.deferrals = payload.deferrals || [];
      this.settings = payload.settings || this.settings;
      this.settingsForm = { ...this.settings };
    },
    // Save a setting, then reload the check (errors land in its banner)
    saveSetting(name, value) {
      const formData = new FormData();
      formData.append("name", name);
      formData.append("value", JSON.stringify(value));
      return this.$refs.check.load(() =>
        Helper.apiPost("settings", "", "", this.$auth, formData)
      );
    },
    saveSettings() {
      return this.saveSetting("proxmox_graylog_check", {
        metric_name: this.settingsForm.metric_name.trim() || "check_graylog",
        stale_hours: Number(this.settingsForm.stale_hours) || 24,
      });
    },
    openDefer(guest) {
      this.deferModal = { show: true, guest, days: 7, reason: "" };
    },
    // Store deferrals without the given guest's entry (and any expired ones)
    persistDeferrals(guest, extra) {
      const today = new Date().toISOString().slice(0, 10);
      const kept = this.deferrals.filter(
        (d) =>
          !(
            String(d.cluster_name) === String(guest.cluster_name) &&
            String(d.id) === String(guest.id)
          ) &&
          (!d.until || d.until >= today)
      );
      return this.saveSetting(
        "proxmox_graylog_deferrals",
        extra ? [...kept, extra] : kept
      );
    },
    saveDeferral() {
      const { guest, days, reason } = this.deferModal;
      let until = null;
      if (days) {
        const date = new Date();
        date.setDate(date.getDate() + days);
        until = date.toISOString().slice(0, 10);
      }
      return this.persistDeferrals(guest, {
        cluster_name: guest.cluster_name,
        id: guest.id,
        name: guest.name,
        until,
        reason: reason.trim(),
      });
    },
    removeDeferral(guest) {
      return this.persistDeferrals(guest, null);
    },
  },
};
</script>
