<template>
  <b-container fluid class="locations mt-2 text-left">
    <CreateEditHost
      :inp_host="selected_host"
      :all_ips="all_ips"
      @update="loadInventory()"
    />

    <b-modal
      id="location_form"
      :title="form._id ? 'Edit location' : 'New location'"
      size="lg"
    >
      <b-form-group label="Name" description="E.g. a building or remote site">
        <b-input v-model="form.name" :state="form_problem ? false : null" />
      </b-form-group>
      <b-form-group label="Address">
        <b-input v-model="form.address" />
      </b-form-group>
      <b-form-group label="Notes">
        <b-textarea v-model="form.notes" rows="2" />
      </b-form-group>
      <h6>Racks</h6>
      <b-row v-for="(rack, idx) in form.racks" :key="idx" class="mb-1">
        <b-col cols="7">
          <b-input v-model="rack.name" size="sm" placeholder="Rack name" />
        </b-col>
        <b-col cols="3">
          <b-input-group size="sm" append="U">
            <b-input
              v-model.number="rack.units"
              type="number"
              min="1"
              max="60"
            />
          </b-input-group>
        </b-col>
        <b-col cols="2">
          <b-button
            size="sm"
            variant="link"
            class="text-danger"
            @click="form.racks.splice(idx, 1)"
            ><font-awesome-icon icon="times"
          /></b-button>
        </b-col>
      </b-row>
      <b-button
        size="sm"
        variant="outline-primary"
        @click="form.racks.push({ name: '', units: 42 })"
        ><font-awesome-icon icon="plus" /> Rack</b-button
      >
      <div class="text-danger mt-2" v-if="form_problem">{{ form_problem }}</div>
      <template #modal-footer="{ cancel }">
        <div class="w-100">
          <b-button
            v-if="form._id"
            class="float-left"
            variant="danger"
            @click="deleteLocation()"
            >Delete</b-button
          >
          <b-button
            class="float-right ml-2"
            variant="primary"
            :disabled="!!form_problem"
            @click="saveLocation()"
            >Save</b-button
          >
          <b-button class="float-right" @click="cancel()">Cancel</b-button>
        </div>
      </template>
    </b-modal>

    <div class="d-flex align-items-center flex-wrap mb-2">
      <h3 class="mb-0 mr-3">
        <font-awesome-icon icon="building" class="mr-1" />Locations
      </h3>
      <b-nav pills class="mr-auto">
        <b-nav-item
          v-for="location in locations"
          :key="location.name"
          :active="selected == location.name"
          @click="select(location.name)"
        >
          {{ location.name }}
          <b-badge v-if="problemCount(location.name)" variant="danger">{{
            problemCount(location.name)
          }}</b-badge>
          <small class="ml-1 count">{{
            devicesAt(location.name).length
          }}</small>
        </b-nav-item>
        <b-nav-item :active="selected === ''" @click="select('')">
          Unassigned
          <small class="ml-1 count">{{ devicesAt("").length }}</small>
        </b-nav-item>
      </b-nav>
      <b-button variant="success" size="sm" @click="editLocation(null)">
        <font-awesome-icon icon="plus" /> Location
      </b-button>
    </div>

    <b-spinner v-if="loading" class="m-2" />
    <div v-else>
      <b-alert v-if="!locations.length" show variant="info">
        No locations yet. Add each building or site, then give devices a
        location – or set a location on a subnet (Dashboard, click the subnet)
        so all of its hosts land there automatically.
      </b-alert>

      <div v-if="current" class="d-flex flex-wrap align-items-start mb-2">
        <div class="mr-auto">
          <h4 class="mb-0">{{ current.name }}</h4>
          <small class="text-muted">{{ current.address }}</small>
          <div class="notes small" v-if="current.notes">
            {{ current.notes }}
          </div>
        </div>
        <b-button
          size="sm"
          variant="outline-primary"
          class="mr-1"
          @click="editLocation(current)"
          ><font-awesome-icon icon="edit" /> Location</b-button
        >
        <b-button size="sm" variant="outline-success" @click="addDevice()"
          ><font-awesome-icon icon="plus" /> Device</b-button
        >
      </div>
      <div v-else-if="selected === ''" class="mb-2">
        <h4 class="mb-0">Unassigned devices</h4>
        <small class="text-muted">
          Devices without a location of their own, their subnet's or their
          Proxmox node's. Pick a location per device below, or give a whole
          subnet a location from the Dashboard.
        </small>
      </div>

      <!-- Keyed so each location opens on its first tab: b-tabs otherwise
           keeps the previously active tab when tabs come and go -->
      <b-tabs :key="selected" v-model="tab" content-class="mt-2">
        <b-tab v-if="current" title="Map">
          <LocationMap
            :all_maps="maps"
            :location="selected"
            :devices="devices_here"
            editable
            @changed="loadMaps()"
            @edit-device="editDevice"
          />
        </b-tab>

        <b-tab v-if="current" :title="'Racks (' + current.racks.length + ')'">
          <div v-if="!current.racks.length" class="text-muted">
            No racks here yet.
            <b-link @click="editLocation(current)">Add a rack</b-link> to lay
            out servers, switches and patch panels by U position.
          </div>
          <b-row v-else>
            <b-col lg="8">
              <div class="racks">
                <div v-for="rack in rack_layouts" :key="rack.name" class="rack">
                  <div class="rack-title">
                    {{ rack.name }} <small>{{ rack.units }}U</small>
                  </div>
                  <div
                    class="rack-body"
                    :style="{
                      gridTemplateRows: 'repeat(' + rack.units + ', 1.3rem)',
                    }"
                  >
                    <div
                      v-for="u in rack.slots"
                      :key="'u' + u"
                      class="slot"
                      :style="{ gridRow: rack.units - u + 1 }"
                      @dragover.prevent
                      @drop.prevent="dropOnRack($event, rack, u)"
                    >
                      <span class="u-number">{{ u }}</span>
                    </div>
                    <div
                      v-for="item in rack.devices"
                      :key="item.device._live.key"
                      :class="
                        'rack-device status-' +
                        item.device._live.status +
                        (item.overlaps ? ' overlap' : '') +
                        (rack_key == item.device._live.key ? ' active' : '')
                      "
                      :style="{ gridRow: item.row + ' / span ' + item.height }"
                      :title="item.overlaps ? 'Overlaps another device' : ''"
                      draggable="true"
                      @dragstart="dragStart($event, item.device)"
                      @click="rack_key = item.device._live.key"
                    >
                      <font-awesome-icon
                        :icon="deviceIcon(item.device)"
                        class="mr-1"
                      />
                      <span class="rack-device-name">{{
                        deviceName(item.device)
                      }}</span>
                      <small v-if="item.device.ip" class="ml-1">{{
                        item.device.ip
                      }}</small>
                      <small v-if="guestsOf(item.device).length" class="ml-1">
                        · {{ guestsOf(item.device).length }} VM/LXC
                      </small>
                    </div>
                  </div>
                </div>
              </div>
            </b-col>
            <b-col lg="4" class="rack-side">
              <div
                class="unracked mb-2"
                @dragover.prevent
                @drop.prevent="dropOnUnracked($event)"
              >
                <h6>Not in a rack ({{ unracked.length }})</h6>
                <small class="text-muted"
                  >Drag devices onto a rack slot (the slot becomes the device's
                  top U); drag them back here to un-rack.</small
                >
                <div class="chips mt-1">
                  <div
                    v-for="device in unracked"
                    :key="device._live.key"
                    :class="'chip status-' + device._live.status"
                    draggable="true"
                    @dragstart="dragStart($event, device)"
                    @click="rack_key = device._live.key"
                  >
                    <font-awesome-icon
                      :icon="deviceIcon(device)"
                      class="mr-1"
                    />
                    {{ deviceName(device) }}
                    <small v-if="(device.rack_height || 1) > 1"
                      >{{ device.rack_height }}U</small
                    >
                  </div>
                </div>
              </div>
              <DeviceCard
                v-if="rack_device"
                :device="rack_device"
                :uplink_device="device_map[rack_device.uplink] || null"
                :guests="guestsOf(rack_device)"
                @edit="editDevice(rack_device)"
              />
              <div v-else class="text-muted small">
                Click a device for details.
              </div>
              <b-card v-if="rack_node" no-body class="mt-2">
                <b-card-header class="p-2">
                  <font-awesome-icon icon="server" class="mr-1" /> Proxmox
                  guests on {{ rack_node.name }}
                </b-card-header>
                <b-table
                  small
                  striped
                  class="mb-0 guests"
                  :items="rack_node.guests"
                  :fields="guest_fields"
                  show-empty
                  empty-text="No VMs or containers"
                >
                  <template v-slot:cell(kind)="row">
                    {{ row.item.kind.toUpperCase() }} {{ row.item.vmid }}
                  </template>
                  <template v-slot:cell(status)="row">
                    <b-badge
                      :variant="
                        row.item.status == 'running' ? 'success' : 'secondary'
                      "
                      >{{ row.item.status }}</b-badge
                    >
                  </template>
                  <template v-slot:cell(disk)="row">
                    {{ percent(row.item.disk, row.item.maxdisk) }}
                  </template>
                  <template v-slot:cell(host_key)="row">
                    <b-link
                      v-if="device_map[row.item.host_key]"
                      @click="editDevice(device_map[row.item.host_key])"
                    >
                      <b-badge
                        :variant="
                          statuses[device_map[row.item.host_key]._live.status]
                            .variant
                        "
                        >{{
                          statuses[device_map[row.item.host_key]._live.status]
                            .label
                        }}</b-badge
                      >
                    </b-link>
                    <small v-else class="text-muted">not a host</small>
                  </template>
                </b-table>
              </b-card>
            </b-col>
          </b-row>
        </b-tab>

        <b-tab :title="'Devices (' + devices_here.length + ')'">
          <div class="d-flex flex-wrap mb-2">
            <b-input
              v-model="filter"
              size="sm"
              class="mr-2 mb-1 filter"
              placeholder="Filter by name, IP, MAC, model..."
            />
            <b-select
              v-model="type_filter"
              size="sm"
              class="mr-2 mb-1 type-filter"
              :options="type_filter_options"
            />
            <b-button
              v-if="current"
              size="sm"
              variant="outline-success"
              class="mb-1"
              @click="addDevice()"
              ><font-awesome-icon icon="plus" /> Device</b-button
            >
          </div>
          <b-table
            small
            striped
            hover
            responsive
            :items="device_rows"
            :fields="device_fields"
            :per-page="50"
            :current-page="page"
            show-empty
            empty-text="No devices here"
          >
            <template v-slot:cell(status)="row">
              <b-badge :variant="statuses[row.item.status].variant">{{
                statuses[row.item.status].label
              }}</b-badge>
            </template>
            <template v-slot:cell(name)="row">
              <font-awesome-icon
                :icon="deviceIcon(row.item.device)"
                class="mr-1 text-muted"
              />
              {{ row.item.name }}
            </template>
            <template v-slot:cell(location)="row">
              <b-select
                v-if="selected === ''"
                size="sm"
                :value="''"
                :options="[
                  { value: '', text: 'Assign to...' },
                  ...locations.map((x) => x.name),
                ]"
                @change="(val) => assign(row.item.device, val)"
              />
              <span v-else-if="row.item.location_source != 'explicit'">
                <small class="text-muted"
                  >from {{ row.item.location_source }}</small
                >
              </span>
            </template>
            <template v-slot:cell(actions)="row">
              <b-button
                size="sm"
                variant="link"
                class="p-0"
                @click="editDevice(row.item.device)"
                ><font-awesome-icon icon="edit"
              /></b-button>
            </template>
          </b-table>
          <b-pagination
            v-if="device_rows.length > 50"
            v-model="page"
            :total-rows="device_rows.length"
            :per-page="50"
            size="sm"
          />
        </b-tab>
      </b-tabs>
    </div>
  </b-container>
