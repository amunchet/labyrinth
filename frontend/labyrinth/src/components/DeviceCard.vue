<template>
  <b-card no-body class="device-card text-left">
    <b-card-header class="d-flex align-items-center p-2">
      <font-awesome-icon :icon="icon" class="mr-2" />
      <strong class="mr-auto name">{{ name }}</strong>
      <b-badge :variant="status.variant">{{ status.label }}</b-badge>
    </b-card-header>
    <b-card-body class="p-2">
      <dl class="mb-2">
        <dt>Type</dt>
        <dd>{{ type_label }}</dd>
        <template v-if="device.ip">
          <dt>IP</dt>
          <dd>{{ device.ip }}</dd>
        </template>
        <template v-if="real_mac">
          <dt>MAC</dt>
          <dd>{{ device.mac }}</dd>
        </template>
        <template v-if="device.ip">
          <dt>Reachability</dt>
          <dd>{{ reachability }}</dd>
        </template>
        <template v-if="service_count">
          <dt>Services</dt>
          <dd>
            {{ live.services.ok }} ok, {{ live.services.warning }} warning,
            {{ live.services.failed }} failing
            <div v-if="live.services.failing.length" class="text-danger">
              {{ live.services.failing.join(", ") }}
            </div>
          </dd>
        </template>
        <dt>Location</dt>
        <dd>
          {{ live.location || "Unassigned" }}
          <small
            v-if="live.location && live.location_source != 'explicit'"
            class="text-muted"
            >(from its {{ live.location_source }})</small
          >
        </dd>
        <template v-if="device.rack">
          <dt>Rack</dt>
          <dd>
            {{ device.rack }}
            <span v-if="device.rack_unit">· {{ units_label }}</span>
          </dd>
        </template>
        <template v-if="live.proxmox">
          <dt>Proxmox</dt>
          <dd>
            <span v-if="live.proxmox.kind == 'node'">
              Node {{ live.proxmox.node }} ({{ live.proxmox.cluster }})
            </span>
            <span v-else>
              {{ live.proxmox.kind.toUpperCase() }} {{ live.proxmox.vmid }} on
              {{ live.proxmox.node }} – {{ live.proxmox.status }}
            </span>
          </dd>
        </template>
        <template v-if="guests.length">
          <dt>Guests</dt>
          <dd>
            {{ guests.length }} VM/LXC
            <span v-if="guest_problems" class="text-danger">
              ({{ guest_problems }} with problems)
            </span>
          </dd>
        </template>
        <template v-if="device.uplink">
          <dt>Uplink</dt>
          <dd>
            {{ uplink_device ? deviceName(uplink_device) : device.uplink }}
            <span v-if="device.link_type">({{ device.link_type }})</span>
          </dd>
        </template>
        <template v-if="hardware">
          <dt>Hardware</dt>
          <dd>{{ hardware }}</dd>
        </template>
        <template v-if="device.notes">
          <dt>Notes</dt>
          <dd class="notes">{{ device.notes }}</dd>
        </template>
      </dl>
      <b-button size="sm" variant="outline-primary" @click="$emit('edit')">
        <font-awesome-icon icon="edit" /> Edit
      </b-button>
    </b-card-body>
  </b-card>
</template>
<script>
import Helper from "@/helper";

// Live details of one inventory device (as returned by /inventory/)
export default {
  name: "DeviceCard",
  props: {
    device: { type: Object, required: true },
    uplink_device: { type: Object, default: null },
    guests: { type: Array, default: () => [] },
  },
  computed: {
    live() {
      return this.device._live;
    },
    name() {
      return Helper.deviceName(this.device);
    },
    icon() {
      return Helper.deviceIcon(this.device);
    },
    status() {
      return Helper.deviceStatuses[this.live.status];
    },
    type_label() {
      let type = Helper.deviceTypes[this.live.type];
      return type ? type.label : "Not set";
    },
    real_mac() {
      // Hosts without a known MAC are keyed by IP or a generated "device-" key
      let mac = this.device.mac || "";
      return mac != this.device.ip && !mac.startsWith("device-");
    },
    reachability() {
      let alive = this.live.alive;
      if (!alive) {
        return "Not checked yet";
      }
      let check =
        alive.method == "port" ? "TCP port " + alive.port + " check" : "ping";
      let ago = Math.max(0, Math.round(Date.now() / 1000 - alive.checked));
      let when = ago < 120 ? ago + "s ago" : Math.round(ago / 60) + "m ago";
      return (
        (alive.up ? "Answered " : "No answer to ") +
        check +
        ", " +
        when +
        (alive.error ? " – " + alive.error : "")
      );
    },
    units_label() {
      let height = this.device.rack_height || 1;
      let top = this.device.rack_unit + height - 1;
      return height > 1
        ? "U" + this.device.rack_unit + "–U" + top
        : "U" + this.device.rack_unit;
    },
    service_count() {
      let services = this.live.services;
      return services ? services.ok + services.warning + services.failed : 0;
    },
    guest_problems() {
      return this.guests.filter(
        (x) => ["down", "error"].indexOf(x._live.status) != -1
      ).length;
    },
    hardware() {
      return [this.device.vendor, this.device.model, this.device.serial]
        .filter((x) => x)
        .join(" · ");
    },
  },
  methods: {
    deviceName: Helper.deviceName,
  },
};
</script>
<style scoped>
.device-card {
  font-size: 0.85rem;
}
.name {
  word-break: break-all;
}
dl {
  display: grid;
  grid-template-columns: max-content auto;
  column-gap: 0.75rem;
  row-gap: 0.15rem;
}
dt {
  font-weight: 600;
  color: #6c757d;
}
dd {
  margin: 0;
  word-break: break-word;
}
.notes {
  white-space: pre-wrap;
}
</style>
