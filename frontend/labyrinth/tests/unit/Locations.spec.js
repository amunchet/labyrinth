import { shallowMount } from "@vue/test-utils";
import Instance from "@/views/Locations.vue";
import Helper from "@/helper";

jest.mock("@/helper", () => {
  const actual = jest.requireActual("@/helper").default;
  return {
    ...actual,
    apiCall: jest.fn(() => new Promise(() => {})),
    apiPost: jest.fn(() => Promise.resolve("Success")),
    apiDelete: jest.fn(() => Promise.resolve("Success")),
  };
});

const device = (key, fields = {}, live = {}) => ({
  mac: key,
  ip: "",
  ...fields,
  _live: {
    key,
    type: "",
    status: "up",
    parent: "",
    location: "Plant",
    location_source: "explicit",
    ...live,
  },
});

const plant = {
  _id: "1",
  name: "Plant",
  racks: [
    { name: "Rack A", units: 10 },
    { name: "Rack B", units: 42 },
  ],
};

let wrapper;

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    mocks: {
      $auth: {},
      $store: { commit: jest.fn() },
      $bvModal: { show: jest.fn(), hide: jest.fn() },
    },
    stubs: [
      "b-container",
      "b-modal",
      "b-form-group",
      "b-input",
      "b-textarea",
      "b-row",
      "b-col",
      "b-input-group",
      "b-button",
      "b-nav",
      "b-nav-item",
      "b-badge",
      "b-spinner",
      "b-alert",
      "b-tabs",
      "b-tab",
      "b-link",
      "b-card",
      "b-card-header",
      "b-table",
      "b-select",
      "b-pagination",
      "font-awesome-icon",
      "CreateEditHost",
      "DeviceCard",
      "LocationMap",
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
  jest.clearAllMocks();
});

const setInventory = (devices, proxmox = []) =>
  wrapper.setData({
    selected: "Plant",
    inventory: { locations: [plant], devices: devices, proxmox: proxmox },
  });