</template>
<script>
import Helper from "@/helper";
import CreateEditHost from "@/components/CreateEditHost";
import DeviceCard from "@/components/DeviceCard";
import LocationMap from "@/components/LocationMap";

// Buildings/sites: a floor plan map, rack layouts and the devices at each
// location, all with live status from /inventory/
export default {
  name: "Locations",
  components: { CreateEditHost, DeviceCard, LocationMap },
  data() {
    return {
      loading: true,
      inventory: { locations: [], devices: [], proxmox: [] },
      maps: [],
      selected: "",
      tab: 0,
      selected_host: "",
      form: { _id: "", name: "", address: "", notes: "", racks: [] },
      rack_key: "",
      filter: "",
      type_filter: "",
      page: 1,
      timeout: null,
      statuses: Helper.deviceStatuses,
      guest_fields: [
        { key: "kind", label: "Guest" },
        "name",
        "status",
        "disk",
        { key: "host_key", label: "Host" },
      ],
      device_fields: [
        { key: "status", sortable: true },
        { key: "name", sortable: true },
        { key: "type", sortable: true },
        { key: "ip", label: "IP", sortable: true },
        { key: "rack", sortable: true },
        { key: "uplink", sortable: true },
        { key: "location", label: "" },
        { key: "actions", label: "" },
      ],
    };
  },
  computed: {
    locations() {
      return this.inventory.locations;
    },
    current() {
      return this.locations.find((x) => x.name == this.selected) || null;
    },
    device_map() {
      let retval = {};
      this.inventory.devices.forEach((x) => (retval[x._live.key] = x));
      return retval;
    },
    devices_here() {
      return this.devicesAt(this.selected);
    },
    all_ips() {
      return new Set(this.inventory.devices.map((x) => x.ip).filter((x) => x));
    },
    rack_layouts() {
      if (!this.current) {
        return [];
      }
      return this.current.racks.map((rack) => {
        let occupied = {};
        let items = this.devices_here
          .filter((x) => x.rack == rack.name && x.rack_unit)
          .map((device) => {
            let height = device.rack_height || 1;
            let bottom = Math.min(device.rack_unit, rack.units);
            let top = Math.min(bottom + height - 1, rack.units);
            for (let u = bottom; u <= top; u++) {
              occupied[u] = (occupied[u] || 0) + 1;
            }
            return {
              device: device,
              bottom: bottom,
              top: top,
              height: top - bottom + 1,
              row: rack.units - top + 1,
            };
          });
        items.forEach((item) => {
          item.overlaps = false;
          for (let u = item.bottom; u <= item.top; u++) {
            item.overlaps = item.overlaps || occupied[u] > 1;
          }
        });
        let slots = [];
        for (let u = rack.units; u >= 1; u--) {
          slots.push(u);
        }
        return {
          name: rack.name,
          units: rack.units,
          slots: slots,
          devices: items,
        };
      });
    },
    unracked() {
      let racks = this.current ? this.current.racks.map((x) => x.name) : [];
      return this.devices_here.filter(
        (x) =>
          !(racks.indexOf(x.rack) != -1 && x.rack_unit) &&
          ["vm", "lxc"].indexOf(x._live.type) == -1
      );
    },
    rack_device() {
      return this.device_map[this.rack_key] || null;
    },
    rack_node() {
      for (let cluster of this.inventory.proxmox) {
        let found = cluster.nodes.find(
          (x) => x.host_key && x.host_key == this.rack_key
        );
        if (found) {
          return found;
        }
      }
      return null;
    },
    type_filter_options() {
      return [{ value: "", text: "All types" }].concat(
        Object.keys(Helper.deviceTypes).map((x) => ({
          value: x,
          text: Helper.deviceTypes[x].label,
        }))
      );
    },
    device_rows() {
      let filter = this.filter.toLowerCase();
      return this.devices_here
        .filter((x) => !this.type_filter || x._live.type == this.type_filter)
        .filter(
          (x) =>
            !filter ||
            [x.host, x.ip, x.mac, x.vendor, x.model, x.serial, x.notes]
              .join(" ")
              .toLowerCase()
              .indexOf(filter) != -1
        )
        .map((device) => {
          let type = Helper.deviceTypes[device._live.type];
          let uplink = this.device_map[device.uplink];
          return {
            device: device,
            status: device._live.status,
            name: Helper.deviceName(device),
            type: type ? type.label : "",
            ip: device.ip,
            rack: device.rack
              ? device.rack + (device.rack_unit ? " U" + device.rack_unit : "")
              : "",
            uplink: uplink
              ? Helper.deviceName(uplink) +
                (device.link_type ? " (" + device.link_type + ")" : "")
              : "",
            location_source: device._live.location_source,
          };
        });
    },
    form_problem() {
      let name = (this.form.name || "").trim();
      if (!name) {
        return "A location needs a name.";
      }
      if (name.indexOf("/") != -1) {
        return "Location names cannot contain '/'.";
      }
      let clash = this.locations.find(
        (x) =>
          x.name.toLowerCase() == name.toLowerCase() && x._id != this.form._id
      );
      if (clash) {
        return "Another location is already called " + clash.name + ".";
      }
      let rack_names = this.form.racks.map((x) => (x.name || "").trim());
      if (rack_names.some((x) => !x)) {
        return "Every rack needs a name.";
      }
      if (new Set(rack_names).size != rack_names.length) {
        return "Rack names must be unique.";
      }
      if (this.form.racks.some((x) => !(x.units >= 1 && x.units <= 60))) {
        return "Racks are 1 to 60 units tall.";
      }
      return "";
    },
  },
  methods: {
    deviceIcon: Helper.deviceIcon,
    deviceName: Helper.deviceName,
    devicesAt(location) {
      return this.inventory.devices.filter((x) => x._live.location == location);
    },
    problemCount(location) {
      return this.devicesAt(location).filter(
        (x) => x._live.status == "down" || x._live.status == "error"
      ).length;
    },
    guestsOf(device) {
      return this.inventory.devices.filter(
        (x) => x._live.parent == device._live.key
      );
    },
    percent(used, total) {
      return total ? Math.round((used / total) * 100) + "%" : "";
    },
    select(location) {
      this.selected = location;
      this.rack_key = "";
      this.page = 1;
      this.tab = 0;
    },
    addDevice() {
      // A fresh object each time, so the modal resets; no MAC means "new"
      this.selected_host = {
        ip: "",
        mac: "",
        host: "",
        subnet: "",
        group: "",
        tags: "",
        icon: "",
        class: "",
        services: [],
        monitor: false,
        location: this.selected,
      };
      this.$bvModal.show("create_edit_host");
    },
    editDevice(device) {
      this.selected_host = JSON.parse(JSON.stringify(device));
      this.$bvModal.show("create_edit_host");
    },
    editLocation(location) {
      this.form = location
        ? {
            _id: location._id,
            name: location.name,
            address: location.address || "",
            notes: location.notes || "",
            racks: location.racks.map((x) => ({
              name: x.name,
              units: x.units,
              previous_name: x.name,
            })),
          }
        : { _id: "", name: "", address: "", notes: "", racks: [] };
      this.$bvModal.show("location_form");
    },
    dragStart(event, device) {
      event.dataTransfer.setData("text/plain", device._live.key);
    },
    dropOnRack(event, rack, u) {
      let device = this.device_map[event.dataTransfer.getData("text/plain")];
      if (!device) {
        return;
      }
      // The slot dropped on becomes the device's top U, kept inside the rack
      let height = device.rack_height || 1;
      this.updateInventory(device, {
        location: this.selected,
        rack: rack.name,
        rack_unit: Math.max(
          1,
          Math.min(u - height + 1, rack.units - height + 1)
        ),
      });
    },
    dropOnUnracked: /* istanbul ignore next */ function (event) {
      let device = this.device_map[event.dataTransfer.getData("text/plain")];
      if (device && device.rack) {
        this.updateInventory(device, { rack: "" });
      }
    },
    assign: /* istanbul ignore next */ function (device, location) {
      if (location) {
        this.updateInventory(device, { location: location });
      }
    },
    updateInventory: /* istanbul ignore next */ async function (
      device,
      fields
    ) {
      let formData = new FormData();
      formData.append("data", JSON.stringify(fields));
      try {
        await Helper.apiPost(
          "host",
          "",
          encodeURIComponent(device._live.key) + "/inventory",
          this.$auth,
          formData
        );
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      await this.loadInventory();
    },
    saveLocation: /* istanbul ignore next */ async function () {
      let data = JSON.parse(JSON.stringify(this.form));
      if (!data._id) {
        delete data._id;
      }
      let formData = new FormData();
      formData.append("data", JSON.stringify(data));
      try {
        await Helper.apiPost("location", "", "", this.$auth, formData);
        this.$bvModal.hide("location_form");
        // Select only once it is loaded, so its tabs exist and Map opens
        await this.loadInventory();
        await this.loadMaps();
        this.select(data.name.trim());
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    deleteLocation: /* istanbul ignore next */ async function () {
      let count = this.devicesAt(this.form.name).length;
      let ok = await this.$bvModal.msgBoxConfirm(
        "Delete " +
          this.form.name +
          "? Its " +
          count +
          " device(s), subnets and maps are kept, just unassigned."
      );
      if (!ok) {
        return;
      }
      try {
        await Helper.apiDelete("location", this.form._id, this.$auth);
        this.$bvModal.hide("location_form");
        this.select("");
        await this.loadInventory();
        await this.loadMaps();
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    loadMaps: /* istanbul ignore next */ async function () {
      try {
        this.maps = await Helper.apiCall("custom_dashboards", "", this.$auth);
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    loadInventory: /* istanbul ignore next */ async function () {
      clearTimeout(this.timeout);
      try {
        this.inventory = await Helper.apiCall("inventory", "", this.$auth);
        if (this.loading) {
          // /locations?device=<key> (e.g. from Home) opens that device
          let key = this.$route && this.$route.query.device;
          if (key && this.device_map[key]) {
            this.select(this.device_map[key]._live.location);
            this.editDevice(this.device_map[key]);
          } else if (this.locations.length) {
            this.selected = this.locations[0].name;
          }
        }
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      this.loading = false;
      // A reload still in flight when the page is left must not restart polling
      if (!this._isDestroyed) {
        clearTimeout(this.timeout);
        this.timeout = setTimeout(() => this.loadInventory(), 10000);
      }
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.loadMaps();
    this.loadInventory();
  },
  destroyed: function () {
    clearTimeout(this.timeout);
  },
};
</script>
<style scoped>
.count {
  opacity: 0.7;
}
.notes {
  white-space: pre-wrap;
}
.filter {
  max-width: 20rem;
}
.type-filter {
  max-width: 12rem;
}
.racks {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-start;
}
.rack {
  width: 17rem;
  border: 3px solid #495057;
  border-radius: 0.4rem;
  background-color: #343a40;
}
.rack-title {
  color: white;
  text-align: center;
  padding: 0.2rem;
  font-weight: 600;
}
.rack-body {
  display: grid;
  grid-template-columns: 100%;
  background-color: #212529;
  padding: 0 0.3rem 0.3rem;
}
.slot {
  grid-column: 1;
  border-top: 1px solid #3d4349;
  position: relative;
}
.u-number {
  font-size: 0.6rem;
  color: #868e96;
  padding-left: 0.2rem;
}
.rack-device {
  grid-column: 1;
  z-index: 1;
  margin: 1px 0 1px 1.4rem;
  padding: 0 0.4rem;
  border-radius: 0.2rem;
  background-color: #e9ecef;
  border-left: 5px solid #6c757d;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  cursor: move;
}
.rack-device-name {
  overflow: hidden;
  text-overflow: ellipsis;
}
.rack-device.active,
.chip.active {
  outline: 3px solid #007bff;
}
.rack-device.overlap {
  background-image: repeating-linear-gradient(
    45deg,
    #fff3cd,
    #fff3cd 6px,
    #e9ecef 6px,
    #e9ecef 12px
  );
}
.status-up {
  border-left-color: #28a745;
}
.status-down,
.status-error {
  border-left-color: #dc3545;
  background-color: #fbe9eb;
}
.status-warning {
  border-left-color: #fd7e14;
}
.status-none {
  border-left-color: #ced4da;
}
/* Beside the (tall) racks and sticky, so drag source and slot are both on screen */
.rack-side {
  position: sticky;
  top: 0.5rem;
  align-self: flex-start;
}
.unracked {
  border: 2px dashed #ced4da;
  border-radius: 0.5rem;
  padding: 0.5rem;
  max-height: 40vh;
  overflow-y: auto;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.chip {
  font-size: 0.8rem;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  background-color: #f1f3f5;
  border-left: 5px solid #6c757d;
  cursor: move;
  white-space: nowrap;
}
.guests {
  font-size: 0.8rem;
}
</style>
