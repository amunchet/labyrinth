<template>
  <b-container fluid class="mt-4 text-left unifi">
    <b-card no-body>
      <b-tabs card pills>
        <b-tab title="Network">
          <div class="d-flex flex-wrap align-items-center mb-2">
            <div class="mr-auto">
              <h4 class="mb-0">
                <font-awesome-icon icon="network-wired" class="mr-1" />UniFi
              </h4>
              <small class="text-muted">
                Controllers are checked every minute: device state, what is
                plugged into each switch port, and Protect cameras.
              </small>
            </div>
            <b-button
              variant="primary"
              :disabled="refreshing"
              @click="refresh()"
            >
              <b-spinner small v-if="refreshing" class="mr-1" />Check now
            </b-button>
          </div>

          <b-spinner v-if="loading" />
          <div v-else>
            <b-alert v-if="!status.controllers.length" show variant="info">
              No UniFi controllers yet: add one under Settings.
            </b-alert>
            <b-row v-else class="mb-2">
              <b-col
                v-for="card in summary_cards"
                :key="card.label"
                cols="6"
                md="3"
                class="mb-2"
              >
                <b-card :class="'summary border-' + card.variant">
                  <div class="text-muted small">{{ card.label }}</div>
                  <div :class="'value text-' + card.variant">
                    {{ card.value }}
                  </div>
                </b-card>
              </b-col>
            </b-row>

            <b-alert v-if="status.problems.length" show variant="danger">
              <div v-for="(problem, idx) in status.problems" :key="idx">
                <b-badge
                  :variant="problem.severity == 'error' ? 'danger' : 'warning'"
                  >{{ problem.alert_name }}</b-badge
                >
                {{ problem.summary }}
                <small v-if="problem.stale" class="text-muted"
                  >(last known: its controller is not answering)</small
                >
              </div>
            </b-alert>

            <b-card
              v-for="controller in status.controllers"
              :key="controller._id"
              no-body
              class="mb-3"
            >
              <b-card-header class="d-flex flex-wrap align-items-center p-2">
                <strong class="mr-2">{{ controller.name }}</strong>
                <small class="mr-2 text-muted">{{
                  controllerState(controller)
                }}</small>
                <b-badge v-if="controller.error" variant="danger">{{
                  controller.error
                }}</b-badge>
              </b-card-header>
              <div
                v-for="site in controller.sites.filter((x) => x.monitored)"
                :key="site.site"
                class="p-2"
              >
                <h6 class="mb-1">
                  {{ site.name }}
                  <b-badge v-if="site.location" variant="info">{{
                    site.location
                  }}</b-badge>
                  <small v-else class="text-muted"
                    >(no location: map it under Settings)</small
                  >
                  <small class="text-muted">
                    · {{ site.devices.length }} devices,
                    {{ site.client_count }} clients connected
                  </small>
                </h6>
                <b-table
                  small
                  hover
                  responsive
                  :items="rowsOf(site)"
                  :fields="device_fields"
                  show-empty
                  empty-text="No devices"
                  @row-clicked="toggle"
                >
                  <template #cell(state)="row">
                    <b-badge :variant="stateVariant(row.item)">{{
                      row.item.disabled ? "disabled" : row.item.state
                    }}</b-badge>
                  </template>
                  <template #cell(name)="row">
                    <font-awesome-icon
                      :icon="typeIcon(row.item.type)"
                      class="mr-1 text-muted"
                    />
                    {{ row.item.name }}
                    <small class="text-muted">{{ row.item.model }}</small>
                    <b-link
                      v-if="row.item.key"
                      class="ml-1"
                      title="Open in Locations"
                      @click.stop="openDevice(row.item.key)"
                      ><font-awesome-icon icon="external-link-alt"
                    /></b-link>
                  </template>
                  <template #cell(uplink)="row">
                    {{ uplinkLabel(row.item.uplink) }}
                  </template>
                  <template #cell(clients)="row">
                    {{ row.item.clients }}
                    <small
                      v-if="row.item.downstream > row.item.clients"
                      class="text-muted"
                      >· {{ row.item.downstream }} behind it</small
                    >
                  </template>
                  <template #row-details="row">
                    <UnifiPorts :ports="row.item.ports" @select="openDevice" />
                  </template>
                </b-table>
              </div>
            </b-card>
          </div>
        </b-tab>

        <b-tab :title="'Cameras (' + cameras.length + ')'">
          <b-alert
            v-for="controller in protect_errors"
            :key="controller._id"
            show
            variant="warning"
          >
            Protect on {{ controller.name }} is not answering:
            {{ controller.protect.error }}
            <span v-if="controller.protect.stale"
              >(showing its last known cameras)</span
            >
          </b-alert>
          <b-alert v-if="!loading && !cameras.length" show variant="info">
            No cameras. Turn on "Watch Protect cameras" for a console under
            Settings.
          </b-alert>
          <b-table
            v-else
            small
            hover
            responsive
            :items="cameras"
            :fields="camera_fields"
          >
            <template #cell(state)="row">
              <b-badge
                :variant="
                  row.item.state == 'connected'
                    ? 'success'
                    : row.item.state == 'disconnected'
                    ? 'danger'
                    : 'warning'
                "
                >{{ row.item.state }}</b-badge
              >
            </template>
            <template #cell(name)="row">
              {{ row.item.name }}
              <small class="text-muted">{{ row.item.model }}</small>
              <b-link
                v-if="row.item.key"
                class="ml-1"
                title="Open in Locations"
                @click="openDevice(row.item.key)"
                ><font-awesome-icon icon="external-link-alt"
              /></b-link>
            </template>
            <template #cell(uplink)="row">
              {{ uplinkLabel(row.item.uplink) }}
            </template>
          </b-table>
        </b-tab>

        <b-tab title="Settings" lazy>
          <UnifiSettings :status="status" @changed="refresh()" />
        </b-tab>
      </b-tabs>
    </b-card>
  </b-container>
