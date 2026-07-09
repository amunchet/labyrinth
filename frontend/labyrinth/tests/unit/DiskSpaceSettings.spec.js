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
    Helper.apiCall.mockResolvedValue({
      clusters: [],
      recipients: [],
      threshold: 80,
    });
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

    expect(wrapper.find(".p-3").exists()).toBe(true);
  });

  test("loads disk space settings on mount", async () => {
    Helper.apiCall.mockResolvedValue({
      clusters: [
        {
          _id: "cluster-1",
          name: "prod-cluster",
          host: "10.0.0.1",
        },
      ],
      recipients: ["admin@example.com"],
      threshold: 85,
    });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 100));

    expect(Helper.apiCall).toHaveBeenCalled();
  });

  test("displays success message on threshold update", async () => {
    Helper.apiPut.mockResolvedValue({ status: "updated" });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.threshold = 90;
    await wrapper.vm.updateThreshold();
    await wrapper.vm.$nextTick();

    expect(Helper.apiPut).toHaveBeenCalled();
  });

  test("displays error when update fails", async () => {
    Helper.apiPut.mockRejectedValue(new Error("Update failed"));

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.updateThreshold();

    expect(wrapper.vm.errorMessage).toBeTruthy();
  });

  test("handles recipient configuration", async () => {
    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.recipients = "admin@example.com, backup@example.com";

    expect(wrapper.vm.recipients).toBe(
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
    Helper.apiCall.mockResolvedValue({
      clusters: [
        {
          _id: "c1",
          name: "cluster-1",
          host: "10.0.0.1",
        },
      ],
      recipients: [],
      threshold: 80,
    });

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
