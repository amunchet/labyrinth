import { shallowMount } from "@vue/test-utils";
import Instance from "@/components/UnifiPorts.vue";

const ports = [
  {
    idx: 1,
    name: "Port 1",
    up: true,
    enabled: true,
    speed: 1000,
    media: "GE",
    poe: 6.5,
    connected: [{ mac: "AA", name: "pve1", key: "10.0.0.10", active: true }],
  },
  {
    idx: 2,
    name: "Port 2",
    up: false,
    enabled: true,
    speed: null,
    connected: [],
  },
  { idx: 3, name: "Port 3", up: false, enabled: false, connected: [] },
  {
    idx: 25,
    name: "SFP+ 1",
    up: true,
    enabled: true,
    speed: 10000,
    media: "SFP+",
    connected: [{ mac: "GW", name: "", ip: "10.0.0.1", upstream: true }],
  },
];

const mount = () =>
  shallowMount(Instance, {
    propsData: { ports },
    stubs: ["b-link", "font-awesome-icon"],
  });

describe("UnifiPorts.vue", () => {
  test("colours ports by link state and lists only the ports in use", () => {
    let wrapper = mount();
    expect(ports.map((x) => wrapper.vm.portState(x))).toStrictEqual([
      "up",
      "down",
      "disabled",
      "up",
    ]);
    expect(wrapper.vm.in_use.map((x) => x.idx)).toStrictEqual([1, 25]);
    expect(wrapper.findAll(".port")).toHaveLength(4);
    expect(wrapper.findAll(".port-list tr")).toHaveLength(2);
  });

  test("labels speeds and describes each port on hover", () => {
    let wrapper = mount();
    expect(ports.map((x) => wrapper.vm.portSpeed(x))).toStrictEqual([
      "1G",
      "",
      "",
      "10G",
    ]);
    expect(wrapper.vm.portSpeed({ speed: 100 })).toBe("100M");
    expect(wrapper.vm.portTitle(ports[0])).toBe(
      "Port 1 – up 1G GE\nPoE 6.5 W\npve1"
    );
    expect(wrapper.vm.portTitle(ports[2])).toBe("Port 3 – disabled");
    // Unnamed devices show their IP
    expect(wrapper.vm.portTitle(ports[3])).toBe(
      "SFP+ 1 – up 10G SFP+\n10.0.0.1"
    );
  });
});
