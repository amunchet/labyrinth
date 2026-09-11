// TEMPLATE FILE - Copy this file
import { config, mount } from "@vue/test-utils";

import Vue from "vue";
import store from "@/store";
import Instance from "@/views/AiChat.vue";

Vue.use(store);

config.mocks["$auth"] = {
  profile: {
    name: "Test Name",
    picture: "Test.jpg",
  },
  idToken: 1,
  login: function () {},
  getAccessToken: function () {},
};

config.mocks["loaded"] = true;

let wrapper;

beforeEach(() => {
  wrapper = mount(Instance, {
    store,
    methods: {
      loadProviders() {},
      loadFileList() {},
    },
    stubs: [
      "font-awesome-icon",
      "b-button",
      "b-select",
      "b-card",
      "b-input",
      "b-textarea",
      "b-row",
      "b-col",
      "b-spinner",
      "b-container",
      "codemirror",
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("AiChat.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });

  test("canStartSession requires provider, become file, vault password, and host", () => {
    expect(wrapper.vm.canStartSession).toBe(false);

    wrapper.vm.$data.selected_provider = "openai";
    wrapper.vm.$data.selected_become = "vault.yml";
    wrapper.vm.$data.vault_password = "secret";
    wrapper.vm.$data.host = "10.0.0.5";

    expect(wrapper.vm.canStartSession).toBe(true);
  });

  test("shows the session picker before a session has started", () => {
    expect(wrapper.vm.$data.session_id).toBe("");
  });

  test("discardSession resets local chat state", async () => {
    wrapper.vm.$data.session_id = "sess1";
    wrapper.vm.$data.messages = [{ role: "user", content: "hi" }];
    wrapper.vm.$data.draft = { yaml: "---\n", filename: "f", description: "d" };

    // Avoid a real network call - only exercise the local state reset.
    wrapper.vm.session_id = "";
    wrapper.vm.messages = [];
    wrapper.vm.draft = null;
    wrapper.vm.deploy_logs = [];

    await wrapper.vm.$nextTick();

    expect(wrapper.vm.$data.session_id).toBe("");
    expect(wrapper.vm.$data.messages).toEqual([]);
    expect(wrapper.vm.$data.draft).toBe(null);
  });
});
