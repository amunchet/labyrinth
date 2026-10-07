import { shallowMount } from "@vue/test-utils";
import Instance from "@/components/LocationMap.vue";
import Helper from "@/helper";

jest.mock("@/helper", () => {
  const actual = jest.requireActual("@/helper").default;
  return {
    ...actual,
    apiCall: jest.fn(() => Promise.resolve([])),
    apiPost: jest.fn(() => Promise.resolve("Success")),
    apiDelete: jest.fn(() => Promise.resolve("Success")),
  };
});

const device = (key, fields = {}, live = {}) => ({
  mac: key,
  ip: fields.ip || "",
  ...fields,
  _live: { key, type: "", status: "up", parent: "", ...live },
});

const floor = {
  name: "Floor 1",
  location: "Plant",
  background_image: "floor.png",
  placements: [
    { key: "SW", x: 10, y: 20 },
    { key: "GONE", x: 50, y: 50 },
  ],
};

let wrapper;

const mount = (props = {}) =>
  shallowMount(Instance, {
    propsData: { all_maps: [floor], location: "Plant", ...props },
    mocks: {
      $auth: { accessToken: "token" },
      $store: { commit: jest.fn() },
    },
    stubs: [
      "b-select",
      "b-badge",
      "b-button",
      "b-form",
      "b-input",
      "b-row",
      "b-col",
      "b-form-file",
      "b-form-checkbox",
      "font-awesome-icon",
      "DeviceCard",
    ],
  });

afterEach(() => {
  wrapper.destroy();
  jest.clearAllMocks();
});

describe("LocationMap.vue", () => {
  test("shows the location's maps, or one named map", () => {
    let other = { name: "Office", location: "Office", placements: [] };
    wrapper = mount({ all_maps: [floor, other] });
    expect(wrapper.vm.maps.map((x) => x.name)).toStrictEqual(["Floor 1"]);
    expect(wrapper.vm.map.name).toBe("Floor 1");

    wrapper.destroy();
    wrapper = mount({ all_maps: [floor, other], map_name: "Office" });
    expect(wrapper.vm.map.name).toBe("Office");
  });

  test("places devices by key; VMs/LXCs never show as unplaced on a floor plan", () => {
    wrapper = mount({
      devices: [
        device("SW", { host: "core-sw" }, { type: "switch" }),
        device("PC", {}, { type: "pc" }),
        device("VM", {}, { type: "vm" }),
      ],
    });
    expect(wrapper.vm.placed).toStrictEqual([
      { device: wrapper.vm.device_map.SW, x: 10, y: 20 },
    ]);
    expect(wrapper.vm.unplaced.map((x) => x._live.key)).toStrictEqual(["PC"]);
  });

  test("without a floor plan every device is on the board, grouped by type", () => {
    wrapper = mount({
      all_maps: [],
      devices: [
        device("X", {}, { type: "" }),
        device("PLC", {}, { type: "plc" }),
        device("SW", {}, { type: "switch" }),
        device("VM", {}, { type: "vm" }),
      ],
    });
    expect(wrapper.vm.has_image).toBe(false);
    expect(wrapper.vm.unplaced_groups.map((x) => x.label)).toStrictEqual([
      "Virtual machine",
      "Switch",
      "PLC / controller",
      "Type not set",
    ]);
  });

  test("converts maps from the old editor (pixel offsets by IP) once the image loads", () => {
    wrapper = mount({
      all_maps: [
        {
          name: "Old",
          location: "Plant",
          background_image: "floor.png",
          components: [{ name: "10.0.0.5", subnet: "10.0.0", x: 200, y: 50 }],
        },
      ],
      devices: [device("AA", { ip: "10.0.0.5", subnet: "10.0.0" })],
    });
    expect(wrapper.vm.placements).toStrictEqual([]);
    wrapper.vm.onImageLoad({
      target: { naturalWidth: 400, naturalHeight: 100 },
    });
    expect(wrapper.vm.placements).toStrictEqual([{ key: "AA", x: 50, y: 50 }]);
  });

  test("draws uplinks between placed devices, coloured by both ends", () => {
    let map = {
      name: "Campus",
      location: "Plant",
      background_image: "campus.png",
      placements: [
        { key: "A", x: 0, y: 0 },
        { key: "B", x: 100, y: 100 },
        { key: "C", x: 50, y: 50 },
      ],
    };
    wrapper = mount({
      all_maps: [map],
      devices: [
        device("A", { uplink: "B", link_type: "wireless" }),
        device("B"),
        device("C", { uplink: "A" }, { status: "down" }),
        device("D", { uplink: "A" }),
      ],
    });
    expect(wrapper.vm.links).toStrictEqual([
      {
        key: "A",
        x1: 0,
        y1: 0,
        x2: 100,
        y2: 100,
        type: "wireless",
        state: "up",
      },
      {
        key: "C",
        x1: 50,
        y1: 50,
        x2: 0,
        y2: 0,
        type: "ethernet",
        state: "down",
      },
    ]);
  });

  test("dropping on the floor plan places the device where it was dropped", async () => {
    wrapper = mount({ devices: [device("SW"), device("PC")] });
    wrapper.vm.startEditing();
    wrapper.vm.$refs.image = {
      getBoundingClientRect: () => ({
        left: 100,
        top: 50,
        width: 400,
        height: 200,
      }),
    };
    wrapper.vm.dropOnMap({
      dataTransfer: { getData: () => "PC" },
      clientX: 200,
      clientY: 250,
    });
    await wrapper.vm.$nextTick();

    let saved = JSON.parse(Helper.apiPost.mock.calls[0][4].get("data"));
    expect(Helper.apiPost.mock.calls[0][2]).toBe("Floor%201");
    expect(saved.placements).toStrictEqual([
      { key: "SW", x: 10, y: 20 },
      { key: "GONE", x: 50, y: 50 },
      { key: "PC", x: 25, y: 100 },
    ]);
    expect(saved._id).toBeUndefined();

    // Dragging a marker back onto the list removes it from the map
    wrapper.vm.dropOnList({ dataTransfer: { getData: () => "SW" } });
    await wrapper.vm.$nextTick();
    saved = JSON.parse(Helper.apiPost.mock.calls[1][4].get("data"));
    expect(saved.placements.map((x) => x.key)).toStrictEqual(["GONE", "PC"]);
  });

  test("map names must be unique and usable in a URL", () => {
    wrapper = mount();
    expect(wrapper.vm.nameProblem(" ")).toBe("A map needs a name");
    expect(wrapper.vm.nameProblem("A/B")).toBe("Map names cannot contain '/'");
    expect(wrapper.vm.nameProblem("Floor 1")).toBe(
      "A map with that name already exists"
    );
    expect(wrapper.vm.nameProblem("Floor 2")).toBe("");
  });

  test("a server's marker flags problems on its VMs/LXCs", () => {
    wrapper = mount({
      devices: [
        device("SRV"),
        device("VM1", {}, { parent: "SRV", status: "down" }),
        device("VM2", {}, { parent: "SRV", status: "up" }),
      ],
    });
    expect(wrapper.vm.guestProblems(wrapper.vm.device_map.SRV)).toBe(1);
  });
});
