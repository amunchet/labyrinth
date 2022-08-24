// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/views/Dashboard.vue";

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
  wrapper = shallowMount(Instance, {
    propsData: {
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
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("Dashboard.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });
  test("findClass", () => {
    expect(wrapper.vm.findClass("")).toBe("outer");
    expect(wrapper.vm.findClass({ color: "blue" })).toBe("outer blue-bg");
  });
  
  test("$refs", () => {});

  test("prepareOriginsLinks", () => {
    // Function to list out a structure that Connector can loop over

    let subnets;

    subnets = [
      {
        subnet: "10.0.0",
        origin: {
          ip: "10.0.0.1",
          icon: "default",
        },
        links: {
          ip: "192.168.0.1",
          color: "orange",
        },
      },
      {
        subnet: "192.168.0",
        origin: {
          ip: "192.168.0.1",
          icon: "default",
        },
        links: {
          ip: "192.168.1.1",
          color: "red",
        },
      },
      {
        subnet: "192.168.1",
        origin: {
          ip: "192.168.1.1",
          icon: "default",
        },
      },
      {
        subnet: "192.168.2",
        origin: {
          ip: "192.168.2.1",
          icon: "default",
        },
        links: {
          ip: "192.168.1.1",
          color: "green",
        },
      },
    ];

    var expected = [
      {
        color: "orange",
        top_1: "10.0.0.1",
        top_2: "192.168.0.1",
        left: 0,
      },
      {
        color: "red",
        top_1: "192.168.0.1",
        top_2: "192.168.1.1",
        left: 20,
      },
      {
        color: "green",
        top_1: "192.168.2.1",
        top_2: "192.168.1.1",
        left: 40,
      },
    ];

    expect(wrapper.vm.prepareOriginsLinks(subnets)).toStrictEqual(expected);
  });
});