</template>
<script>
import Helper from "@/helper";
import UnifiPorts from "@/components/UnifiPorts";
import UnifiSettings from "@/components/UnifiSettings";

// UniFi controllers: their sites' devices (state, uplink, switch ports),
// Protect cameras and current problems, from /unifi/
export default {
  name: "UniFi",
  components: { UnifiPorts, UnifiSettings },
  data() {
    return {
      loading: true,
      refreshing: false,
      status: { controllers: [], problems: [] },
      expanded: [],
      timeout: null,
      device_fields: [
        { key: "state", sortable: true },
        { key: "name", sortable: true },
        { key: "ip", label: "IP", sortable: true },
        { key: "uplink", label: "Plugged into" },
        { key: "clients", label: "Clients", sortable: true },
        { key: "version", label: "Firmware" },
      ],
      camera_fields: [
        { key: "state", sortable: true },
        { key: "name", sortable: true },
        { key: "ip", label: "IP", sortable: true },
        { key: "uplink", label: "Plugged into" },
        { key: "location", sortable: true },
        { key: "controller", sortable: true },
      ],
    };
  },
  computed: {
    devices() {
      let retval = [];
      this.status.controllers.forEach((controller) =>
        controller.sites.forEach((site) => retval.push(...site.devices))
      );
      return retval;
    },
    cameras() {
      let retval = [];
      this.status.controllers.forEach((controller) =>
        ((controller.protect || {}).cameras || []).forEach((camera) =>
          retval.push({ ...camera, controller: controller.name })
        )
      );
      return retval;
    },
    protect_errors() {
      return this.status.controllers.filter(
        (x) => x.protect && x.protect.error && !x.error
      );
    },
    summary_cards() {
      let offline = this.devices.filter((x) => x.offline).length;
      let cameras_offline = this.cameras.filter(
        (x) => x.state == "disconnected"
      ).length;
      return [
        { label: "Devices", value: this.devices.length, variant: "primary" },
        {
          label: "Devices offline",
          value: offline,
          variant: offline ? "danger" : "success",
        },
        { label: "Cameras", value: this.cameras.length, variant: "primary" },
        {
          label: "Cameras offline",
          value: cameras_offline,
          variant: cameras_offline ? "danger" : "success",
        },
      ];
    },
  },
  methods: {
    rowsOf(site) {
      // b-table opens a row's ports when `_showDetails` is set; kept by MAC
      // so it survives reloads
      return site.devices.map((x) => ({
        ...x,
        _showDetails: this.expanded.includes(x.mac),
      }));
    },
    toggle(item) {
      if (this.expanded.includes(item.mac)) {
        this.expanded = this.expanded.filter((x) => x != item.mac);
      } else if (item.ports.length) {
        this.expanded = this.expanded.concat([item.mac]);
      }
    },
    stateVariant(device) {
      if (device.disabled) {
        return "secondary";
      }
      if (device.offline) {
        return "danger";
      }
      return device.state == "connected" ? "success" : "warning";
    },
    typeIcon(type) {
      let found = Helper.deviceTypes[type];
      return found ? found.icon : "circle";
    },
    uplinkLabel(uplink) {
      if (!uplink) {
        return "";
      }
      let retval = uplink.name || uplink.mac;
      if (uplink.port) {
        retval += " port " + uplink.port;
      }
      return retval + (uplink.link_type ? " (" + uplink.link_type + ")" : "");
    },
    ago(epoch) {
      let minutes = Math.max(0, Math.round((Date.now() / 1000 - epoch) / 60));
      if (minutes < 120) {
        return minutes + "m ago";
      }
      let hours = Math.round(minutes / 60);
      return hours < 48 ? hours + "h ago" : Math.round(hours / 24) + "d ago";
    },
    controllerState(controller) {
      if (!controller.fetched_at) {
        return controller.error ? "Never reached" : "Not checked yet";
      }
      if (controller.stale) {
        return (
          "Not answering – showing results from " +
          this.ago(controller.fetched_at)
        );
      }
      return "Checked " + this.ago(controller.fetched_at);
    },
    openDevice(key) {
      this.$router.push({ path: "/locations", query: { device: key } });
    },
    load: /* istanbul ignore next */ async function () {
      clearTimeout(this.timeout);
      try {
        this.status = await Helper.apiCall("unifi", "", this.$auth);
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      this.loading = false;
      if (!this._isDestroyed) {
        this.timeout = setTimeout(() => this.load(), 30000);
      }
    },
    refresh: /* istanbul ignore next */ async function () {
      this.refreshing = true;
      try {
        let res = await Helper.apiPost("unifi/refresh", "", "", this.$auth);
        this.status = JSON.parse(res);
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      this.refreshing = false;
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.load();
  },
  destroyed: function () {
    clearTimeout(this.timeout);
  },
};
</script>
<style scoped>
.summary .value {
  font-size: 1.6rem;
  font-weight: 600;
}
</style>
