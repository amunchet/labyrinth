import { config, shallowMount } from "@vue/test-utils";
import Vue from "vue";
import store from "@/store";
import Instance from "@/views/Settings/Ansible.vue";

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

let wrapper;

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    store,
    methods: {
      loadSettings: function () {},
    },
    stubs: [
      "font-awesome-icon",
      "b-button",
      "b-select",
      "b-row",
      "b-col",
      "b-container",
      "b-form-checkbox",
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("SettingsAnsible.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.exists()).toBe(true);
  });

  test("defaults manage_vars_files to enabled", () => {
    expect(wrapper.vm.manage_vars_files).toBe(true);
  });
});
