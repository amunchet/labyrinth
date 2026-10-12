<template>
  <ProxmoxGuestCheck
    title="Telegraf Check"
    route="telegraf-check"
    :statuses="statuses"
    :issue-statuses="issueStatuses"
    :fields="fields"
    empty-text="No guests to show. Add a Proxmox cluster in Settings to begin."
  >
    <template #description="{ summary }">
      Every Proxmox VM and LXC should map to a monitored Labyrinth host that is
      reporting Telegraf metrics (within the last
      {{ summary.stale_minutes || 15 }} minutes).
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
  </ProxmoxGuestCheck>
</template>

<script>
import ProxmoxGuestCheck from "@/components/DiskSpace/ProxmoxGuestCheck";

export default {
  name: "TelegrafCheckView",
  components: { ProxmoxGuestCheck },
  data() {
    return {
      statuses: {
        ok: { label: "OK", variant: "success" },
        unmatched: { label: "No Labyrinth host", variant: "danger" },
        not_monitored: { label: "Not monitored", variant: "warning" },
        no_telegraf: { label: "No Telegraf", variant: "danger" },
        stopped: { label: "Stopped", variant: "secondary" },
      },
      issueStatuses: ["unmatched", "not_monitored", "no_telegraf"],
      fields: [
        { key: "name", label: "Guest", sortable: true },
        { key: "node", label: "Node", sortable: true },
        { key: "labyrinth_host", label: "Labyrinth Host" },
        { key: "telegraf", label: "Last Telegraf Metric" },
        { key: "check_status", label: "Status", sortable: true },
      ],
    };
  },
};
</script>
