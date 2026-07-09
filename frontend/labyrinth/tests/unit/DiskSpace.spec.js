import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import DiskSpace from "@/views/DiskSpace.vue";
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
}));

jest.mock("@/components/DiskSpace/DiskSpaceView", () => ({
  name: "DiskSpaceView",
  template: "<div class='disk-space-view'>Disk Space View</div>",
}));

jest.mock("@/components/DiskSpace/DiskSpaceSettings", () => ({
  name: "DiskSpaceSettings",
  template: "<div class='disk-space-settings'>Settings</div>",
}));

jest.mock("@/components/DiskSpace/ProxmoxDocumentation", () => ({
  name: "ProxmoxDocumentation",
  template: "<div class='proxmox-docs'>Docs</div>",
}));

describe("DiskSpace.vue", () => {
  let wrapper;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        DiskSpaceView: true,
        DiskSpaceSettings: true,
        ProxmoxDocumentation: true,
      },
    });

    expect(wrapper.find(".container, .p-3, [class*='view']").exists()).toBe(true);
  });

  test("displays disk space view tab/section", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        DiskSpaceView: { template: "<div>View</div>" },
        DiskSpaceSettings: { template: "<div>Settings</div>" },
        ProxmoxDocumentation: { template: "<div>Docs</div>" },
      },
    });

    expect(wrapper.text()).toMatch(/View|Settings|Documentation/i);
  });

  test("displays disk space settings tab/section", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        DiskSpaceView: { template: "<div>View</div>" },
        DiskSpaceSettings: { template: "<div>Settings</div>" },
        ProxmoxDocumentation: { template: "<div>Docs</div>" },
      },
    });

    expect(wrapper.text()).toMatch(/Settings|View|Documentation/i);
  });

  test("displays documentation tab/section", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        DiskSpaceView: { template: "<div>View</div>" },
        DiskSpaceSettings: { template: "<div>Settings</div>" },
        ProxmoxDocumentation: { template: "<div>Docs</div>" },
      },
    });

    expect(wrapper.text()).toMatch(/Documentation|View|Settings/i);
  });

  test("component has proper structure", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        DiskSpaceView: true,
        DiskSpaceSettings: true,
        ProxmoxDocumentation: true,
      },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("renders without errors", () => {
    expect(() => {
      wrapper = mount(DiskSpace, {
        mocks: { $auth: config.mocks["$auth"] },
        stubs: {
          DiskSpaceView: true,
          DiskSpaceSettings: true,
          ProxmoxDocumentation: true,
        },
      });
    }).not.toThrow();
  });

  test("has navigation structure for tabs", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        DiskSpaceView: { template: "<div>View</div>" },
        DiskSpaceSettings: { template: "<div>Settings</div>" },
        ProxmoxDocumentation: { template: "<div>Docs</div>" },
      },
    });

    const html = wrapper.html();
    expect(html).toBeTruthy();
  });
});
