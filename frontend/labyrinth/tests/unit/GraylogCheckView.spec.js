import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import GraylogCheckView from "@/components/DiskSpace/GraylogCheckView.vue";
import Helper from "@/helper";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: { name: "Test User", email: "test@example.com" },
  getAccessToken: jest.fn(() => Promise.resolve("access-token")),
};

jest.mock("@/helper", () => ({
  apiCall: jest.fn(),
  apiPost: jest.fn(() => Promise.resolve("Success")),
}));

const guest = (id, name, check_status, extra = {}) => ({
  cluster_name: "home",
  node: "pv3",
  type: "lxc",
  id,
  name,
  status: check_status === "stopped" ? "stopped" : "running",
  labyrinth_matches: [],
  graylog_last_seen: null,
  graylog_fields: {},
  graylog_target: null,
  deferral: null,
  result_status: check_status,
  check_status,
  ...extra,
});

const payload = () => ({
  guests: [
    guest(100, "web01", "ok", {
      graylog_last_seen: "2026-10-07 12:00:00",
      graylog_fields: { ok: 1, status: "ok" },
      graylog_target: "graylog.lan:1514",
    }),
    guest(101, "db01", "failing", {
      graylog_last_seen: "2026-10-07 12:00:00",
      graylog_fields: { ok: 0, status: "rsyslog not running" },
    }),
    guest(102, "cache01", "not_deployed"),
    guest(103, "app01", "deferred", {
      result_status: "failing",
      deferral: {
        cluster_name: "home",
        id: 103,
        until: null,
        reason: "appliance",
      },
    }),
  ],
  errors: [],
  deferrals: [
    { cluster_name: "home", id: 103, until: null, reason: "appliance" },
    { cluster_name: "home", id: 999, until: "2000-01-01" },
  ],
  summary: { guest_count: 4, ok_count: 1, failing_count: 1 },
  settings: { metric_name: "check_graylog", stale_hours: 24 },
});

const flush = () => new Promise((resolve) => setTimeout(resolve));

const savedValue = (name) => {
  const call = Helper.apiPost.mock.calls.find((c) => c[4].get("name") === name);
  return JSON.parse(call[4].get("value"));
};

describe("GraylogCheckView.vue", () => {
  let wrapper;

  beforeEach(async () => {
    jest.clearAllMocks();
    Helper.apiCall.mockResolvedValue(payload());
    wrapper = mount(GraylogCheckView, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await flush();
  });

  afterEach(() => {
    wrapper.destroy();
  });

  test("shows only undeferred issues by default", () => {
    expect(Helper.apiCall).toHaveBeenCalledWith(
      "disk-space/proxmox",
      "graylog-check",
      config.mocks["$auth"]
    );
    expect(wrapper.vm.filteredGuests.map((g) => g.name)).toEqual([
      "db01",
      "cache01",
    ]);
    expect(wrapper.text()).toContain("rsyslog not running");

    wrapper.setData({ filter: "deferred" });
    expect(wrapper.vm.filteredGuests.map((g) => g.name)).toEqual(["app01"]);
  });

  test("deferring a guest saves it with an expiry and drops expired entries", async () => {
    const db01 = wrapper.vm.guests.find((g) => g.name === "db01");
    wrapper.vm.openDefer(db01);
    wrapper.setData({
      deferModal: { ...wrapper.vm.deferModal, days: 7, reason: " later " },
    });
    await wrapper.vm.saveDeferral();

    const saved = savedValue("proxmox_graylog_deferrals");
    expect(saved.map((d) => d.id)).toEqual([103, 101]);
    expect(saved[1].reason).toBe("later");
    expect(saved[1].until).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(Helper.apiCall).toHaveBeenCalledTimes(2);
  });

  test("permanent deferral has no expiry, and undefer removes it", async () => {
    const cache01 = wrapper.vm.guests.find((g) => g.name === "cache01");
    wrapper.vm.openDefer(cache01);
    wrapper.setData({ deferModal: { ...wrapper.vm.deferModal, days: null } });
    await wrapper.vm.saveDeferral();
    expect(savedValue("proxmox_graylog_deferrals")[1].until).toBeNull();

    Helper.apiPost.mockClear();
    const app01 = wrapper.vm.guests.find((g) => g.name === "app01");
    await wrapper.vm.removeDeferral(app01);
    expect(savedValue("proxmox_graylog_deferrals")).toEqual([]);
  });

  test("saves check settings with defaults for blank values", async () => {
    wrapper.setData({ settingsForm: { metric_name: " ", stale_hours: "" } });
    await wrapper.vm.saveSettings();
    expect(savedValue("proxmox_graylog_check")).toEqual({
      metric_name: "check_graylog",
      stale_hours: 24,
    });
  });
});
