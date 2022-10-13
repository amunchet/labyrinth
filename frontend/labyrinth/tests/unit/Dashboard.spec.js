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

  test("sortSubnets", ()=>{
    var subnets = [
      {
        "subnet" : "192.168.1"
      },
      {
        "subnet" : "192.168.10"
      },
      {
        "subnet" : "10.8.0"
      },
      {
        "subnet" : "192.168.2"
      }
    ]
    var output = [
      {
        "subnet" : "10.8.0"
      },
      {
        "subnet" : "192.168.1"
      },
      {
        "subnet" : "192.168.2"
      },
      {
        "subnet" : "192.168.10"
      },
    ]
    expect(wrapper.vm.sortSubnets(subnets)).toStrictEqual(output)
  })

  test("filterMonitor", ()=>{
    expect(wrapper.vm.filterMonitored(undefined, false)).toBeFalsy();

    var groups = [
      {
        "something" : 1,
      },
      {
        name: "yes",
        hosts:[
          {
            "monitor" : false
          },
          {
            "monitor" : true
          }
        ]
      },
      {
        name: "no",
        hosts: [
          {
            "monitor" : false
          }
        ]
      }
    ]

    expect(wrapper.vm.filterMonitored(groups, true)).toStrictEqual([groups[1]])

  })

  test("findClass", () => {
    expect(wrapper.vm.findClass("")).toBe("");

    wrapper.vm.$data.themes = [
      {
        name: "TEST",
      },
    ];
    expect(wrapper.vm.findClass({ color: "TESTXXX" })).toBe("");
    expect(wrapper.vm.findClass({ color: "TEST" })).toBe(""); // No additional information

    wrapper.vm.$data.themes = [
      {
        name: "TEST",
        background: {
          hex: "black",
        },
        border: {
          hex: "red",
        },
        text: {
          hex: "green",
        },
      },
    ];

    expect(wrapper.vm.findClass({ color: "TEST" })).toStrictEqual(
      "background-color: black;border: 1px solid red;"
    );
    expect(wrapper.vm.findClass({ color: "TEST" }, 1)).toStrictEqual(
      "background-color: black;color: green;"
    );
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

    wrapper.vm.$data.themes = [
      {
        name: "orange",
        connection: {
          hex: "orange",
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
        color: "white",
        top_1: "192.168.0.1",
        top_2: "192.168.1.1",
        left: 10,
      },
      {
        color: "white",
        top_1: "192.168.2.1",
        top_2: "192.168.1.1",
        left: 20,
      },
    ];

    expect(wrapper.vm.prepareOriginsLinks(subnets)).toStrictEqual(expected);
  });
});
