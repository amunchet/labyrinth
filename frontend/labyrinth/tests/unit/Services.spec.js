// tests/Services.spec.js
import { config, shallowMount } from "@vue/test-utils";
import Vue from "vue";
import Instance from "@/views/Services.vue";

// ---- Mock Helper api layer used by Services.vue
jest.mock("@/helper", () => {
  return {
    __esModule: true,
    default: {
      // keep signatures compatible with Services.vue
      apiCall: jest.fn(async (name, arg) => {
        if (name === "settings" && arg === "default_telegraf_backend") {
          return "http://test";
        }
        if (name === "telegraf_key") {
          return ""; // test uses empty token in expected headers
        }
        if (name === "redis" && arg === "get_structure") {
          return [];
        }
        if (name === "redis" && arg === "autosave") {
          // no autosave to start with
          return {};
        }
        if (name === "hosts") {
          return [{ ip: "TEST", mac: "Test" }];
        }
        if (name === "load_service") {
          // structured config payload
          return {};
        }
        if (name === "run_conf") {
          return "ok";
        }
        return {};
      }),
      apiPost: jest.fn(async () => {
        return "ok";
      }),
    },
  };
});

config.mocks["$auth"] = {
  profile: { name: "Test Name", picture: "Test.jpg" },
  idToken: 1,
  login: function () {},
  getAccessToken: function () {},
};

config.mocks["$sanitize"] = (x) => x;

// Mock the store so commits from component don't explode
config.mocks["$store"] = {
  commit: jest.fn(),
};

let wrapper;

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    // no real Vuex store needed; we mocked $store above
    stubs: [
      "font-awesome-icon",
      "b-modal",
      "b-button",
      "b-select",
      "b-input",
      "b-row",
      "b-col",
      "b-table",
      "b-tab",
      "b-tabs",
      "b-spinner",
      "b-container",
      "b-textarea",
      "b-avatar",
      "b-form-file",
      "b-form-input",
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("Services.vue (refactor)", () => {
  test("mounts", () => {
    expect(wrapper.vm).toBeTruthy();
  });

  test("loadSuggestedFields sets outputs.http and global_tags for selected host", async () => {
    // Arrange: minimal state so loadSuggestedFields doesn't call out for defaults
    wrapper.vm.$data.raw_hosts = [{ ip: "TEST", mac: "Test" }];
    wrapper.vm.$data.default_backend = "http://test";
    wrapper.vm.$data.telegraf_key = ""; // header comes from this
    wrapper.vm.$data.selected_host = "TEST";
    wrapper.vm.$data.output_data = {};

    // Act
    await wrapper.vm.loadSuggestedFields();

    // Assert
    expect(wrapper.vm.$data.output_data["global_tags"]).toStrictEqual({
      ip: "TEST",
      mac: "Test",
    });

    expect(wrapper.vm.$data.output_data["outputs"]["http"]).toStrictEqual({
      url: "http://test",
      timeout: "5s",
      method: "POST",
      insecure_skip_verify: true,
      data_format: "json",
      content_encoding: "identity",
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        idle_conn_timeout: "0",
        Authorization: "",
      },
    });
  });

  test("add transfers a template structure and retains canonical outputs.http + tags", async () => {
    // Arrange
    const data = {
      item: [
        {
          server_key: "my-server-key",
          amon_instance: "https://youramoninstance",
          timeout: "5s",
        },
      ],
      name: "amon",
      parent: "undefined.outputs",
    };

    wrapper.vm.$data.raw_hosts = [{ ip: "TEST", mac: "Test" }];
    wrapper.vm.$data.default_backend = "http://test";
    wrapper.vm.$data.telegraf_key = "";
    wrapper.vm.$data.selected_host = "TEST";
    wrapper.vm.$data.output_data = {};

    // Act
    wrapper.vm.add(JSON.stringify(data));
    // add() triggers loadSuggestedFields() but it's async; ensure settled:
    await Vue.nextTick();
    await wrapper.vm.loadSuggestedFields();

    // Assert
    const expected = {
      outputs: {
        http: {
          content_encoding: "identity",
          data_format: "json",
          headers: {
            Authorization: "",
            "Content-Type": "text/plain; charset=utf-8",
            idle_conn_timeout: "0",
          },
          insecure_skip_verify: true,
          method: "POST",
          timeout: "5s",
          url: "http://test",
        },
        amon: [
          {
            server_key: "my-server-key",
            amon_instance: "https://youramoninstance",
            timeout: "5s",
          },
        ],
      },
      global_tags: {
        ip: "TEST",
        mac: "Test",
      },
    };

    expect(wrapper.vm.$data.output_data).toStrictEqual(expected);
  });
});

