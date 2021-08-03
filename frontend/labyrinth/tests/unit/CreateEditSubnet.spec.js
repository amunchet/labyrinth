// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/components/CreateEditSubnet.vue";

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

let state;
let auth;
let wrapper;
let created;

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
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("CreateEditSubnet.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });

  test("Changing input subnet", async () => {
    wrapper.setProps({
      inp_subnet: "TEST",
    });
    await wrapper.vm.$forceUpdate();

    expect(wrapper.vm.$data.subnet.indexOf("hosts")).toBe(-1);
    expect(wrapper.vm.$data.subnet.indexOf("groups")).toBe(-1);
    expect(wrapper.vm.$data.isNew).toBe(false);

    wrapper.setProps({
      inp_subnet: "",
    });
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.isNew).toBe(true);
    expect(wrapper.vm.$data.subnet.subnet).toBe("");
  });
});
