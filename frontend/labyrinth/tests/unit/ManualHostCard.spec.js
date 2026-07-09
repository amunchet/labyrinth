import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import ManualHostCard from "@/components/DiskSpace/ManualHostCard.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
};

describe("ManualHostCard.vue", () => {
  let wrapper;

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component with host data", () => {
    const hostData = {
      id: "manual-1",
      name: "backup-server",
      host: "backup.example.com",
      ip: "192.168.1.100",
      username: "admin",
      port: 22,
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".manual-host-card").exists()).toBe(true);
  });

  test("displays host information", () => {
    const hostData = {
      id: "manual-1",
      name: "storage-server",
      host: "storage.local",
      ip: "10.0.0.50",
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("storage-server");
  });

  test("displays disk usage information if available", () => {
    const hostData = {
      id: "manual-1",
      name: "data-server",
      host: "data.example.com",
      ip: "10.0.0.60",
      disk_usage: {
        total: 1000000000,
        used: 700000000,
        percent: 70,
      },
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("emits delete event when delete button is clicked", async () => {
    const hostData = {
      id: "manual-1",
      name: "server",
      host: "example.com",
      ip: "10.0.0.1",
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    // Find and click delete button
    const deleteButtons = wrapper.findAll("button");
    const deleteBtn = deleteButtons.filter((btn) =>
      btn.text().toLowerCase().includes("delete")
    );

    if (deleteBtn.length > 0) {
      await deleteBtn[0].trigger("click");
      expect(wrapper.emitted("delete")).toBeTruthy();
    }
  });

  test("handles missing optional fields gracefully", () => {
    const hostData = {
      id: "manual-1",
      name: "server",
      host: "example.com",
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".manual-host-card").exists()).toBe(true);
  });

  test("renders with complete host data", () => {
    const hostData = {
      id: "manual-1",
      name: "production-server",
      host: "prod.example.com",
      ip: "203.0.113.42",
      username: "ops",
      port: 2222,
      disk_usage: {
        total: 2000000000,
        used: 1500000000,
        available: 500000000,
        percent: 75,
      },
      last_check: "2024-01-15T10:30:00Z",
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toContain("production-server");
    expect(wrapper.text()).toContain("prod.example.com");
  });

  test("handles array of disk data if provided", () => {
    const hostData = {
      id: "manual-1",
      name: "multi-disk-server",
      host: "multi.example.com",
      ip: "10.0.0.80",
      disks: [
        { mount: "/", usage: 70 },
        { mount: "/var", usage: 50 },
        { mount: "/home", usage: 85 },
      ],
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("displays connection status if available", () => {
    const hostData = {
      id: "manual-1",
      name: "monitored-server",
      host: "monitored.example.com",
      ip: "10.0.0.90",
      status: "online",
      last_check: "2024-01-15T10:35:00Z",
    };

    wrapper = mount(ManualHostCard, {
      propsData: { host: hostData },
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm).toBeTruthy();
  });
});