describe("Locations.vue", () => {
  test("devices are grouped by effective location, with problem counts", () => {
    setInventory([
      device("A", {}, { status: "down" }),
      device("B", {}, { status: "error" }),
      device("C", {}, { status: "warning" }),
      device("D", {}, { location: "" }),
    ]);
    expect(wrapper.vm.devices_here.map((x) => x._live.key)).toStrictEqual([
      "A",
      "B",
      "C",
    ]);
    expect(wrapper.vm.problemCount("Plant")).toBe(2);
    expect(wrapper.vm.devicesAt("").map((x) => x._live.key)).toStrictEqual([
      "D",
    ]);
  });

  test("rack layouts place devices by U from the top, and flag overlaps", () => {
    setInventory([
      device("SRV", { rack: "Rack A", rack_unit: 1, rack_height: 2 }),
      device("SW", { rack: "Rack A", rack_unit: 10 }),
      device("UPS", { rack: "Rack A", rack_unit: 2 }),
      device("TALL", { rack: "Rack B", rack_unit: 41, rack_height: 4 }),
    ]);
    let [rack_a, rack_b] = wrapper.vm.rack_layouts;
    expect(rack_a.slots[0]).toBe(10);
    expect(rack_a.slots).toHaveLength(10);

    let items = {};
    rack_a.devices.forEach((x) => (items[x.device._live.key] = x));
    // A 2U device at U1 fills the bottom two rows of a 10U rack
    expect([items.SRV.row, items.SRV.height]).toStrictEqual([9, 2]);
    expect([items.SW.row, items.SW.height]).toStrictEqual([1, 1]);
    expect(items.SRV.overlaps).toBe(true);
    expect(items.UPS.overlaps).toBe(true);
    expect(items.SW.overlaps).toBe(false);

    // Taller than the space left: clipped at the top of the rack
    expect([rack_b.devices[0].row, rack_b.devices[0].height]).toStrictEqual([
      1, 2,
    ]);
  });

  test("devices not in one of this location's racks can be racked; VMs cannot", () => {
    setInventory([
      device("SRV", { rack: "Rack A", rack_unit: 1 }),
      device("OLD", { rack: "Removed rack", rack_unit: 3 }),
      device("NOU", { rack: "Rack A" }),
      device("PC"),
      device("VM", {}, { type: "vm" }),
    ]);
    expect(wrapper.vm.unracked.map((x) => x._live.key)).toStrictEqual([
      "OLD",
      "NOU",
      "PC",
    ]);
  });

  test("dropping on a rack slot makes it the device's top U, inside the rack", () => {
    setInventory([
      device("SW"),
      device("SRV", { rack_height: 2 }),
      device("BIG", { rack_height: 4 }),
    ]);
    let rack = wrapper.vm.rack_layouts[0];
    let drop = (key, u) =>
      wrapper.vm.dropOnRack({ dataTransfer: { getData: () => key } }, rack, u);
    let posted = () =>
      Helper.apiPost.mock.calls.map((x) => [
        x[2],
        JSON.parse(x[4].get("data")).rack_unit,
      ]);

    drop("SW", 5);
    drop("SRV", 5);
    drop("SRV", 1);
    drop("BIG", 10);
    drop("NOBODY", 3);
    // toEqual: mock.calls.map() builds its array in jest-mock's realm
    expect(posted()).toEqual([
      ["SW/inventory", 5],
      ["SRV/inventory", 4],
      ["SRV/inventory", 1],
      ["BIG/inventory", 7],
    ]);
    expect(
      JSON.parse(Helper.apiPost.mock.calls[0][4].get("data"))
    ).toStrictEqual({ location: "Plant", rack: "Rack A", rack_unit: 5 });
  });

  test("the location form is checked before saving", () => {
    wrapper.setData({
      inventory: { locations: [plant], devices: [], proxmox: [] },
    });
    let check = (form) => {
      wrapper.setData({
        form: { _id: "", name: "", address: "", notes: "", racks: [], ...form },
      });
      return wrapper.vm.form_problem;
    };
    expect(check({ name: "" })).toBe("A location needs a name.");
    expect(check({ name: "A/B" })).toBe("Location names cannot contain '/'.");
    expect(check({ name: "plant" })).toBe(
      "Another location is already called Plant."
    );
    expect(check({ _id: "1", name: "PLANT" })).toBe("");
    expect(check({ name: "Office", racks: [{ name: "", units: 42 }] })).toBe(
      "Every rack needs a name."
    );
    expect(
      check({
        name: "Office",
        racks: [
          { name: "R1", units: 42 },
          { name: "R1", units: 42 },
        ],
      })
    ).toBe("Rack names must be unique.");
    expect(check({ name: "Office", racks: [{ name: "R1", units: 61 }] })).toBe(
      "Racks are 1 to 60 units tall."
    );
    expect(check({ name: "Office", racks: [{ name: "R1", units: 42 }] })).toBe(
      ""
    );
  });

  test("editing a location remembers rack names so renames keep devices", () => {
    wrapper.vm.editLocation(plant);
    expect(wrapper.vm.form.racks[0]).toStrictEqual({
      name: "Rack A",
      units: 10,
      previous_name: "Rack A",
    });
    expect(wrapper.vm.$bvModal.show).toHaveBeenCalledWith("location_form");
  });

  test("the device list filters by text and type", () => {
    setInventory([
      device("A", { host: "core-sw", ip: "10.0.0.1" }, { type: "switch" }),
      device("B", { host: "gate", model: "S7-1200" }, { type: "plc" }),
      device("C", { host: "pc-12", uplink: "A", link_type: "ethernet" }),
    ]);
    wrapper.setData({ filter: "s7" });
    expect(wrapper.vm.device_rows.map((x) => x.name)).toStrictEqual(["gate"]);
    wrapper.setData({ filter: "", type_filter: "switch" });
    expect(wrapper.vm.device_rows.map((x) => x.name)).toStrictEqual([
      "core-sw",
    ]);
    wrapper.setData({ type_filter: "" });
    expect(wrapper.vm.device_rows[2].uplink).toBe("core-sw (ethernet)");
  });

  test("selecting a Proxmox server shows its node's guests", () => {
    let node = { name: "pve1", host_key: "SRV", guests: [] };
    setInventory([device("SRV")], [{ cluster: "prod", nodes: [node] }]);
    wrapper.setData({ rack_key: "SRV" });
    expect(wrapper.vm.rack_node).toStrictEqual(node);
    wrapper.setData({ rack_key: "OTHER" });
    expect(wrapper.vm.rack_node).toBe(null);
  });

  test("device rows show the rack and, when known, the rack unit", () => {
    setInventory([
      device("A", { rack: "Rack A", rack_unit: 4 }),
      device("B", { rack: "Rack B" }),
      device("C"),
    ]);
    expect(wrapper.vm.device_rows.map((x) => x.rack)).toStrictEqual([
      "Rack A U4",
      "Rack B",
      "",
    ]);
  });

  test("racked and unracked devices can be picked with the keyboard", async () => {
    setInventory([
      device("SRV", { rack: "Rack A", rack_unit: 2 }),
      device("PC"),
    ]);
    await wrapper.setData({ loading: false });
    await wrapper.find(".rack-device").trigger("keydown.enter");
    expect(wrapper.vm.rack_key).toBe("SRV");
    await wrapper.find(".unracked .chip").trigger("keydown.space");
    expect(wrapper.vm.rack_key).toBe("PC");
  });

  test("devices UniFi sees cabled to a racked switch are suggested for its rack", () => {
    let ports = [
      { idx: 1, connected: [{ mac: "SRV" }] },
      { idx: 2, connected: [{ mac: "HV" }, { mac: "VM" }] },
      { idx: 3, connected: [{ mac: "NAS" }, { mac: "NAS-2" }] },
      { idx: 25, connected: [{ mac: "GW", upstream: true }] },
    ];
    let on = (key, port, extra = {}) => ({
      unifi: { uplink: { key: key, port: port, wireless: false, ...extra } },
    });
    setInventory([
      device("SW", { rack: "Rack A", rack_unit: 5 }, { unifi: { ports } }),
      device("SRV", {}, on("SW", 1)),
      device("HV", {}, on("SW", 2)),
      device("NAS", { rack_height: 2 }, { type: "storage", ...on("SW", 3) }),
      device("PHONE", {}, { type: "phone", ...on("SW", 4) }),
      device("LAPTOP", {}, on("SW", null, { wireless: true })),
      device("FAR", {}, on("ELSEWHERE", 1)),
      // UniFi's own switches are left to place by hand
      device(
        "SW2",
        {},
        { type: "switch", unifi: { ...on("SW", 24).unifi, kind: "device" } }
      ),
    ]);
    // The nearest free slot below the switch: SRV takes U4, so the 2U NAS
    // goes to U2-3 rather than above the switch
    expect(
      wrapper.vm.rack_suggestions.map((x) => [
        x.device._live.key,
        x.rack,
        x.unit,
        x.port,
      ])
    ).toStrictEqual([
      ["SRV", "Rack A", 4, 1],
      ["NAS", "Rack A", 2, 3],
    ]);
    expect(wrapper.vm.rack_suggestions[0].switch_name).toBe("SW");
  });

  test("slots above the switch are used once below is full, and a full rack suggests nothing", () => {
    let near = { bottom: 5, top: 5 };
    expect(wrapper.vm.freeUnit(new Set([4, 5]), 7, 1, near)).toBe(3);
    expect(wrapper.vm.freeUnit(new Set([1, 2, 3, 4, 5]), 7, 1, near)).toBe(6);
    let taken = new Set([1, 2, 3, 5]);
    expect(wrapper.vm.freeUnit(taken, 5, 1, near)).toBe(4);
    expect(wrapper.vm.freeUnit(taken, 5, 2, near)).toBe(null);
  });

  test("the device list shows the switch port UniFi sees a device on", () => {
    setInventory([
      device("SW", { host: "core-sw" }),
      device(
        "SRV",
        {},
        {
          uplink: "SW",
          link_type: "ethernet",
          unifi: { uplink: { key: "SW", name: "USW-48", port: 7 } },
        }
      ),
      device(
        "PC",
        {},
        {
          uplink: "",
          link_type: "",
          unifi: { uplink: { key: "", name: "USW-Lite-8", port: 3 } },
        }
      ),
    ]);
    expect(wrapper.vm.device_rows.map((x) => x.uplink)).toStrictEqual([
      "",
      "core-sw port 7 (ethernet)",
      "USW-Lite-8 port 3",
    ]);
  });

  test("new devices start at the current location", () => {
    wrapper.setData({ selected: "Plant" });
    wrapper.vm.addDevice();
    expect(wrapper.vm.selected_host.location).toBe("Plant");
    expect(wrapper.vm.selected_host.mac).toBe("");
    expect(wrapper.vm.$bvModal.show).toHaveBeenCalledWith("create_edit_host");
  });
});
