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
    wrapper.vm.loadServices = () => {};
    wrapper.vm.loadLookups = () => {};

    // Raw host documents (e.g. from /inventory/) list services by name
    let device = {
      ip: "10.0.0.5",
      mac: "AA:BB",
      host: "plc-gate",
      services: ["open_ports", { name: "cpu", state: true }],
      location: "Plant",
      _live: { status: "up" },
    };
    wrapper.setProps({ inp_host: device });
    await wrapper.vm.$forceUpdate();
    let host = wrapper.vm.$data.host;
    expect(wrapper.vm.$data.isNew).toBe(false);
    expect(host).not.toBe(device);
    expect(host.services).toStrictEqual([
      { name: "open_ports", state: "" },
      { name: "cpu", state: true },
    ]);
    expect(host._live).toBeUndefined();
    expect(host.location).toBe("Plant");
    expect(host.rack).toBe("");

    // Editing the form leaves the caller's object alone
    host.host = "renamed";
    expect(device.host).toBe("plc-gate");

    // Creates a new host
    wrapper.setProps({
      inp_host: "",
    });
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.isNew).toBe(true);
    expect(wrapper.vm.$data.host).toStrictEqual(wrapper.vm.$data.safe_host);
    expect(wrapper.vm.$data.metrics).toStrictEqual([]);

    // A device without a MAC/key is new, with its preset location
    wrapper.setProps({ inp_host: { location: "Plant", services: [] } });
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.isNew).toBe(true);
    expect(wrapper.vm.$data.host.location).toBe("Plant");
  });

  test("IP is optional but must be valid, and unique for new hosts", async () => {
    await wrapper.setProps({ all_ips: new Set(["10.0.0.5"]) });
    wrapper.setData({ host: { ip: "", subnet: "" }, isNew: true });
    expect(wrapper.vm.$v.host.$invalid).toBe(false);
    expect(wrapper.vm.duplicate_ip).toBe(false);

    wrapper.setData({ host: { ip: "10.0.0.300", subnet: "" } });
    expect(wrapper.vm.$v.host.ip.$invalid).toBe(true);

    wrapper.setData({ host: { ip: "10.0.0.5", subnet: "" } });
    expect(wrapper.vm.duplicate_ip).toBe(true);
    wrapper.setData({ isNew: false });
    expect(wrapper.vm.duplicate_ip).toBe(false);
  });

  test("rack and uplink choices follow the inventory", async () => {
    wrapper.setData({
      locations: [
        { name: "Plant", racks: [{ name: "Rack A", units: 42 }] },
        { name: "Office", racks: [] },
      ],
      all_hosts: [
        { mac: "SELF", ip: "10.0.0.5", host: "me" },
        { mac: "CORE", ip: "10.0.0.1", host: "core-sw" },
        { mac: "device-1", ip: "", host: "" },
      ],
      host: { mac: "SELF", location: "Plant" },
    });
    expect(wrapper.vm.rack_options.slice(1)).toStrictEqual(["Rack A"]);
    expect(wrapper.vm.uplink_options).toStrictEqual([
      { value: "CORE", text: "core-sw (10.0.0.1)" },
      { value: "device-1", text: "device-1" },
    ]);

    wrapper.setData({ host: { mac: "SELF", location: "Office" } });
    expect(wrapper.vm.rack_options).toHaveLength(1);
  });
});
