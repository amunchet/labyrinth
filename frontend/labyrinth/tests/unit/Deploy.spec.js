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

    test("a staged request keeps the agent's vault format", async () => {
      jest.spyOn(Helper, "apiCall").mockResolvedValue({
        request_id: "req-2",
        hosts: ["10.0.0.7"],
        playbook: "patch",
        become_file: "proxmox-root",
        vault_format: "proxmox",
        generated: true,
        playbook_content: "",
      });
      wrapper.vm.$route = { query: { request: "req-2" } };
      await wrapper.vm.loadDeepLink();

      expect(wrapper.vm.deep_link.vault_format).toBe("proxmox");
    });

    test("a request staged before formats existed reads as standard", async () => {
      jest.spyOn(Helper, "apiCall").mockResolvedValue({
        request_id: "req-3",
        hosts: ["10.0.0.7"],
        playbook: "patch",
        become_file: "creds",
        generated: true,
        playbook_content: "",
      });
      wrapper.vm.$route = { query: { request: "req-3" } };
      await wrapper.vm.loadDeepLink();

      expect(wrapper.vm.deep_link.vault_format).toBe("standard");
    });

    test("a deploy link carries the vault format", async () => {
      jest.spyOn(Helper, "apiCall").mockResolvedValue("- hosts: all\n");
      wrapper.vm.$route = {
        query: {
          ips: "10.0.0.5",
          playbook: "patch",
          become: "proxmox-root",
          vault_format: "proxmox",
        },
      };
      await wrapper.vm.loadDeepLink();

      expect(wrapper.vm.deep_link.vault_format).toBe("proxmox");
    });

    test("copying a deploy link only names a non-standard format", async () => {
      const writeText = jest.fn().mockResolvedValue();
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText },
      });
      jest.spyOn(Helper, "apiCall").mockResolvedValue("- hosts: all\n");
      wrapper.vm.selected_host = "10.0.0.5";
      wrapper.vm.selected_playbook = "patch.yml";
      wrapper.vm.selected.become = "proxmox-root.yml";

      await wrapper.vm.copyDeployLink();
      expect(writeText.mock.calls[0][0]).not.toContain("vault_format");

      wrapper.vm.vault_format = "proxmox";
      await wrapper.vm.copyDeployLink();
      expect(writeText.mock.calls[1][0]).toContain("vault_format=proxmox");
    });
  });

  describe("vault format", () => {
    afterEach(() => {
      jest.restoreAllMocks();
    });

    const apiData = (api) => JSON.parse(api.mock.calls[0][4].get("data"));

    test("a manual deploy sends the chosen format", async () => {
      const api = jest.spyOn(Helper, "apiPost").mockResolvedValue({
        json: async () => ({ job_id: "job-1", status: "started" }),
      });
      jest
        .spyOn(Helper, "apiCall")
        .mockResolvedValue({ status: "completed", logs: [], results: "" });
      wrapper.vm.selected_host = "10.0.0.5";
      wrapper.vm.selected_playbook = "patch.yml";
      wrapper.vm.selected.become = "proxmox-root.yml";
      wrapper.vm.vault_password = "pw";
      wrapper.vm.vault_format = "proxmox";

      await wrapper.vm.runPlaybook();

      expect(apiData(api)).toMatchObject({
        become_file: "proxmox-root",
        vault_format: "proxmox",
      });
    }, 10000);

    test("the prepared deployment sends the format chosen on it", async () => {
      const api = jest.spyOn(Helper, "apiPost").mockResolvedValue({
        json: async () => ({ job_id: "job-2", status: "started" }),
      });
      jest
        .spyOn(Helper, "apiCall")
        .mockResolvedValue({ status: "completed", logs: [], failures: [] });
      wrapper.vm.vault_password = "pw";
      wrapper.vm.deep_link = {
        request_id: "req-4",
        hosts: ["10.0.0.5"],
        playbook: "patch",
        become_file: "proxmox-root",
        vault_format: "proxmox",
      };

      await wrapper.vm.deployDeepLink();

      expect(apiData(api)).toEqual({
        vault_password: "pw",
        become_file: "proxmox-root",
        vault_format: "proxmox",
      });
    }, 10000);
  });
});
