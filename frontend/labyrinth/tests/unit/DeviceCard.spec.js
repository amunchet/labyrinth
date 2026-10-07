import { shallowMount } from "@vue/test-utils";
import Instance from "@/components/DeviceCard.vue";

const mount = (device, props = {}) =>
  shallowMount(Instance, {
    propsData: {
      device: {
        mac: "AA:BB",
        ip: "10.0.0.5",
        ...device,
        _live: {
          key: "AA:BB",
          type: "plc",
          status: "up",
          location: "Plant",
          location_source: "explicit",
          alive: null,
          services: null,
          proxmox: null,
          parent: "",
          ...device._live,
        },
      },
      ...props,
    },
    stubs: [
      "b-card",
      "b-card-header",
      "b-card-body",
      "b-badge",
      "b-button",
      "font-awesome-icon",
    ],
  });

describe("DeviceCard.vue", () => {
  test("describes the last reachability check", () => {
    let now = Date.now() / 1000;
    let wrapper = mount({
      _live: {
        alive: { up: false, method: "port", port: "80", checked: now - 30 },
      },
    });
    expect(wrapper.vm.reachability).toBe(
      "No answer to TCP port 80 check, 30s ago"
    );

    wrapper = mount({
      _live: { alive: { up: true, method: "ping", checked: now - 600 } },
    });
    expect(wrapper.vm.reachability).toBe("Answered ping, 10m ago");

    wrapper = mount({
      _live: {
        alive: {
          up: false,
          method: "port",
          port: "http",
          error: "Invalid check port: http",
          checked: now,
        },
      },
    });
    expect(wrapper.vm.reachability).toContain("– Invalid check port: http");
  });

  test("only shows a MAC when it is a real one, not an IP or generated key", () => {
    expect(mount({}).vm.real_mac).toBe(true);
    expect(mount({ mac: "10.0.0.5" }).vm.real_mac).toBe(false);
    expect(mount({ mac: "device-1a2b", ip: "" }).vm.real_mac).toBe(false);
  });

  test("summarises rack position, hardware and guests", () => {
    let wrapper = mount(
      {
        rack: "Rack A",
        rack_unit: 10,
        rack_height: 2,
        vendor: "Dell",
        serial: "XYZ",
      },
      {
        guests: [
          { _live: { status: "down" } },
          { _live: { status: "error" } },
          { _live: { status: "up" } },
        ],
      }
    );
    expect(wrapper.vm.units_label).toBe("U10–U11");
    expect(wrapper.vm.hardware).toBe("Dell · XYZ");
    expect(wrapper.vm.guest_problems).toBe(2);
    expect(wrapper.vm.type_label).toBe("PLC / controller");
    expect(wrapper.vm.status.label).toBe("Up");
  });
});
