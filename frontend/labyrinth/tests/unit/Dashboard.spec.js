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
  beforeEach(() => {
    wrapper.setData({
      full_data: [
        {
          subnet: "172.19.0",
          origin: {
            ip: "",
            icon: "",
          },
          links: {
            ref: "",
            ip: "",
            icon: "",
            color: "",
          },
          groups: [
            {
              name: "",
              hosts: [
                {
                  ip: "172.19.0.0",
                  subnet: "172.19.0",
                  mac: "172.19.0.0",
                  group: "",
                  icon: "",
                  monitor: false,
                  services: [
                    {
                      name: "open_ports",
                      state: -1,
                    },
                    {
                      name: "closed_ports",
                      state: -1,
                    },
                    {
                      name: "new_host",
                      state: true,
                    },
                  ],
                  open_ports: [22],
                  class: "",
                  host: "",
                },
                {
                  ip: "172.19.0.6",
                  subnet: "172.19.0",
                  mac: "172.19.0.6",
                  group: "",
                  icon: "",
                  monitor: false,
                  services: [
                    {
                      name: "open_ports",
                      state: true,
                    },
                    {
                      name: "closed_ports",
                      state: true,
                    },
                    {
                      name: "new_host",
                      state: false,
                    },
                    {
                      name: "Fileboi",
                      state: true,
                      latest_metric: {
                          tags: {
                             ip: "172.19.0.6" 
                          }
                      }

                    }
                  ],
                  open_ports: [139],
                  class: "",
                  host: "TESTHOST",
                },
              ],
            },
          ],
        },
      ],
    });
  });
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });

  test("sortSubnets", () => {
    var subnets = [
      {
        subnet: "192.168.1",
      },
      {
        subnet: "192.168.10",
      },
      {
        subnet: "10.8.0",
      },
      {
        subnet: "192.168.2",
      },
    ];
    var output = [
      {
        subnet: "10.8.0",
      },
      {
        subnet: "192.168.1",
      },
      {
        subnet: "192.168.2",
      },
      {
        subnet: "192.168.10",
      },
    ];
    expect(wrapper.vm.sortSubnets(subnets)).toStrictEqual(output);
  });

  test("filterMonitor", () => {
    expect(wrapper.vm.filterMonitored(undefined, false)).toBeFalsy();

    var groups = [
      {
        something: 1,
      },
      {
        name: "yes",
        hosts: [
          {
            monitor: false,
          },
          {
            monitor: true,
          },
        ],
      },
      {
        name: "no",
        hosts: [
          {
            monitor: false,
          },
        ],
      },
    ];

    expect(wrapper.vm.filterMonitored(groups, true)).toStrictEqual([groups[1]]);
  });

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
        left: 7,
      },
      {
        color: "white",
        top_1: "192.168.2.1",
        top_2: "192.168.1.1",
        left: 14,
      },
    ];

    expect(wrapper.vm.prepareOriginsLinks(subnets)).toStrictEqual(expected);
  });

  /* Parse Command Lines */

  /*
  test("parseCommandLine - service FAIL", async () => {
    wrapper.setData({
      smartbar: "service=FAIL",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });

  test("parseCommandLine - service OLD", async () => {
    wrapper.setData({
      smartbar: "service=OLD",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });
  test("parseCommandLine - service OK", async () => {
    wrapper.setData({
      smartbar: "service=OK",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(0);
  });
  */

  test("parseCommandLine - service Fileboi", async () => {
    wrapper.setData({
      smartbar: "service=Fileboi",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });

  test("parseCommandLine - host TESTHOST", async () => {
    wrapper.setData({
      smartbar: "host=TESTHOST",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts
    found_hosts = found_hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });

  test("parseCommandLine - tag ip", async () => {
    wrapper.setData({
      smartbar: "tag:ip=172.19.0.6",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });

  test("parseCommandLine - port:22", async () => {
    wrapper.setData({
      smartbar: "port=22",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });

  /*
  test("parseCommandLine - NOT port:23", async () => {
    wrapper.setData({
      smartbar: "NOT port=23",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(2);
  });

  test("parseCommandLine - NOT port:23 AND ", async () => {
    wrapper.setData({
      smartbar: "NOT port=23 AND service=FAIL",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });
  test("parseCommandLine - port 23 OR tag ip", async () => {
    wrapper.setData({
      smartbar: "port=23 OR NOT tag:ip=172.19.0.6",
    });
    await wrapper.vm.$forceUpdate();
    let found_hosts = wrapper.vm.parsed_data[0].groups[0].hosts.filter(x=>x.display);
    expect(found_hosts.length).toStrictEqual(1);
  });
  */
});
