<template>
  <div class="location-map text-left">
    <div class="d-flex flex-wrap align-items-center mb-2">
      <b-select
        v-if="maps.length > 1"
        v-model="selected_name"
        :options="maps.map((x) => x.name)"
        size="sm"
        class="map-select mr-2"
        :disabled="editing"
      />
      <h5 v-else-if="shown" class="mb-0 mr-2">{{ shown.name }}</h5>
      <span>
        <b-badge
          v-for="(count, status) in status_counts"
          :key="status"
          :variant="statuses[status].variant"
          class="mr-1 status-count"
          >{{ count }} {{ statuses[status].label }}</b-badge
        >
      </span>
      <div class="ml-auto mt-1" v-if="editable">
        <b-button
          size="sm"
          variant="outline-primary"
          class="mr-1"
          :disabled="editing"
          @click="new_map_name = ''"
        >
          <font-awesome-icon icon="plus" /> New map
        </b-button>
        <b-button
          v-if="shown"
          size="sm"
          :variant="editing ? 'success' : 'outline-primary'"
          @click="editing ? stopEditing() : startEditing()"
        >
          <font-awesome-icon :icon="editing ? 'check' : 'edit'" />
          {{ editing ? "Done" : "Edit map" }}
        </b-button>
      </div>
    </div>

    <b-form
      inline
      v-if="new_map_name !== null"
      class="mb-2"
      @submit.prevent="createMap()"
    >
      <b-input
        v-model="new_map_name"
        size="sm"
        class="mr-2"
        placeholder="Map name, e.g. Floor 1"
        :state="new_map_name ? !nameProblem(new_map_name) : null"
      />
      <b-button
        size="sm"
        type="submit"
        variant="success"
        :disabled="!new_map_name || !!nameProblem(new_map_name)"
        >Create</b-button
      >
      <b-button size="sm" variant="link" @click="new_map_name = null"
        >Cancel</b-button
      >
      <small class="text-danger ml-2" v-if="new_map_name">{{
        nameProblem(new_map_name)
      }}</small>
    </b-form>

    <div v-if="editing" class="edit-bar mb-2 p-2">
      <b-row>
        <b-col md="4" class="mb-1">
          <small>Map name</small>
          <b-input
            v-model="draft_name"
            size="sm"
            lazy
            :state="draft_name != draft.name ? !nameProblem(draft_name) : null"
            @change="renameMap()"
          />
        </b-col>
        <b-col md="4" class="mb-1">
          <small>Floor plan / background image</small>
          <b-select
            v-model="draft.background_image"
            size="sm"
            :options="[{ value: '', text: '(none – device board)' }, ...images]"
            @change="saveDraft()"
          />
          <b-form-file
            v-model="upload"
            size="sm"
            class="mt-1"
            accept="image/*"
            placeholder="Upload an image..."
          />
        </b-col>
        <b-col md="4" class="mb-1">
          <b-form-checkbox v-model="draft.default" switch @change="saveDraft()">
            Show by default on Home
          </b-form-checkbox>
          <b-button
            size="sm"
            variant="outline-danger"
            class="mt-1 mr-1"
            @click="deleteMap()"
            >Delete map</b-button
          >
          <b-button
            v-if="draft.background_image"
            size="sm"
            variant="link"
            class="mt-1 text-danger"
            @click="deleteImage(draft.background_image)"
            >Delete image file</b-button
          >
        </b-col>
      </b-row>
      <small class="text-muted">
        Drag devices from the list below onto the floor plan, drag markers to
        move them, and drag a marker back onto the list to take it off the map.
      </small>
    </div>

    <b-row>
      <b-col :lg="has_image ? 9 : 12">
        <div
          v-if="has_image"
          class="map-area"
          @dragover.prevent
          @drop.prevent="dropOnMap($event)"
        >
          <img
            ref="image"
            :src="imageUrl(shown.background_image)"
            class="map-image"
            draggable="false"
            @load="onImageLoad($event)"
          />
          <svg
            class="map-links"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            <line
              v-for="link in links"
              :key="link.key"
              :x1="link.x1"
              :y1="link.y1"
              :x2="link.x2"
              :y2="link.y2"
              :class="'link link-' + link.type + ' link-' + link.state"
              vector-effect="non-scaling-stroke"
            />
          </svg>
          <div
            v-for="item in placed"
            :key="item.device._live.key"
            :class="
              'marker status-' +
              item.device._live.status +
              (active_key == item.device._live.key ? ' active' : '')
            "
            :style="{ left: item.x + '%', top: item.y + '%' }"
            :title="tooltip(item.device)"
            :draggable="editing"
            @dragstart="dragStart($event, item.device._live.key)"
            @click="select(item.device)"
          >
            <span class="marker-icon">
              <font-awesome-icon :icon="deviceIcon(item.device)" />
              <span
                v-if="guestProblems(item.device)"
                class="guest-alert"
                :title="guestProblems(item.device) + ' VM/LXC with problems'"
              />
            </span>
            <span class="marker-label">{{ deviceName(item.device) }}</span>
          </div>
        </div>

        <div
          :class="'unplaced ' + (editing ? 'drop-zone' : '')"
          @dragover.prevent
          @drop.prevent="dropOnList($event)"
        >
          <div
            v-if="has_image"
            class="unplaced-header"
            @click="show_unplaced = !show_unplaced"
          >
            <font-awesome-icon
              :icon="show_unplaced || editing ? 'caret-down' : 'caret-right'"
            />
            Not on this map ({{ unplaced.length }})
          </div>
          <div v-if="!has_image || show_unplaced || editing">
            <div v-if="!devices.length" class="text-muted p-2">
              No devices here yet.
            </div>
            <div v-for="group in unplaced_groups" :key="group.type">
              <div class="group-title">{{ group.label }}</div>
              <div class="chips">
                <div
                  v-for="device in group.devices"
                  :key="device._live.key"
                  :class="
                    'chip status-' +
                    device._live.status +
                    (active_key == device._live.key ? ' active' : '')
                  "
                  :title="tooltip(device)"
                  :draggable="editing && has_image"
                  @dragstart="dragStart($event, device._live.key)"
                  @click="select(device)"
                >
                  <font-awesome-icon :icon="deviceIcon(device)" class="mr-1" />
                  {{ deviceName(device) }}
                  <span v-if="device.ip" class="chip-ip">{{ device.ip }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </b-col>
      <b-col :lg="has_image ? 3 : 12" v-if="has_image || active_device">
        <DeviceCard
          v-if="active_device"
          class="mt-2 mt-lg-0 details"
          :device="active_device"
          :uplink_device="device_map[active_device.uplink] || null"
          :guests="guestsOf(active_device)"
          @edit="$emit('edit-device', active_device)"
        />
        <div v-else class="text-muted small mt-2 mt-lg-0">
          Click a device for details.
          <div v-for="(status, key) in statuses" :key="key">
            <span :class="'legend-dot status-' + key" /> {{ status.label }}
          </div>
        </div>
      </b-col>
    </b-row>
  </div>
</template>
<script>
import Helper from "@/helper";
import DeviceCard from "@/components/DeviceCard";

// Floor plan / board of devices with live status.  A map is a custom
// dashboard document: {name, location, background_image, default,
// placements: [{key, x, y}]} where x/y are percentages of the image, so
// markers stay put at any screen size.  Without an image, the map is a board
// of every device at the location ("auto-populated").
export default {
  name: "LocationMap",
  components: { DeviceCard },
  props: {
    all_maps: { type: Array, default: () => [] },
    // Maps of this location are shown; new maps are created here
    location: { type: String, default: "" },
    // Show only this map (e.g. on Home) instead of the location's maps
    map_name: { type: String, default: "" },
    devices: { type: Array, default: () => [] },
    editable: { type: Boolean, default: false },
  },
  data() {
    return {
      selected_name: "",
      editing: false,
      draft: null,
      draft_name: "",
      new_map_name: null,
      images: [],
      upload: null,
      image_size: null,
      show_unplaced: false,
      active_key: "",
      statuses: Helper.deviceStatuses,
    };
  },
  computed: {
    maps() {
      if (this.map_name) {
        return this.all_maps.filter((x) => x.name == this.map_name);
      }
      return this.all_maps.filter((x) => (x.location || "") == this.location);
    },
    map() {
      return (
        this.maps.find((x) => x.name == this.selected_name) ||
        this.maps.find((x) => x.default) ||
        this.maps[0] ||
        null
      );
    },
    shown() {
      return this.editing ? this.draft : this.map;
    },
    has_image() {
      return !!(this.shown && this.shown.background_image);
    },
    device_map() {
      let retval = {};
      this.devices.forEach((x) => (retval[x._live.key] = x));
      return retval;
    },
    placements() {
      if (!this.shown) {
        return [];
      }
      if (this.shown.placements) {
        return this.shown.placements;
      }
      // Maps from the old dashboard editor stored host IPs at pixel offsets
      if (!this.shown.components || !this.image_size) {
        return [];
      }
      let retval = [];
      this.shown.components.forEach((component) => {
        let device = this.devices.find(
          (x) =>
            x.ip == component.name &&
            (!component.subnet || x.subnet == component.subnet)
        );
        if (device) {
          retval.push({
            key: device._live.key,
            x: (component.x / this.image_size.width) * 100,
            y: (component.y / this.image_size.height) * 100,
          });
        }
      });
      return retval;
    },
    placed() {
      if (!this.has_image) {
        return [];
      }
      return this.placements
        .filter((x) => this.device_map[x.key])
        .map((x) => ({ device: this.device_map[x.key], x: x.x, y: x.y }));
    },
    unplaced() {
      let placed = {};
      this.placed.forEach((x) => (placed[x.device._live.key] = true));
      // VMs and containers have no physical spot; they show on their server
      return this.devices.filter(
        (x) =>
          !placed[x._live.key] &&
          !(this.has_image && ["vm", "lxc"].indexOf(x._live.type) != -1)
      );
    },
    unplaced_groups() {
      let groups = {};
      this.unplaced.forEach((device) => {
        let type = device._live.type || "";
        if (!groups[type]) {
          let found = Helper.deviceTypes[type];
          groups[type] = {
            type: type,
            label: found ? found.label : "Type not set",
            devices: [],
          };
        }
        groups[type].devices.push(device);
      });
      let order = Object.keys(Helper.deviceTypes);
      return Object.values(groups).sort(
        (a, b) =>
          (order.indexOf(a.type) + 1 || 99) - (order.indexOf(b.type) + 1 || 99)
      );
    },
    links() {
      // Uplinks between two devices placed on this map (bridges, fiber, ...)
      let positions = {};
      this.placed.forEach((x) => (positions[x.device._live.key] = x));
      let retval = [];
      this.placed.forEach((item) => {
        let other = positions[item.device.uplink];
        if (!other) {
          return;
        }
        let states = [item.device._live.status, other.device._live.status];
        let state = "unknown";
        if (states.some((x) => x == "down" || x == "error")) {
          state = "down";
        } else if (states.every((x) => x == "up" || x == "warning")) {
          state = "up";
        }
        retval.push({
          key: item.device._live.key,
          x1: item.x,
          y1: item.y,
          x2: other.x,
          y2: other.y,
          type: item.device.link_type || "ethernet",
          state: state,
        });
      });
      return retval;
    },
    status_counts() {
      let retval = {};
      this.devices.forEach((x) => {
        retval[x._live.status] = (retval[x._live.status] || 0) + 1;
      });
      return retval;
    },
    active_device() {
      return this.device_map[this.active_key] || null;
    },
  },
  watch: {
    upload: /* istanbul ignore next */ function (file) {
      if (file) {
        this.uploadImage(file);
      }
    },
    map_name: function () {
      this.image_size = null;
    },
    selected_name: function () {
      this.image_size = null;
    },
  },
  methods: {
    deviceIcon: Helper.deviceIcon,
    deviceName: Helper.deviceName,
    imageUrl(name) {
      return (
        Helper.getURL() +
        "custom_dashboard_images/" +
        this.$auth.accessToken +
        "/" +
        encodeURIComponent(name)
      );
    },
    onImageLoad(event) {
      this.image_size = {
        width: event.target.naturalWidth,
        height: event.target.naturalHeight,
      };
    },
    tooltip(device) {
      return (
        Helper.deviceName(device) +
        (device.ip ? " (" + device.ip + ")" : "") +
        " – " +
        Helper.deviceStatuses[device._live.status].label
      );
    },
    guestsOf(device) {
      return this.devices.filter((x) => x._live.parent == device._live.key);
    },
    guestProblems(device) {
      return this.guestsOf(device).filter(
        (x) => x._live.status == "down" || x._live.status == "error"
      ).length;
    },
    select(device) {
      if (!this.editing) {
        this.active_key =
          this.active_key == device._live.key ? "" : device._live.key;
      }
    },
    nameProblem(name) {
      if (!name.trim()) {
        return "A map needs a name";
      }
      if (name.indexOf("/") != -1) {
        return "Map names cannot contain '/'";
      }
      if (this.all_maps.some((x) => x.name == name.trim())) {
        return "A map with that name already exists";
      }
      return "";
    },

    // Editing
    startEditing() {
      this.draft = JSON.parse(JSON.stringify(this.map));
      this.draft.placements = JSON.parse(JSON.stringify(this.placements));
      delete this.draft.components;
      delete this.draft._id;
      this.draft_name = this.draft.name;
      this.editing = true;
      this.show_unplaced = true;
      this.active_key = "";
      this.loadImages();
    },
    stopEditing() {
      this.selected_name = this.draft.name;
      this.editing = false;
      this.draft = null;
    },
    dragStart(event, key) {
      // Firefox only starts a drag when data is set
      event.dataTransfer.setData("text/plain", key);
    },
    dropOnMap(event) {
      let key = event.dataTransfer.getData("text/plain");
      if (!this.editing || !this.device_map[key]) {
        return;
      }
      let rect = this.$refs.image.getBoundingClientRect();
      let clamp = (value) => Math.min(100, Math.max(0, value));
      this.setPlacement(
        key,
        clamp(((event.clientX - rect.left) / rect.width) * 100),
        clamp(((event.clientY - rect.top) / rect.height) * 100)
      );
    },
    dropOnList(event) {
      let key = event.dataTransfer.getData("text/plain");
      if (!this.editing || !this.draft.placements.some((x) => x.key == key)) {
        return;
      }
      this.draft.placements = this.draft.placements.filter((x) => x.key != key);
      this.saveDraft();
    },
    setPlacement(key, x, y) {
      let placement = { key: key, x: +x.toFixed(2), y: +y.toFixed(2) };
      this.draft.placements = this.draft.placements
        .filter((item) => item.key != key)
        .concat([placement]);
      this.saveDraft();
    },

    // Persistence
    saveMap: /* istanbul ignore next */ function (map) {
      let formData = new FormData();
      formData.append("data", JSON.stringify(map));
      return Helper.apiPost(
        "custom_dashboard",
        "",
        encodeURIComponent(map.name),
        this.$auth,
        formData
      );
    },
    saveDraft: /* istanbul ignore next */ async function () {
      try {
        if (this.draft.default) {
          // Only one map is the Home default
          for (let other of this.all_maps) {
            if (other.default && other.name != this.draft.name) {
              let copy = JSON.parse(JSON.stringify(other));
              delete copy._id;
              copy.default = false;
              await this.saveMap(copy);
            }
          }
        }
        await this.saveMap(this.draft);
        this.$emit("changed");
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    createMap: /* istanbul ignore next */ async function () {
      let map = {
        name: this.new_map_name.trim(),
        location: this.location,
        background_image: "",
        default: false,
        placements: [],
      };
      try {
        await this.saveMap(map);
        this.new_map_name = null;
        this.selected_name = map.name;
        this.$emit("changed");
        this.draft = map;
        this.draft_name = map.name;
        this.editing = true;
        this.show_unplaced = true;
        this.loadImages();
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    renameMap: /* istanbul ignore next */ async function () {
      let name = this.draft_name.trim();
      if (name == this.draft.name || this.nameProblem(name)) {
        return;
      }
      let old_name = this.draft.name;
      try {
        this.draft.name = name;
        await this.saveMap(this.draft);
        await Helper.apiDelete("custom_dashboard", old_name, this.$auth);
        this.selected_name = name;
        this.$emit("changed");
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    deleteMap: /* istanbul ignore next */ async function () {
      let ok = await this.$bvModal.msgBoxConfirm(
        "Delete the map '" + this.draft.name + "'? Devices are not affected."
      );
      if (!ok) {
        return;
      }
      try {
        await Helper.apiDelete("custom_dashboard", this.draft.name, this.$auth);
        this.editing = false;
        this.draft = null;
        this.selected_name = "";
        this.$emit("changed");
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    loadImages: /* istanbul ignore next */ async function () {
      try {
        this.images = await Helper.apiCall(
          "custom_dashboard_images",
          "",
          this.$auth
        );
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    uploadImage: /* istanbul ignore next */ async function (file) {
      let before = this.images.slice();
      let formData = new FormData();
      formData.append("file", file);
      try {
        await Helper.apiPost(
          "custom_dashboard_images",
          "",
          "",
          this.$auth,
          formData,
          true
        );
        await this.loadImages();
        // The server sanitises file names: the new entry is the upload, or
        // the same name when an existing image was replaced
        let added = this.images.filter((x) => before.indexOf(x) == -1);
        let uploaded = added.length == 1 ? added[0] : file.name;
        if (this.draft && this.images.indexOf(uploaded) != -1) {
          this.draft.background_image = uploaded;
          await this.saveDraft();
        }
      } catch (e) {
        this.$store.commit(
          "updateError",
          ("" + e).indexOf("484") != -1
            ? "Error: That file is not a valid image."
            : e
        );
      }
      this.upload = null;
    },
    deleteImage: /* istanbul ignore next */ async function (name) {
      let ok = await this.$bvModal.msgBoxConfirm(
        "Delete the image file '" +
          name +
          "'? Every map using it loses its floor plan."
      );
      if (!ok) {
        return;
      }
      try {
        await Helper.apiDelete("custom_dashboard_images", name, this.$auth);
        this.draft.background_image = "";
        await this.saveDraft();
        await this.loadImages();
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
  },
};
</script>
<style scoped>
.map-select {
  max-width: 20rem;
}
.edit-bar {
  background-color: #f4f6f8;
  border-radius: 0.5rem;
}
.map-area {
  position: relative;
  border: 1px solid #dee2e6;
  border-radius: 0.5rem;
  overflow: hidden;
  background-color: #fafafa;
}
.map-image {
  display: block;
  width: 100%;
  height: auto;
  user-select: none;
}
.map-links {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.link {
  stroke-width: 3;
  stroke: #adb5bd;
}
/* In-building copper is routine; keep it quiet next to fiber/wireless/VPN */
.link-ethernet {
  stroke-width: 1.5;
  opacity: 0.55;
}
.link-ethernet.link-down {
  opacity: 1;
}
.link-wireless,
.link-vpn {
  stroke-dasharray: 6 4;
}
.link-fiber {
  stroke-width: 4;
}
.link-up {
  stroke: #28a745;
}
.link-down {
  stroke: #dc3545;
}
.marker {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  z-index: 2;
}
.marker[draggable="true"] {
  cursor: move;
}
.marker-icon {
  position: relative;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  border: 2px solid white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}
.marker-label {
  margin-top: 2px;
  padding: 0 0.3rem;
  border-radius: 0.25rem;
  background-color: rgba(255, 255, 255, 0.85);
  font-size: 0.7rem;
  white-space: nowrap;
  max-width: 9rem;
  overflow: hidden;
  text-overflow: ellipsis;
}
.marker.active .marker-icon,
.chip.active {
  outline: 3px solid #007bff;
}
.guest-alert {
  position: absolute;
  top: -3px;
  right: -3px;
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  background-color: #dc3545;
  border: 1px solid white;
}
/* Status colours: markers fill, chips get a coloured edge */
.status-up .marker-icon,
.legend-dot.status-up {
  background-color: #28a745;
}
.status-down .marker-icon,
.status-error .marker-icon,
.legend-dot.status-down,
.legend-dot.status-error {
  background-color: #dc3545;
}
.status-down .marker-icon {
  animation: pulse 1.5s infinite;
}
.status-warning .marker-icon,
.legend-dot.status-warning {
  background-color: #fd7e14;
}
.status-unknown .marker-icon,
.legend-dot.status-unknown {
  background-color: #6c757d;
}
.status-none .marker-icon,
.legend-dot.status-none {
  background-color: #ced4da;
  color: #495057;
}
@keyframes pulse {
  50% {
    box-shadow: 0 0 0 6px rgba(220, 53, 69, 0.35);
  }
}
.unplaced {
  margin-top: 0.5rem;
  border-radius: 0.5rem;
}
.drop-zone {
  border: 2px dashed #adb5bd;
  padding: 0.25rem;
}
.unplaced-header {
  cursor: pointer;
  color: #6c757d;
  font-size: 0.9rem;
}
.group-title {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #6c757d;
  margin-top: 0.4rem;
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
  cursor: pointer;
  white-space: nowrap;
}
.chip[draggable="true"] {
  cursor: move;
}
.chip-ip {
  color: #6c757d;
  margin-left: 0.25rem;
}
.chip.status-up {
  border-left-color: #28a745;
}
.chip.status-down,
.chip.status-error {
  border-left-color: #dc3545;
  background-color: #fbe9eb;
}
.chip.status-warning {
  border-left-color: #fd7e14;
}
.chip.status-none {
  border-left-color: #ced4da;
}
.legend-dot {
  display: inline-block;
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  margin-right: 0.3rem;
}
.details {
  position: sticky;
  top: 0.5rem;
}
@media screen and (max-width: 576px) {
  .marker-icon {
    width: 1.4rem;
    height: 1.4rem;
    font-size: 0.7rem;
  }
  .marker-label {
    font-size: 0.6rem;
    max-width: 5rem;
  }
}
</style>
