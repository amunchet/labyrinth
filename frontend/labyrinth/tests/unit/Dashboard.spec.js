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
  test("findTitleClass", () => {
    expect(wrapper.vm.findTitleClass("")).toBe("text-right subnet");
    expect(wrapper.vm.findTitleClass({ color: "blue" })).toBe(
      "text-right subnet blue"
    );
  });
  test("findTop - connector calculations", async () => {
    wrapper.vm.$data.connector_count = 1;
    wrapper.vm.$refs = {
      start_0: [
        {
          $el: {
            offsetTop: 5,
            offsetHeight: 10,
          },
        },
      ],
      end_1: [
        {
          offsetTop: 20,
        },
      ],
    };

    wrapper.vm.findTop();
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.connectorBottom).toStrictEqual([1]);
  });
  test("$refs", () => {});
});
