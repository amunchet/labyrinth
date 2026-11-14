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

  describe("manual vault entry", () => {
    const { Vault } = require("ansible-vault");
    const entry = {
      vault_password: "testpassword",
      filename: "lab.yml",
      ssh_username: "root",
      ssh_password: 'p#ss: "wörd"',
      ssh_passphrase: "sshkeypass",
      ssh_key_file: "sshkeyfile",
    };
    let modal;

    beforeEach(() => {
      wrapper.vm.$data.generated_ansible = { ...entry };
      modal = { hide: jest.fn() };
      Object.defineProperty(wrapper.vm, "$bvModal", { value: modal });
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    test("encrypts quoted YAML that decrypts back, non-ASCII included", async () => {
      const encrypted = await wrapper.vm.generateAnsibleVault();
      expect(encrypted.startsWith("$ANSIBLE_VAULT;1.1;AES256\n")).toBe(true);
      const plain = await new Vault({ password: "testpassword" }).decrypt(
        encrypted
      );
      // Quoted, so a password with "#", ": " or quotes stays valid YAML
      expect(plain).toBe(
        'ansible_user: "root"\n' +
          'ansible_ssh_pass: "p#ss: \\"wörd\\""\n' +
          'ansible_become_password: "p#ss: \\"wörd\\""\n' +
          'ssh_key_pass: "sshkeypass"\n' +
          'ssh_key_file: "/src/uploads/ssh/sshkeyfile"\n'
      );
    });

    test("save encrypts, uploads and selects the new file", async () => {
      const post = jest.spyOn(Helper, "apiPost").mockResolvedValue("lab.yml");
      jest.spyOn(Helper, "apiCall").mockResolvedValue(["lab.yml"]);

      await wrapper.vm.saveAnsibleVault({ preventDefault() {} });

      const form = post.mock.calls[0][4];
      expect(post.mock.calls[0].slice(0, 2)).toEqual(["upload", "/become"]);
      expect(form.get("filename")).toBe("lab.yml");
      expect(form.get("file")).toContain("$ANSIBLE_VAULT");
      expect(wrapper.vm.selected.become).toBe("lab.yml");
      expect(wrapper.vm.saving_vault).toBe(false);
      expect(modal.hide).toHaveBeenCalledWith("add_vault");
    });

    test("save refuses an incomplete entry instead of uploading", async () => {
      const post = jest.spyOn(Helper, "apiPost");
      wrapper.vm.$data.generated_ansible = { ...entry, filename: ".yml" };

      await wrapper.vm.saveAnsibleVault({ preventDefault() {} });

      expect(post).not.toHaveBeenCalled();
      expect(modal.hide).not.toHaveBeenCalled();
      expect(store.state.error).toContain("filename");
    });

    test("save with nothing typed just closes", async () => {
      const post = jest.spyOn(Helper, "apiPost");
      wrapper.vm.$data.generated_ansible = { type: "Username and Password" };

      await wrapper.vm.saveAnsibleVault({ preventDefault() {} });

      expect(post).not.toHaveBeenCalled();
      expect(modal.hide).toHaveBeenCalledWith("add_vault");
    });

    test("a failed upload keeps the dialog open", async () => {
      jest.spyOn(Helper, "apiPost").mockRejectedValue(new Error("HTTP 522"));

      await wrapper.vm.saveAnsibleVault({ preventDefault() {} });

      expect(modal.hide).not.toHaveBeenCalled();
      expect(wrapper.vm.saving_vault).toBe(false);
    });
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
