// TEMPLATE FILE - Copy this file
import { config, mount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/views/Deploy.vue";

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
  wrapper = mount(Instance, {
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

describe("Deploy.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });

  test("ansible encrypt", async () => {
    wrapper.vm.$data.generated_ansible = {
      vault_password: "testpassword",
      ansible_user: "Test",
      ssh_password: "testpass",
      ssh_passphrase: "sshkeypass",
      ssh_key_file: "sshkeyfile",
    };

    await wrapper.vm.$forceUpdate();
    await wrapper.vm.generateAnsibleVault();

    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.loading_generated_vault_file).toBe(false);
    expect(wrapper.vm.generated_vault_file).toContain("ANSIBLE_VAULT");
  });
});
