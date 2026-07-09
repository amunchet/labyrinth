import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import ProxmoxHostCard from "@/components/DiskSpace/ProxmoxHostCard.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
};

describe("ProxmoxHostCard.vue", () => {
  let wrapper;

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component with host data", () => {
    const hostData = {
      _id: "cluster-1",
      cluster_name: "prod-cluster",
      host: "10.0.0.1",
      nodes: [
        {
          name: "node-1",
          storage: [
            {
              name: "local",
              type: "dir",
              disk: 1000000,
              used: 800000,
              avail: 200000,
            },
          ],
        },
      ],
      vms: [
        {
          name: "vm-1",
          vmid: "100",
          disk: 100000,
          maxdisk: 100000,
        },
      ],
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".proxmox-host-card").exists()).toBe(true);
  });

  test("displays cluster information", () => {
    const hostData = {
      cluster_name: "test-cluster",
      host: "192.168.1.1",
      nodes: [],
      vms: [],
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("test-cluster");
  });

  test("displays nodes information", () => {
    const hostData = {
      cluster_name: "cluster",
      host: "10.0.0.1",
      nodes: [
        {
          name: "pve-node-1",
          status: "online",
          storage: [],
        },
      ],
      vms: [],
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("pve-node-1");
  });

  test("displays storage information", () => {
    const hostData = {
      cluster_name: "cluster",
      host: "10.0.0.1",
      nodes: [
        {
          name: "node-1",
          storage: [
            {
              name: "local-storage",
              type: "dir",
              disk: 1000000,
              used: 700000,
              avail: 300000,
            },
          ],
        },
      ],
      vms: [],
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("local-storage");
  });

  test("displays VM information", () => {
    const hostData = {
      cluster_name: "cluster",
      host: "10.0.0.1",
      nodes: [],
      vms: [
        {
          name: "web-server",
          vmid: "101",
          disk: 50000,
          maxdisk: 100000,
        },
      ],
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("web-server");
  });

  test("handles missing optional data gracefully", () => {
    const hostData = {
      cluster_name: "cluster",
      host: "10.0.0.1",
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".proxmox-host-card").exists()).toBe(true);
  });

  test("renders empty state for empty nodes array", () => {
    const hostData = {
      cluster_name: "cluster",
      host: "10.0.0.1",
      nodes: [],
      vms: [],
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("renders with complex nested data", () => {
    const hostData = {
      cluster_name: "production",
      host: "10.10.10.1",
      nodes: [
        {
          name: "pve1",
          status: "online",
          storage: [
            { name: "storage1", type: "dir", disk: 5000000, used: 4000000 },
            { name: "storage2", type: "nfs", disk: 10000000, used: 8000000 },
          ],
        },
        {
          name: "pve2",
          status: "online",
          storage: [
            { name: "storage1", type: "dir", disk: 5000000, used: 3000000 },
          ],
        },
      ],
      vms: [
        { name: "vm1", vmid: "100", disk: 50000, maxdisk: 100000 },
        { name: "vm2", vmid: "101", disk: 75000, maxdisk: 150000 },
        { name: "vm3", vmid: "102", disk: 0, maxdisk: 200000 },
      ],
    };

    wrapper = mount(ProxmoxHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".proxmox-host-card").exists()).toBe(true);
    expect(wrapper.text()).toContain("production");
  });
});
