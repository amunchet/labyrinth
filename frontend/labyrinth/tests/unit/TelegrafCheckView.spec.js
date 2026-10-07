import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import TelegrafCheckView from "@/components/DiskSpace/TelegrafCheckView.vue";
import Helper from "@/helper";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: { name: "Test User", email: "test@example.com" },
  getAccessToken: jest.fn(() => Promise.resolve("access-token")),
};

jest.mock("@/helper", () => ({
  apiCall: jest.fn(),
}));

const guest = (name, check_status, extra = {}) => ({
  cluster_name: "home",
  node: "pv3",
  type: "vm",
  id: name.length,
  name,
  status: check_status === "stopped" ? "stopped" : "running",
  labyrinth_matches: [],
  telegraf_last_seen: null,
  check_status,
  ...extra,
});

const flush = () => new Promise((resolve) => setTimeout(resolve));

describe("TelegrafCheckView.vue", () => {
  let wrapper;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.destroy();
  });

  test("loads the telegraf check and shows only issues by default", async () => {
    Helper.apiCall.mockResolvedValue({
      guests: [
        guest("web01", "ok", {
          labyrinth_matches: [{ ip: "10.0.0.10", host: "web01" }],
          telegraf_last_seen: "2026-10-07 12:00:00",
        }),
        guest("orphan", "unmatched"),
        guest("db01", "no_telegraf"),
        guest("template", "stopped"),
      ],
      errors: [],
      summary: {
        guest_count: 4,
        ok_count: 1,
        unmatched_count: 1,
        no_telegraf_count: 1,
        stopped_count: 1,
        stale_minutes: 15,
      },
    });

    wrapper = mount(TelegrafCheckView, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await flush();

    expect(Helper.apiCall).toHaveBeenCalledWith(
      "disk-space/proxmox",
      "telegraf-check",
      config.mocks["$auth"]
    );
    const names = wrapper.vm.filteredGuests.map((g) => g.name);
    expect(names).toEqual(["orphan", "db01"]);
    expect(wrapper.text()).toContain("No Labyrinth host");
    expect(wrapper.text()).toContain("No Telegraf");

    wrapper.setData({ filter: "all" });
    expect(wrapper.vm.filteredGuests.length).toBe(4);

    wrapper.setData({ filter: "ok" });
    expect(wrapper.vm.filteredGuests.map((g) => g.name)).toEqual(["web01"]);
  });

  test("surfaces cluster errors and request failures", async () => {
    Helper.apiCall.mockResolvedValueOnce(
      JSON.stringify({
        guests: [],
        errors: [
          { cluster_name: "broken", error: "Failed to get Proxmox data" },
        ],
        summary: { guest_count: 0, stale_minutes: 15 },
      })
    );
    wrapper = mount(TelegrafCheckView, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await flush();
    expect(wrapper.text()).toContain("broken: Failed to get Proxmox data");

    Helper.apiCall.mockRejectedValueOnce("Error 500: boom");
    await wrapper.vm.loadGuests();
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("Error 500: boom");
  });
});
