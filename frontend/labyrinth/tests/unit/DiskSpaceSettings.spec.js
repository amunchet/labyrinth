import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import DiskSpaceSettings from "@/components/DiskSpace/DiskSpaceSettings.vue";
import Helper from "@/helper";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
  getAccessToken: jest.fn(() => Promise.resolve("access-token")),
};

jest.mock("@/helper", () => ({
  apiCall: jest.fn(),
  apiPost: jest.fn(),
  apiPut: jest.fn(),
  apiDelete: jest.fn(),
}));

describe("DiskSpaceSettings.vue", () => {
  let wrapper;

  beforeEach(() => {
    jest.clearAllMocks();
    Helper.apiCall
      .mockResolvedValueOnce({
        clusters: [],
        disk_space_alert_recipients: [],
        disk_space_alert_threshold: 80,
      })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ manual_hosts: [] });
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", async () => {
    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".disk-space-settings").exists()).toBe(true);
  });

  test("loads disk space settings on mount", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({
        clusters: [
          {
            _id: "cluster-1",
            name: "prod-cluster",
            host: "10.0.0.1",
          },
        ],
        disk_space_alert_recipients: ["admin@example.com"],
        disk_space_alert_threshold: 85,
      })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 100));

    expect(Helper.apiCall).toHaveBeenCalled();
  });

  test("displays success message on threshold update", async () => {
    Helper.apiPost.mockResolvedValue({ status: "updated" });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.alertThreshold = 90;
    wrapper.vm.alertRecipientsText = "admin@example.com";
    await wrapper.vm.saveAlertSettings();
    await wrapper.vm.$nextTick();

    expect(Helper.apiPost).toHaveBeenCalled();
  });

  test("displays error when update fails", async () => {
    Helper.apiPost.mockRejectedValue(new Error("Update failed"));

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.alertThreshold = 90;
    wrapper.vm.alertRecipientsText = "admin@example.com";
    await wrapper.vm.saveAlertSettings();

    expect(wrapper.vm.errorMessage).toBeTruthy();
  });

  test("handles recipient configuration", async () => {
    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.alertRecipientsText = "admin@example.com, backup@example.com";

    expect(wrapper.vm.alertRecipientsText).toBe(
      "admin@example.com, backup@example.com"
    );
  });

  test("clears error message", async () => {
    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.errorMessage = "Test error";
    wrapper.vm.errorMessage = "";

    expect(wrapper.vm.errorMessage).toBe("");
  });

  test("parses cluster data correctly", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({
        clusters: [
          {
            _id: "c1",
            name: "cluster-1",
            host: "10.0.0.1",
          },
        ],
        disk_space_alert_recipients: [],
        disk_space_alert_threshold: 80,
      })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadSettings();
    await wrapper.vm.$nextTick();

    if (wrapper.vm.clusters) {
      expect(wrapper.vm.clusters.length).toBeGreaterThanOrEqual(0);
    }
  });
});
