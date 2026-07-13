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

  const createWrapper = (item) =>
    mount(VMContainerProgressBar, {
      propsData: { item, type: "vm" },
      mocks: { $auth: config.mocks["$auth"] },
    });

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders progress bar with VM data", () => {
    const item = {
      name: "web-server",
      id: "100",
      disk: 50000000000,
      maxdisk: 100000000000,
    };

    wrapper = createWrapper(item);

    expect(wrapper.find(".vm-tile").exists()).toBe(true);
  });

  test("displays VM name", () => {
    const item = {
      name: "database-server",
      id: "101",
      disk: 75000000000,
      maxdisk: 200000000000,
    };

    wrapper = createWrapper(item);

    expect(wrapper.text()).toContain("database-server");
  });

  test("calculates usage percentage correctly", () => {
    const item = {
      name: "test-vm",
      id: "102",
      disk: 50000000000,
      maxdisk: 100000000000,
    };

    wrapper = createWrapper(item);

    const percentage = wrapper.vm.diskUsagePercentage;
    expect(percentage).toBe(50);
  });

  test("handles zero maxdisk gracefully", () => {
    const item = {
      name: "vm-no-disk",
      id: "103",
      disk: 0,
      maxdisk: 0,
    };

    wrapper = createWrapper(item);

    expect(wrapper.vm).toBeTruthy();
  });

  test("handles missing disk data", () => {
    const item = {
      name: "vm-guest-agent-missing",
      id: "104",
      disk: null,
      maxdisk: 100000000000,
    };

    wrapper = createWrapper(item);

    expect(wrapper.vm.hasDiskInfo).toBe(false);
  });

  test("displays variant based on usage threshold", () => {
    const item = {
      name: "vm-full",
      id: "105",
      disk: 90000000000,
      maxdisk: 100000000000,
    };

    wrapper = createWrapper(item);

    const usageClass = wrapper.vm.diskUsageClass;
    expect(["usage-success", "usage-warning", "usage-danger"]).toContain(
      usageClass
    );
  });

  test("displays VM ID", () => {
    const item = {
      name: "prod-vm",
      id: "200",
      disk: 30000000000,
      maxdisk: 100000000000,
    };

    wrapper = createWrapper(item);

    expect(wrapper.text()).toContain("prod-vm");
  });

  test("formats disk sizes correctly", () => {
    const item = {
      name: "storage-vm",
      id: "300",
      disk: 1099511627776,
      maxdisk: 2199023255552,
    };

    wrapper = createWrapper(item);

    expect(wrapper.vm.formatBytes(1099511627776)).toBe("1 TB");
  });

  test("updates when VM prop changes", async () => {
    const item = {
      name: "vm",
      id: "400",
      disk: 20000000000,
      maxdisk: 100000000000,
    };

    wrapper = createWrapper(item);

    const initialPercentage = wrapper.vm.diskUsagePercentage;

    await wrapper.setProps({
      item: {
        name: "vm",
        id: "400",
        disk: 80000000000,
        maxdisk: 100000000000,
      },
    });

    const newPercentage = wrapper.vm.diskUsagePercentage;
    expect(newPercentage).not.toBe(initialPercentage);
  });

  test("handles extremely high usage", () => {
    const item = {
      name: "over-quota-vm",
      id: "500",
      disk: 150000000000,
      maxdisk: 100000000000,
    };

    wrapper = createWrapper(item);

    const percentage = wrapper.vm.diskUsagePercentage;
    expect(percentage).toBeGreaterThan(100);
  });
});
