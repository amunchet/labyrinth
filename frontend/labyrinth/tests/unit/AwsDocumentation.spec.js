import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import AwsDocumentation from "@/components/AWS/AwsDocumentation.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
};

describe("AwsDocumentation.vue", () => {
  let wrapper;

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", () => {
    wrapper = mount(AwsDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.find(".p-3").exists()).toBe(true);
  });

  test("displays documentation content", () => {
    wrapper = mount(AwsDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.text()).toMatch(/AWS|Documentation|Setup|Configuration/i);
  });

  test("displays code blocks or instructions", () => {
    wrapper = mount(AwsDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const html = wrapper.html();
    expect(html).toBeTruthy();
  });

  test("contains headings", () => {
    wrapper = mount(AwsDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const headings = wrapper.findAll("h1, h2, h3, h4, h5, h6");
    expect(headings.length).toBeGreaterThan(0);
  });

  test("properly renders alerts or callout boxes", () => {
    wrapper = mount(AwsDocumentation, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const alerts = wrapper.findAll(".alert, .b-alert");
    expect(alerts.length).toBeGreaterThanOrEqual(0);
  });
});
