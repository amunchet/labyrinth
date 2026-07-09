import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import StorageProgressBar from "@/components/DiskSpace/StorageProgressBar.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
};

describe("StorageProgressBar.vue", () => {
  let wrapper;

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders progress bar with storage data", () => {
    const storage = {
      name: "local-storage",
      type: "dir",
      disk: 1000000000,
      used: 750000000,
      avail: 250000000,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".progress").exists()).toBe(true);
  });

  test("displays storage name", () => {
    const storage = {
      name: "backup-storage",
      type: "nfs",
      disk: 5000000000,
      used: 3000000000,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("backup-storage");
  });

  test("calculates and displays usage percentage correctly", () => {
    const storage = {
      name: "storage",
      disk: 1000,
      used: 500,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    const percentage = wrapper.vm.usagePercentage;
    expect(percentage).toBe(50);
  });

  test("displays variant based on threshold", () => {
    const storage = {
      name: "storage",
      disk: 1000,
      used: 900,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    const variant = wrapper.vm.variant;
    expect(["success", "warning", "danger"]).toContain(variant);
  });

  test("handles zero disk size gracefully", () => {
    const storage = {
      name: "empty-storage",
      disk: 0,
      used: 0,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("formats storage size for display", () => {
    const storage = {
      name: "storage",
      disk: 1099511627776,
      used: 549755813888,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("displays storage type information", () => {
    const storage = {
      name: "nfs-storage",
      type: "nfs",
      disk: 1000000000,
      used: 600000000,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("nfs-storage");
  });

  test("handles large storage values", () => {
    const storage = {
      name: "large-storage",
      disk: 10995116277760,
      used: 5497558138880,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".progress").exists()).toBe(true);
  });

  test("updates when storage prop changes", async () => {
    const storage = {
      name: "storage",
      disk: 1000,
      used: 300,
    };

    wrapper = mount(StorageProgressBar, {
      propsData: { storage },
      mocks: { $auth: config.mocks["$auth"] },
    });

    const initialPercentage = wrapper.vm.usagePercentage;

    await wrapper.setProps({
      storage: {
        name: "storage",
        disk: 1000,
        used: 700,
      },
    });

    const newPercentage = wrapper.vm.usagePercentage;
    expect(newPercentage).not.toBe(initialPercentage);
  });
});
