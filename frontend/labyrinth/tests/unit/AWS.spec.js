import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import AWS from "@/views/AWS.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
  getAccessToken: jest.fn(() => Promise.resolve("access-token")),
};

describe("AWS.vue", () => {
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
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: ["AwsSettings", "AwsInstancesView", "AwsDocumentation"],
    });

    expect(wrapper.findComponent({ name: "BTabs" }).exists()).toBe(true);
  });

  test("displays AWS settings tab/section", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: ["AwsSettings", "AwsInstancesView", "AwsDocumentation"],
    });

    const tabs = wrapper.findAllComponents({ name: "BTab" });
    expect(tabs.at(1).props("title")).toBe("Settings");
  });

  test("displays AWS instances view tab/section", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: ["AwsSettings", "AwsInstancesView", "AwsDocumentation"],
    });

    const tabs = wrapper.findAllComponents({ name: "BTab" });
    expect(tabs.at(0).props("title")).toBe("EC2 Instances");
  });

  test("displays AWS documentation tab/section", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: ["AwsSettings", "AwsInstancesView", "AwsDocumentation"],
    });

    const tabs = wrapper.findAllComponents({ name: "BTab" });
    expect(tabs.at(2).props("title")).toBe("Documentation");
  });

  test("component has proper structure", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: ["AwsSettings", "AwsInstancesView", "AwsDocumentation"],
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("renders without errors", () => {
    expect(() => {
      wrapper = mount(AWS, {
        mocks: { $auth: config.mocks["$auth"] },
        stubs: ["AwsSettings", "AwsInstancesView", "AwsDocumentation"],
      });
    }).not.toThrow();
  });
});
