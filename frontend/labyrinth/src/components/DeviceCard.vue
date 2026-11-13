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
            >(from {{ location_source }})</small
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
        <template v-if="unifi">
          <dt>UniFi</dt>
          <dd>
            {{ unifi_label }}
            <div class="text-muted">
              {{ [unifi.site, unifi.controller].filter(Boolean).join(" · ") }}
              <span v-if="unifi.stale" class="text-warning"
                >(controller not answering)</span
              >
            </div>
          </dd>
          <template v-if="unifi.uplink && unifi.uplink.name">
            <dt>Plugged into</dt>
            <dd>
              <b-link
                v-if="unifi.uplink.key"
                @click="$emit('select', unifi.uplink.key)"
                >{{ unifi.uplink.name }}</b-link
              >
              <span v-else>{{ unifi.uplink.name }}</span>
              <span v-if="unifi.uplink.port">
                port {{ unifi.uplink.port }}</span
              >
              ({{ unifi.uplink.link_type }})
            </dd>
          </template>
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
      <UnifiPorts
        v-if="unifi && unifi.ports && unifi.ports.length"
        class="mb-2"
        :ports="unifi.ports"
        @select="(key) => $emit('select', key)"
      />
      <b-button size="sm" variant="outline-primary" @click="$emit('edit')">
        <font-awesome-icon icon="edit" /> Edit
      </b-button>
    </b-card-body>
  </b-card>
</template>
<script>
import Helper from "@/helper";
import UnifiPorts from "@/components/UnifiPorts";

// Live details of one inventory device (as returned by /inventory/); emits
// `select` with the key of a device it links to (its switch, a port's device)
export default {
  name: "DeviceCard",
  components: { UnifiPorts },
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
    location_source() {
      return (
        Helper.locationSources[this.live.location_source] ||
        this.live.location_source
      );
    },
    unifi() {
      return this.live.unifi || null;
    },
    unifi_label() {
      let unifi = this.unifi;
      if (unifi.kind == "device") {
        return [
          unifi.model,
          unifi.state,
          unifi.version && "firmware " + unifi.version,
        ]
          .filter(Boolean)
          .join(" · ");
      }
      if (unifi.kind == "camera") {
        return "Protect camera · " + unifi.state;
      }
      if (unifi.active) {
        return "Client, connected";
      }
      let hours = Math.max(0, (Date.now() / 1000 - unifi.last_seen) / 3600);
      return (
        "Client, last seen " +
        (hours < 48 ? Math.round(hours) + "h" : Math.round(hours / 24) + "d") +
        " ago"
      );
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
      return this.guests.filter((x) =>
        ["down", "error"].includes(x._live.status)
      ).length;
    },
    hardware() {
      return [this.device.vendor, this.device.model, this.device.serial]
        .filter(Boolean)
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
  overflow-wrap: anywhere;
}
.notes {
  white-space: pre-wrap;
}
</style>
