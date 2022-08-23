// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/components/CustomDashboardsView.vue";

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

describe('CustomDashboardsView.vue', () => {
    test('is a Vue instance', () => {
        expect(wrapper.isVueInstance).toBeTruthy()
    })

    test("computed_filtered_data", async ()=>{
        wrapper.vm.$data.selected_dashboard = {
            components: [
                {
                    name: "test_name",
                    subnet: "255.255.255"
                },
                {
                    name: "second_name",
                    subnet: "255.255.254"
                }
            ]
        }
        wrapper.vm.$data.full_data = [
            {
                subnet: "255.255.255",
                ip: "test_name"
            },
            {
                subnet: "255.255.254",
                ip: "second_name"
            },
            {
                subnet: "123.123.123",
                ip: "NOTSEEN"

            }
        ]

        await wrapper.vm.$forceUpdate()
        expect(wrapper.vm.computed_filtered_data).toStrictEqual([
            {
                ip: "test_name",
                subnet: "255.255.255"
            },
            {
                ip: "second_name",
                subnet: "255.255.254"
            }
        ])
    })

    test("generateHostStyle", ()=>{

    })
    test("generateBackgroundImage", ()=>{

    })
})
