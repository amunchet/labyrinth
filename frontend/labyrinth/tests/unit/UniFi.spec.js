import { shallowMount } from "@vue/test-utils";
import Instance from "@/views/UniFi.vue";

jest.mock("@/helper", () => {
  const actual = jest.requireActual("@/helper").default;
  return {
    ...actual,
    apiCall: jest.fn(() => new Promise(() => {})),
    apiPost: jest.fn(() => new Promise(() => {})),
  };
});

const now = Date.now() / 1000;

const switch_ = {
  mac: "SW",
  name: "USW-Pro-48",
  type: "switch",
  state: "connected",
  offline: false,
  disabled: false,
  ports: [{ idx: 1, connected: [] }],
  uplink: { mac: "GW", name: "UDM Pro", port: 11, link_type: "fiber" },
};

const status = {
  controllers: [
    {
      _id: "1",
      name: "HQ console",
      fetched_at: now - 60,
      error: "",
      stale: false,
      sites: [
        {
          site: "default",
          name: "Default",
          location: "HQ",
          monitored: true,
          client_count: 12,
          devices: [
            switch_,
            {
              mac: "EDGE",
              name: "USW-Lite-8",
              state: "disconnected",
              offline: true,
              disabled: false,
              ports: [],
              uplink: null,
            },
            {
              mac: "UP",
              name: "U6-Pro",
              state: "upgrading",
              offline: false,
              disabled: false,
              ports: [],
              uplink: null,
            },
          ],
        },
      ],
      protect: {
        error: "",
        stale: false,
        cameras: [
          { name: "Front Door", state: "connected" },
          { name: "Back Lot", state: "disconnected" },
        ],
      },
    },
    {
      _id: "2",
      name: "Branch",
      fetched_at: now - 3 * 3600,
      error: "Could not connect",
      stale: true,
      sites: [],
      protect: null,
    },
  ],
  problems: [],
};

let wrapper;

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    mocks: {
      $auth: {},
      $store: { commit: jest.fn() },
      $router: { push: jest.fn() },
    },
    stubs: [
      "b-container",
      "b-card",
      "b-card-header",
      "b-tabs",
      "b-tab",
      "b-button",
      "b-spinner",
      "b-alert",
      "b-row",
      "b-col",
      "b-badge",
      "b-table",
      "b-link",
      "font-awesome-icon",
      "UnifiPorts",
      "UnifiSettings",
    ],
  });
  wrapper.setData({ status: status, loading: false });
});

afterEach(() => {
  wrapper.destroy();
});

describe("UniFi.vue", () => {
  test("counts devices and cameras, and which of them are offline", () => {
    expect(
      wrapper.vm.summary_cards.map((x) => [x.label, x.value, x.variant])
    ).toStrictEqual([
      ["Devices", 3, "primary"],
      ["Devices offline", 1, "danger"],
      ["Cameras", 2, "primary"],
      ["Cameras offline", 1, "danger"],
    ]);
    expect(wrapper.vm.cameras[0].controller).toBe("HQ console");
  });

  test("shows each device's state, and where it is plugged in", () => {
    let [sw, edge, ap] = status.controllers[0].sites[0].devices;
    expect([sw, edge, ap].map((x) => wrapper.vm.stateVariant(x))).toStrictEqual(
      ["success", "danger", "warning"]
    );
    expect(wrapper.vm.stateVariant({ ...edge, disabled: true })).toBe(
      "secondary"
    );
    expect(wrapper.vm.uplinkLabel(sw.uplink)).toBe("UDM Pro port 11 (fiber)");
    expect(wrapper.vm.uplinkLabel({ mac: "AA:BB", link_type: "" })).toBe(
      "AA:BB"
    );
    expect(wrapper.vm.uplinkLabel(null)).toBe("");
  });

  test("says how fresh each controller's data is", () => {
    let [hq, branch] = status.controllers;
    expect(wrapper.vm.controllerState(hq)).toBe("Checked 1m ago");
    expect(wrapper.vm.controllerState(branch)).toBe(
      "Not answering – showing results from 3h ago"
    );
    expect(wrapper.vm.controllerState({ fetched_at: null, error: "" })).toBe(
      "Not checked yet"
    );
    expect(
      wrapper.vm.controllerState({ fetched_at: null, error: "Timed out" })
    ).toBe("Never reached");
    expect(wrapper.vm.ago(now - 5 * 86400)).toBe("5d ago");
  });

  test("a switch's row opens its ports, and stays open across reloads", () => {
    let site = status.controllers[0].sites[0];
    wrapper.vm.toggle(switch_);
    expect(wrapper.vm.rowsOf(site).map((x) => x._showDetails)).toStrictEqual([
      true,
      false,
      false,
    ]);
    // Nothing to open on a device without ports
    wrapper.vm.toggle(site.devices[1]);
    expect(wrapper.vm.expanded).toStrictEqual(["SW"]);
    wrapper.vm.toggle(switch_);
    expect(wrapper.vm.expanded).toStrictEqual([]);
  });

  test("a device opens in Locations", () => {
    wrapper.vm.openDevice("SW");
    expect(wrapper.vm.$router.push).toHaveBeenCalledWith({
      path: "/locations",
      query: { device: "SW" },
    });
  });

  test("lists Protect errors only for controllers that answer", () => {
    expect(wrapper.vm.protect_errors).toStrictEqual([]);
    let broken = JSON.parse(JSON.stringify(status));
    broken.controllers[0].protect.error = "HTTP 502";
    wrapper.setData({ status: broken });
    expect(wrapper.vm.protect_errors.map((x) => x.name)).toStrictEqual([
      "HQ console",
    ]);
  });
});
