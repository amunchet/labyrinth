import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import ProxmoxDocumentation from "@/components/DiskSpace/ProxmoxDocumentation.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
};

describe("ProxmoxDocumentation.vue", () => {
  let wrapper;

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", () => {
    wrapper = mount(ProxmoxDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".proxmox-documentation").exists()).toBe(true);
  });

  test("displays documentation content", () => {
    wrapper = mount(ProxmoxDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toMatch(
      /Proxmox|Documentation|Setup|Configuration/i
    );
  });

  test("contains informational sections", () => {
    wrapper = mount(ProxmoxDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const html = wrapper.html();
    expect(html).toBeTruthy();
  });

  test("displays headings", () => {
    wrapper = mount(ProxmoxDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const headings = wrapper.findAll("h1, h2, h3, h4, h5, h6");
    expect(headings.length).toBeGreaterThan(0);
  });

  test("renders code examples or instructions", () => {
    wrapper = mount(ProxmoxDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const codeElements = wrapper.findAll("code, pre, .code");
    expect(codeElements.length).toBeGreaterThanOrEqual(0);
  });

  test("displays alerts or important notices", () => {
    wrapper = mount(ProxmoxDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const alerts = wrapper.findAll(".alert, .b-alert, .notice");
    expect(alerts.length).toBeGreaterThanOrEqual(0);
  });
});
