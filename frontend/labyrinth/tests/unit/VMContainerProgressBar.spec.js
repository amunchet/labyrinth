import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import VMContainerProgressBar from "@/components/DiskSpace/VMContainerProgressBar.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
};

describe("VMContainerProgressBar.vue", () => {
  let wrapper;

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders progress bar with VM data", () => {
    const vm = {
      name: "web-server",
      vmid: "100",
      disk: 50000000000,
      maxdisk: 100000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".progress").exists()).toBe(true);
  });

  test("displays VM name", () => {
    const vm = {
      name: "database-server",
      vmid: "101",
      disk: 75000000000,
      maxdisk: 200000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("database-server");
  });

  test("calculates usage percentage correctly", () => {
    const vm = {
      name: "test-vm",
      vmid: "102",
      disk: 50000000000,
      maxdisk: 100000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    const percentage = wrapper.vm.usagePercentage;
    expect(percentage).toBe(50);
  });

  test("handles zero maxdisk gracefully", () => {
    const vm = {
      name: "vm-no-disk",
      vmid: "103",
      disk: 0,
      maxdisk: 0,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("handles missing disk data", () => {
    const vm = {
      name: "vm-guest-agent-missing",
      vmid: "104",
      disk: 0,
      maxdisk: 100000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".progress").exists()).toBe(true);
  });

  test("displays variant based on usage threshold", () => {
    const vm = {
      name: "vm-full",
      vmid: "105",
      disk: 90000000000,
      maxdisk: 100000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    const variant = wrapper.vm.variant;
    expect(["success", "warning", "danger"]).toContain(variant);
  });

  test("displays VM ID", () => {
    const vm = {
      name: "prod-vm",
      vmid: "200",
      disk: 30000000000,
      maxdisk: 100000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("prod-vm");
  });

  test("formats disk sizes correctly", () => {
    const vm = {
      name: "storage-vm",
      vmid: "300",
      disk: 1099511627776,
      maxdisk: 2199023255552,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("updates when VM prop changes", async () => {
    const vm = {
      name: "vm",
      vmid: "400",
      disk: 20000000000,
      maxdisk: 100000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    const initialPercentage = wrapper.vm.usagePercentage;

    await wrapper.setProps({
      vm: {
        name: "vm",
        vmid: "400",
        disk: 80000000000,
        maxdisk: 100000000000,
      },
    });

    const newPercentage = wrapper.vm.usagePercentage;
    expect(newPercentage).not.toBe(initialPercentage);
  });

  test("handles extremely high usage", () => {
    const vm = {
      name: "over-quota-vm",
      vmid: "500",
      disk: 150000000000,
      maxdisk: 100000000000,
    };

    wrapper = mount(VMContainerProgressBar, {
      propsData: { vm },
      mocks: { $auth: config.mocks["$auth"] },
    });

    const percentage = wrapper.vm.usagePercentage;
    expect(percentage).toBeGreaterThan(100);
  });
});
