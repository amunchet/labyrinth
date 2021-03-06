// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/components/Host.vue";

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
      icon: "test",
      passed_class: "test",
      show_ports: "0",
      host: "",
      ip: "test.test.test",
      services: [
        {
          name: "test",
        },
      ],
      cpu: "test",
      mem: "test",
      hd: "test",
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
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("Host.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });

  test("determineClass", () => {
    var service = {
      state: -1,
    };
    expect(wrapper.vm.determineClass(service));
    service.state = false;

    expect(wrapper.vm.determineClass(service));
    service.state = 71;

    expect(wrapper.vm.determineClass(service));
  });

  test("drag_start", () => {
    wrapper.vm.drag_start("TESTIP");
    expect(wrapper.vm.$data.drag_class).toEqual("dragging");
    expect(wrapper.vm.$data.dragging_ip).toEqual("TESTIP");
  });
  test("drag_end", () => {
    wrapper.vm.drag_end();
    expect(wrapper.vm.$data.drag_class).toEqual("");
    expect(wrapper.vm.$data.dragging_ip).toEqual("");
  });
});
