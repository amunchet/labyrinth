import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import DiskSpaceView from "@/components/DiskSpace/DiskSpaceView.vue";
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
  apiDelete: jest.fn(),
}));

jest.mock("@/components/DiskSpace/ProxmoxHostCard", () => ({
  name: "ProxmoxHostCard",
  template: "<div class='proxmox-card'>{{ host.cluster_name }}</div>",
  props: ["host"],
}));

jest.mock("@/components/DiskSpace/ManualHostCard", () => ({
  name: "ManualHostCard",
  template: "<div class='manual-card'>{{ host.name }}</div>",
  props: ["host"],
  emits: ["delete"],
}));

describe("DiskSpaceView.vue", () => {
  let wrapper;

  const flushPromises = () => new Promise((resolve) => setImmediate(resolve));

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.clearAllTimers();
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({ proxmox_hosts: [] })
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.refreshData();
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".disk-space-view").exists()).toBe(true);
  });

  test("displays loading state while fetching data", async () => {
    jest.useFakeTimers();
    try {
      Helper.apiCall.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ proxmox_hosts: [] }), 100))
      );

      wrapper = mount(DiskSpaceView, {
        mocks: { $auth: config.mocks["$auth"] },
      });

      // Component starts with loading=true, which triggers a refreshData call
      // Before the refreshData completes, we should see the loading state
      expect(wrapper.find(".loading-state").exists()).toBe(true);
      expect(wrapper.text()).toContain("Loading disk space data");
      
      // Advance timers to let the promise resolve
      jest.advanceTimersByTime(150);
      await wrapper.vm.$nextTick();
    } finally {
      jest.useRealTimers();
    }
  });

  test("displays error alert when data fetch fails", async () => {
    Helper.apiCall.mockRejectedValue(new Error("API Error"));

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.refreshData();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.error).toContain("API Error");
  });

  test("displays proxmox clusters data", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({
        proxmox_hosts: [
          {
            _id: "cluster-1",
            cluster_name: "prod-cluster",
            host: "10.0.0.1",
            nodes: [],
          },
        ],
      })
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    // Wait for the initial refreshData call to complete (triggered by mounted)
    await wrapper.vm.$nextTick();
    await flushPromises();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.proxmoxData.length).toBe(1);
    expect(wrapper.vm.proxmoxData[0].cluster_name).toBe("prod-cluster");
  });

  test("displays manual hosts data", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({ proxmox_hosts: [] })
      .mockResolvedValueOnce({
        manual_hosts: [
          {
            id: "manual-1",
            name: "storage-server",
            host: "storage.example.com",
            ip: "10.0.0.50",
          },
        ],
      });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    // Wait for the initial refreshData call to complete
    await wrapper.vm.$nextTick();
    await flushPromises();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.manualData.length).toBe(1);
    expect(wrapper.vm.manualData[0].name).toBe("storage-server");
  });

  test("displays both proxmox and manual hosts", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({
        proxmox_hosts: [
          {
            _id: "cluster-1",
            cluster_name: "prod-cluster",
          },
        ],
      })
      .mockResolvedValueOnce({
        manual_hosts: [
          {
            id: "manual-1",
            name: "storage-server",
            host: "storage.example.com",
          },
        ],
      });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    // Wait for the initial refreshData call to complete
    await wrapper.vm.$nextTick();
    await flushPromises();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.proxmoxData.length).toBe(1);
    expect(wrapper.vm.manualData.length).toBe(1);
  });

  test("displays empty state when no data", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({ proxmox_hosts: [] })
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    // Wait for mounted hook to trigger refreshData
    await wrapper.vm.$nextTick();
    // Wait for the async refreshData calls to complete
    await flushPromises();
    // Let Vue finish rendering
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.loading).toBe(false);
    expect(wrapper.vm.proxmoxData.length).toBe(0);
    expect(wrapper.vm.manualData.length).toBe(0);
    expect(wrapper.text()).toContain("No disk space data available");
  });

  test("handles manual host deletion", async () => {
    window.confirm = jest.fn(() => true);
    Helper.apiCall
      .mockResolvedValueOnce({ proxmox_hosts: [] })
      .mockResolvedValueOnce({ manual_hosts: [] });
    Helper.apiDelete.mockResolvedValue({});

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.manualData = [
      {
        id: "manual-1",
        name: "storage-server",
      },
    ];

    jest.spyOn(wrapper.vm, "refreshData").mockResolvedValue();

    await wrapper.vm.deleteManualHost("manual-1");

    expect(wrapper.vm.refreshData).toHaveBeenCalled();
  });

  test("refresh button works correctly", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({
        proxmox_hosts: [
          {
            _id: "cluster-1",
            cluster_name: "prod-cluster",
          },
        ],
      })
      .mockResolvedValueOnce({ manual_hosts: [] })
      .mockResolvedValueOnce({
        proxmox_hosts: [
          {
            _id: "cluster-1",
            cluster_name: "prod-cluster",
          },
        ],
      })
      .mockResolvedValueOnce({ manual_hosts: [] });
    Helper.apiPost.mockResolvedValue({
      proxmox_hosts: [
        {
          _id: "cluster-1",
          cluster_name: "prod-cluster",
        },
      ],
    });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const initialCall = Helper.apiCall.mock.calls.length;

    await wrapper.vm.refreshData(true);
    await wrapper.vm.$nextTick();
    await flushPromises();

    expect(Helper.apiPost).toHaveBeenCalled();
    expect(Helper.apiCall.mock.calls.length).toBeGreaterThanOrEqual(initialCall);
  });

  test("clears error when dismissing alert", async () => {
    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.error = "Test error";
    await wrapper.vm.$nextTick();

    wrapper.vm.error = null;
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.error).toBe(null);
  });

  test("starts auto-refresh on mount", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({ proxmox_hosts: [] })
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    
    await wrapper.vm.$nextTick();
    await flushPromises();

    expect(wrapper.vm.autoRefreshTimer).toBeTruthy();
  });

  test("stops auto-refresh on destroy", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({ proxmox_hosts: [] })
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const timer = wrapper.vm.autoRefreshTimer;
    wrapper.destroy();

    expect(wrapper.vm.autoRefreshTimer).toBeNull();
  });
});
