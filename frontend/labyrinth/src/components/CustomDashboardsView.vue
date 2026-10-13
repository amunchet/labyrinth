<template>
  <b-container fluid class="text-left">
    <div class="d-flex flex-wrap align-items-center mb-2">
      <b-select
        v-if="options.length"
        v-model="selected"
        :options="options"
        size="sm"
        class="board-select mr-2"
      />
      <router-link to="/locations" class="small">
        <font-awesome-icon icon="building" /> Manage locations &amp; maps
      </router-link>
    </div>
    <div v-if="!loaded" />
    <div v-else-if="!options.length" class="text-muted">
      No maps yet. Add your buildings under
      <router-link to="/locations">Locations</router-link> and upload a floor
      plan to see devices and their live status here.
    </div>
    <LocationMap
      v-else-if="choice"
      :all_maps="maps"
      :map_name="choice.map"
      :location="choice.location"
      :devices="devices"
      @edit-device="
        (device) => $router.push('/locations?device=' + device._live.key)
      "
    />
  </b-container>
</template>
<script>
import Helper from "@/helper";
import LocationMap from "@/components/LocationMap";

// Home wallboard: any map, or the automatic device board of a location that
// has no map yet, with live status
export default {
  name: "CustomDashboardsView",
  components: { LocationMap },
  data() {
    return {
      maps: [],
      inventory: { locations: [], devices: [] },
      selected: "",
      loaded: false,
      timeout: null,
    };
  },
  computed: {
    options() {
      let retval = this.maps.map((x) => ({
        value: "map:" + x.name,
        text: x.location ? x.location + " – " + x.name : x.name,
      }));
      this.inventory.locations
        .filter((x) => !this.maps.some((map) => map.location == x.name))
        .forEach((x) => {
          retval.push({ value: "board:" + x.name, text: x.name + " (board)" });
        });
      return retval;
    },
    choice() {
      let selected = this.options.some((x) => x.value == this.selected)
        ? this.selected
        : this.default_option;
      if (!selected) {
        return null;
      }
      if (selected.startsWith("map:")) {
        let map = this.maps.find((x) => "map:" + x.name == selected);
        return { map: map.name, location: map.location || "" };
      }
      return { map: "", location: selected.slice("board:".length) };
    },
    default_option() {
      let map = this.maps.find((x) => x.default) || this.maps[0];
      if (map) {
        return "map:" + map.name;
      }
      return this.options.length ? this.options[0].value : "";
    },
    devices() {
      // A map without a location may show devices from anywhere
      if (!this.choice.location) {
        return this.inventory.devices;
      }
      return this.inventory.devices.filter(
        (x) => x._live.location == this.choice.location
      );
    },
  },
  methods: {
    loadData: /* istanbul ignore next */ async function () {
      clearTimeout(this.timeout);
      try {
        let results = await Promise.all([
          Helper.apiCall("custom_dashboards", "", this.$auth),
          Helper.apiCall("inventory", "", this.$auth),
        ]);
        this.maps = results[0];
        this.inventory = results[1];
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      this.loaded = true;
      if (!this._isDestroyed) {
        this.timeout = setTimeout(() => this.loadData(), 10000);
      }
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.loadData();
  },
  destroyed: function () {
    clearTimeout(this.timeout);
  },
};
</script>
<style scoped>
.board-select {
  max-width: 24rem;
}
</style>
