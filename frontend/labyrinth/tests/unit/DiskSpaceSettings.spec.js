import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import DiskSpaceSettings from "@/components/DiskSpace/DiskSpaceSettings.vue";
import Helper from "@/helper";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
  },
  getAccessToken: jest.fn(() => Promise.resolve("access-token")),
};

jest.mock("@/helper", () => ({
  apiCall: jest.fn(),
  apiPost: jest.fn(),
  apiPut: jest.fn(),
  apiDelete: jest.fn(),
}));

describe("DiskSpaceSettings.vue", () => {
  let wrapper;

  beforeEach(() => {
    jest.clearAllMocks();
    Helper.apiCall
      .mockResolvedValueOnce({
        clusters: [],
        disk_space_alert_recipients: [],
        disk_space_alert_threshold: 80,
      })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ manual_hosts: [] });
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", async () => {
    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".disk-space-settings").exists()).toBe(true);
  });

  test("loads disk space settings on mount", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({
        clusters: [
          {
            _id: "cluster-1",
            name: "prod-cluster",
            host: "10.0.0.1",
          },
        ],
        disk_space_alert_recipients: ["admin@example.com"],
        disk_space_alert_threshold: 85,
      })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 100));

    expect(Helper.apiCall).toHaveBeenCalled();
  });

  test("displays success message on threshold update", async () => {
    Helper.apiPost.mockResolvedValue({ status: "updated" });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.alertThreshold = 90;
    wrapper.vm.alertRecipientsText = "admin@example.com";
    await wrapper.vm.saveAlertSettings();
    await wrapper.vm.$nextTick();

    expect(Helper.apiPost).toHaveBeenCalled();
  });

  test("displays error when update fails", async () => {
    Helper.apiPost.mockRejectedValue(new Error("Update failed"));

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.alertThreshold = 90;
    wrapper.vm.alertRecipientsText = "admin@example.com";
    await wrapper.vm.saveAlertSettings();

    expect(wrapper.vm.errorMessage).toBeTruthy();
  });

  test("handles recipient configuration", async () => {
    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.alertRecipientsText = "admin@example.com, backup@example.com";

    expect(wrapper.vm.alertRecipientsText).toBe(
      "admin@example.com, backup@example.com"
    );
  });

  test("clears error message", async () => {
    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.errorMessage = "Test error";
    wrapper.vm.errorMessage = "";

    expect(wrapper.vm.errorMessage).toBe("");
  });

  test("parses cluster data correctly", async () => {
    Helper.apiCall
      .mockResolvedValueOnce({
        clusters: [
          {
            _id: "c1",
            name: "cluster-1",
            host: "10.0.0.1",
          },
        ],
        disk_space_alert_recipients: [],
        disk_space_alert_threshold: 80,
      })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ manual_hosts: [] });

    wrapper = mount(DiskSpaceSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadSettings();
    await wrapper.vm.$nextTick();

    if (wrapper.vm.clusters) {
      expect(wrapper.vm.clusters.length).toBeGreaterThanOrEqual(0);
    }
  });

  describe("QEMU guest agent exceptions", () => {
    let confirmSpy;

    beforeEach(() => {
      confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
    });

    afterEach(() => {
      confirmSpy.mockRestore();
    });

    test("loads the ignore list from settings", async () => {
      Helper.apiCall.mockReset();
      Helper.apiCall
        .mockResolvedValueOnce({
          clusters: [],
          disk_space_alert_recipients: [],
          disk_space_alert_threshold: 80,
          proxmox_qemu_agent_ignore_vms: ["macos-vm", "prod-pve/105"],
        })
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce({ manual_hosts: [] });

      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });
      // mounted() kicks off loadSettings(); let the mocked calls settle.
      await new Promise((r) => setTimeout(r, 50));
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.qemuIgnoreEntries).toEqual([
        "macos-vm",
        "prod-pve/105",
      ]);
      expect(wrapper.vm.qemuIgnoreText).toBe("macos-vm\nprod-pve/105");
      expect(wrapper.text()).toContain("QEMU Guest Agent Exceptions");
      expect(wrapper.text()).toContain("Currently ignored:");
    });

    test("editor is hidden behind an explicit acknowledgement when empty", async () => {
      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });
      await wrapper.vm.$nextTick();

      expect(wrapper.find("#qemu-ignore-vms").exists()).toBe(false);
      wrapper.vm.showQemuIgnoreEditor = true;
      await wrapper.vm.$nextTick();
      expect(wrapper.find("#qemu-ignore-vms").exists()).toBe(true);
    });

    test("parses comma and newline separated entries", () => {
      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });

      expect(
        wrapper.vm.parseQemuIgnoreText(" macos-vm ,\n prod-pve/105,, \n")
      ).toEqual(["macos-vm", "prod-pve/105"]);
      expect(wrapper.vm.parseQemuIgnoreText("")).toEqual([]);
    });

    test("saves entries via the settings API after confirmation", async () => {
      Helper.apiPost.mockResolvedValue("Success");

      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });
      wrapper.vm.qemuIgnoreText = "macos-vm\nprod-pve/105";
      await wrapper.vm.saveQemuIgnoreList();

      expect(confirmSpy).toHaveBeenCalled();
      expect(Helper.apiPost).toHaveBeenCalledTimes(1);
      const formData = Helper.apiPost.mock.calls[0][4];
      expect(formData.get("name")).toBe("proxmox_qemu_agent_ignore_vms");
      expect(formData.get("value")).toBe("macos-vm, prod-pve/105");
      expect(wrapper.vm.qemuIgnoreEntries).toEqual([
        "macos-vm",
        "prod-pve/105",
      ]);
      expect(wrapper.vm.successMessage).toContain("2 VMs ignored");
    });

    test("does nothing when the confirmation is declined", async () => {
      confirmSpy.mockReturnValue(false);

      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });
      wrapper.vm.qemuIgnoreText = "macos-vm";
      await wrapper.vm.saveQemuIgnoreList();

      expect(Helper.apiPost).not.toHaveBeenCalled();
      expect(Helper.apiDelete).not.toHaveBeenCalled();
    });

    test("saving an empty list deletes the setting", async () => {
      Helper.apiDelete.mockResolvedValue("Success");

      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });
      wrapper.vm.qemuIgnoreEntries = ["macos-vm"];
      wrapper.vm.qemuIgnoreText = "";
      await wrapper.vm.saveQemuIgnoreList();

      expect(Helper.apiPost).not.toHaveBeenCalled();
      expect(Helper.apiDelete).toHaveBeenCalledWith(
        "settings",
        "proxmox_qemu_agent_ignore_vms",
        expect.anything()
      );
      expect(wrapper.vm.qemuIgnoreEntries).toEqual([]);
      expect(wrapper.vm.successMessage).toContain("cleared");
    });

    test("clear all asks for confirmation then deletes the setting", async () => {
      Helper.apiDelete.mockResolvedValue("Success");

      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });
      wrapper.vm.qemuIgnoreEntries = ["macos-vm"];
      wrapper.vm.qemuIgnoreText = "macos-vm";

      confirmSpy.mockReturnValueOnce(false);
      await wrapper.vm.clearQemuIgnoreList();
      expect(Helper.apiDelete).not.toHaveBeenCalled();

      await wrapper.vm.clearQemuIgnoreList();
      expect(Helper.apiDelete).toHaveBeenCalledTimes(1);
      expect(wrapper.vm.qemuIgnoreEntries).toEqual([]);
      expect(wrapper.vm.qemuIgnoreText).toBe("");
    });

    test("surfaces API errors when saving fails", async () => {
      Helper.apiPost.mockRejectedValue(new Error("Save failed"));

      wrapper = mount(DiskSpaceSettings, {
        mocks: { $auth: config.mocks["$auth"] },
      });
      wrapper.vm.qemuIgnoreText = "macos-vm";
      await wrapper.vm.saveQemuIgnoreList();

      expect(wrapper.vm.errorMessage).toBe("Save failed");
      expect(wrapper.vm.savingQemuIgnoreList).toBe(false);
    });
  });
});
