// TEMPLATE FILE - Copy this file
import { config, mount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/views/Deploy.vue";
import Helper from "@/helper";

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
      "b-card",
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

  describe("deep links", () => {
    beforeEach(() => {
      // $route is read-only on the instance; shadow it for these tests
      Object.defineProperty(wrapper.vm, "$route", {
        writable: true,
        value: { query: {} },
      });
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    test("query params prepare a deployment of a saved playbook", async () => {
      const api = jest
        .spyOn(Helper, "apiCall")
        .mockResolvedValue("- hosts: all\n");
      wrapper.vm.$route = {
        query: {
          ips: "10.0.0.5,10.0.0.6",
          playbook: "patch.yml",
          become: "creds.yml",
        },
      };
      await wrapper.vm.loadDeepLink();

      expect(wrapper.vm.deep_link).toMatchObject({
        hosts: ["10.0.0.5", "10.0.0.6"],
        playbook: "patch",
        become_file: "creds",
        generated: false,
      });
      expect(api).toHaveBeenCalledWith(
        "get_ansible_file",
        "patch",
        expect.anything()
      );
      expect(wrapper.vm.deep_link_playbook).toBe("- hosts: all\n");
      // The manual deploy form is left alone
      expect(wrapper.vm.manual_ips).toBe(false);
      expect(wrapper.vm.ips).toEqual([]);
    });

    test("ips alone keep the plain multi-IP flow", async () => {
      wrapper.vm.$route = { query: { ips: "10.0.0.5" } };
      await wrapper.vm.loadDeepLink();

      expect(wrapper.vm.deep_link).toBeNull();
      expect(wrapper.vm.manual_ips).toBe(true);
      expect(wrapper.vm.ips).toEqual(["10.0.0.5"]);
    });

    test("staged request shows the generated playbook for review", async () => {
      const content = "- hosts: all\n  tasks: []\n";
      const api = jest.spyOn(Helper, "apiCall").mockResolvedValue({
        request_id: "req-1",
        hosts: ["10.0.0.7"],
        playbook: "ai_patch",
        become_file: "creds",
        ssh_key: "",
        notes: "Patch nginx",
        generated: true,
        playbook_content: content,
        runs: [],
      });
      wrapper.vm.$route = { query: { request: "req-1" } };
      await wrapper.vm.loadDeepLink();

      expect(api).toHaveBeenCalledTimes(1);
      expect(api).toHaveBeenCalledWith(
        "ansible_request",
        "req-1",
        expect.anything()
      );
      expect(wrapper.vm.deep_link.request_id).toBe("req-1");
      expect(wrapper.vm.deep_link_playbook).toBe(content);
    });
  });
});
