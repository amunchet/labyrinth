// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/components/CreateEditHost.vue";

import Vuelidate from "vuelidate";

Vue.use(store);
Vue.use(Vuelidate);

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
      inpHost: "",

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
      "b-form-checkbox",
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

describe("CreateEditHost.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });
  test("inp_host", async () => {
    wrapper.vm.loadMetrics = () => {};
    wrapper.setProps({
      inp_host: "TEST",
    });
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.isNew).toBe(false);
    expect(wrapper.vm.$data.host).toBe("TEST");

    // Creates a new host
    wrapper.setProps({
      inp_host: "",
    });
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.isNew).toBe(true);
    expect(wrapper.vm.$data.host).toStrictEqual(wrapper.vm.$data.safe_host);
    expect(wrapper.vm.$data.metrics).toStrictEqual([]);
  });
});
