// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/App.vue";

Vue.use(store);

config.mocks["$auth"] = {
  profile: {
    name: "Test Name",
    picture: "Test.jpg",
  },
  idToken: 1,
  login: function () {},
  getAccessToken: function () {},
  handleAuthentication() {},
};

config.mocks["$route"] = {
  query: {
    page: "Home",
  },
};

config.mocks["loaded"] = true;

let wrapper;

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    propsData: {
      options: [
        "All",
        "utopiany",
        "rousingr",
        "cunningh",
        "papayawi",
        "elegantc",
        "tidyseri",
        "quirkyco",
      ],
      onChange() {
        //console.log('select changed')
      },
    },
    store,
    methods: {},
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
      "b-navbar-toggle",
      "b-collapse",
      "b-nav-item",
      "router-link",
      "b-navbar-nav",
      "b-dropdown-item",
      "b-navbar-brand",
      "b-nav-item-dropdown",
      "router-view",
      "b-navbar",
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("App.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });
  test("Change Error message", async () => {
    wrapper.vm.$store.state.error = "TEST";
    expect(wrapper.vm.$store.state.error).toBe("TEST");

    wrapper.vm.$store.state.error = "401";
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$store.state.error).toBe(
      "Error: Logged out.  Please login again."
    );
  });
  test("checkErrorMessage", () => {
    wrapper.vm.$store.state.error = "Error!";
    expect(wrapper.vm.checkErrorMessage()).toBe("danger");
    wrapper.vm.$store.state.error = "Meow!";
    expect(wrapper.vm.checkErrorMessage()).toBe("success");
  });
});
