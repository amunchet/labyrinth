import { config, shallowMount } from "@vue/test-utils";

import Vue from "vue";
import store from "@/store";
import Instance from "@/components/CustomDashboardsView.vue";

Vue.use(store);

config.mocks["$auth"] = {
  profile: {
    name: "Test Name",
    picture: "Test.jpg",
  },
  idToken: 1,
  login: function () {},
  getAccessToken: function () {},
};

let wrapper;

const device = (key, location) => ({ _live: { key, location } });

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    store,
    stubs: ["b-container", "b-select", "router-link", "LocationMap"],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("CustomDashboardsView.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });

  test("offers every map plus a board for locations without a map", async () => {
    wrapper.setData({
      maps: [
        { name: "Floor 1", location: "Plant" },
        { name: "Campus", location: "" },
      ],
      inventory: {
        locations: [{ name: "Plant" }, { name: "Warehouse" }],
        devices: [],
      },
    });
    expect(wrapper.vm.options).toStrictEqual([
      { value: "map:Floor 1", text: "Plant – Floor 1" },
      { value: "map:Campus", text: "Campus" },
      { value: "board:Warehouse", text: "Warehouse (board)" },
    ]);
  });

  test("defaults to the default map, then any map, then a board", async () => {
    wrapper.setData({
      inventory: { locations: [{ name: "Warehouse" }], devices: [] },
    });
    expect(wrapper.vm.choice).toStrictEqual({ map: "", location: "Warehouse" });

    wrapper.setData({ maps: [{ name: "Floor 1", location: "Plant" }] });
    expect(wrapper.vm.choice).toStrictEqual({
      map: "Floor 1",
      location: "Plant",
    });

    wrapper.setData({
      maps: [
        { name: "Floor 1", location: "Plant" },
        { name: "Floor 2", location: "Plant", default: true },
      ],
    });
    expect(wrapper.vm.choice.map).toBe("Floor 2");

    // An explicit choice wins, and a stale one (map deleted) falls back
    wrapper.setData({ selected: "board:Warehouse" });
    expect(wrapper.vm.choice.location).toBe("Warehouse");
    wrapper.setData({ selected: "map:Gone" });
    expect(wrapper.vm.choice.map).toBe("Floor 2");
  });

  test("shows the chosen location's devices; a location-less map gets all", async () => {
    let devices = [device("a", "Plant"), device("b", "Warehouse")];
    wrapper.setData({
      maps: [
        { name: "Floor 1", location: "Plant", default: true },
        { name: "Campus", location: "" },
      ],
      inventory: { locations: [], devices: devices },
    });
    expect(wrapper.vm.devices.map((x) => x._live.key)).toStrictEqual(["a"]);

    wrapper.setData({ selected: "map:Campus" });
    expect(wrapper.vm.devices).toHaveLength(2);
  });
});
