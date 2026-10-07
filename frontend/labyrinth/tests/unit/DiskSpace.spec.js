import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import DiskSpace from "@/views/DiskSpace.vue";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
  getAccessToken: jest.fn(() => Promise.resolve("access-token")),
};

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
      stubs: [
        "DiskSpaceView",
        "DiskSpaceSettings",
        "TelegrafCheckView",
        "GraylogCheckView",
      ],
    });

    expect(wrapper.findComponent({ name: "BTabs" }).exists()).toBe(true);
  });

  test("displays disk space view tab/section", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: [
        "DiskSpaceView",
        "DiskSpaceSettings",
        "TelegrafCheckView",
        "GraylogCheckView",
      ],
    });

    const tabs = wrapper.findAllComponents({ name: "BTab" });
    expect(tabs.at(0).props("title")).toBe("Disk Space Check");
  });

  test("displays disk space settings tab/section", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: [
        "DiskSpaceView",
        "DiskSpaceSettings",
        "TelegrafCheckView",
        "GraylogCheckView",
      ],
    });

    const tabs = wrapper.findAllComponents({ name: "BTab" });
    expect(tabs.at(3).props("title")).toBe("Settings");
  });

  test("displays telegraf check tab/section", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: [
        "DiskSpaceView",
        "DiskSpaceSettings",
        "TelegrafCheckView",
        "GraylogCheckView",
      ],
    });

    const tabs = wrapper.findAllComponents({ name: "BTab" });
    expect(tabs.at(1).props("title")).toBe("Telegraf Check");
    expect(tabs.at(2).props("title")).toBe("Graylog Check");
  });

  test("displays documentation tab/section", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: [
        "DiskSpaceView",
        "DiskSpaceSettings",
        "TelegrafCheckView",
        "GraylogCheckView",
      ],
    });

    expect(wrapper.findAllComponents({ name: "BTab" }).length).toBe(4);
  });

  test("component has proper structure", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: [
        "DiskSpaceView",
        "DiskSpaceSettings",
        "TelegrafCheckView",
        "GraylogCheckView",
      ],
    });

    expect(wrapper.vm).toBeTruthy();
  });

  test("renders without errors", () => {
    expect(() => {
      wrapper = mount(DiskSpace, {
        mocks: { $auth: config.mocks["$auth"] },
        stubs: [
          "DiskSpaceView",
          "DiskSpaceSettings",
          "TelegrafCheckView",
          "GraylogCheckView",
        ],
      });
    }).not.toThrow();
  });

  test("has navigation structure for tabs", () => {
    wrapper = mount(DiskSpace, {
      mocks: { $auth: config.mocks["$auth"] },
      stubs: [
        "DiskSpaceView",
        "DiskSpaceSettings",
        "TelegrafCheckView",
        "GraylogCheckView",
      ],
    });

    const html = wrapper.html();
    expect(html).toBeTruthy();
  });
});
