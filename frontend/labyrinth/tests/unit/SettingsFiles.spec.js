import { config, shallowMount } from "@vue/test-utils";
import Vue from "vue";
import store from "@/store";
import Instance from "@/views/Settings/Files.vue";

Vue.use(store);

config.mocks["$auth"] = {
  profile: {
    name: "Test Name",
    picture: "Test.jpg",
  },
  idToken: 1,
  accessToken: 1,
  login: function () {},
  getAccessToken: function () {},
};

config.mocks["$bvModal"] = {
  show: function () {},
  hide: function () {},
  msgBoxConfirm: function () {
    return Promise.resolve(false);
  },
};

let wrapper;

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    store,
    methods: {
      loadFiles: function () {},
    },
    stubs: [
      "font-awesome-icon",
      "b-modal",
      "b-button",
      "b-select",
      "b-input",
      "b-row",
      "b-col",
      "b-spinner",
      "b-container",
      "b-form-file",
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("SettingsFiles.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.exists()).toBe(true);
  });

  test("defaults to become folder", () => {
    expect(wrapper.vm.selected_folder).toBe("become");
  });
});
