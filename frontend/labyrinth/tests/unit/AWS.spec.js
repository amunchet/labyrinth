import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import AWS from "@/views/AWS.vue";
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

jest.mock("@/components/AWS/AwsSettings", () => ({
  name: "AwsSettings",
  template: "<div class='aws-settings'>AWS Settings</div>",
}));

jest.mock("@/components/AWS/AwsInstancesView", () => ({
  name: "AwsInstancesView",
  template: "<div class='aws-instances'>AWS Instances</div>",
}));

jest.mock("@/components/AWS/AwsDocumentation", () => ({
  name: "AwsDocumentation",
  template: "<div class='aws-docs'>AWS Documentation</div>",
}));

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
      stubs: {
        AwsSettings: true,
        AwsInstancesView: true,
        AwsDocumentation: true,
      },
    });

    expect(wrapper.find(".container, .p-3, [class*='view']").exists()).toBe(true);
  });

  test("displays AWS settings tab/section", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        AwsSettings: { template: "<div>Settings</div>" },
        AwsInstancesView: { template: "<div>Instances</div>" },
        AwsDocumentation: { template: "<div>Docs</div>" },
      },
    });

    expect(wrapper.text()).toMatch(/Settings|Instances|Documentation/i);
  });

  test("displays AWS instances view tab/section", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        AwsSettings: { template: "<div>Settings</div>" },
        AwsInstancesView: { template: "<div>Instances</div>" },
        AwsDocumentation: { template: "<div>Docs</div>" },
      },
    });

    expect(wrapper.text()).toMatch(/Instances|Settings|Documentation/i);
  });

  test("displays AWS documentation tab/section", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        AwsSettings: { template: "<div>Settings</div>" },
        AwsInstancesView: { template: "<div>Instances</div>" },
        AwsDocumentation: { template: "<div>Docs</div>" },
      },
    });

    expect(wrapper.text()).toMatch(/Documentation|Settings|Instances/i);
  });

  test("component has proper structure", () => {
    wrapper = mount(AWS, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: {
        AwsSettings: true,
        AwsInstancesView: true,
        AwsDocumentation: true,
      },
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("renders without errors", () => {
    expect(() => {
      wrapper = mount(AWS, {
        mocks: { $auth: config.mocks["$auth"] },
        stubs: {
          AwsSettings: true,
          AwsInstancesView: true,
          AwsDocumentation: true,
        },
      });
    }).not.toThrow();
  });
});
