import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import AwsSettings from "@/components/AWS/AwsSettings.vue";
import Helper from "@/helper";

Vue.use(BootstrapVue);

config.mocks["$auth"] = {
  profile: {
    name: "Test User",
    email: "test@example.com",
    picture: "test.jpg",
  },
  idToken: "test-token",
  login: jest.fn(),
  getAccessToken: jest.fn(() => Promise.resolve("access-token")),
};

jest.mock("@/helper", () => ({
  apiCall: jest.fn(),
  apiPost: jest.fn(),
  apiPut: jest.fn(),
  apiDelete: jest.fn(),
}));

describe("AwsSettings.vue", () => {
  let wrapper;

  beforeEach(() => {
    jest.clearAllMocks();
    Helper.apiCall.mockResolvedValue({ accounts: [] });
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", async () => {
    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".p-3").exists()).toBe(true);
    expect(wrapper.text()).toContain("Add AWS Account");
  });

  test("loads accounts on mount", async () => {
    Helper.apiCall.mockResolvedValue({
      accounts: [
        {
          _id: "123",
          name: "prod-account",
          region: "us-east-1",
          access_key_id: "AKIA123",
          updated: "2024-01-01",
        },
      ],
    });

    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 100));

    expect(Helper.apiCall).toHaveBeenCalled();
    expect(wrapper.vm.accounts.length).toBe(1);
    expect(wrapper.vm.accounts[0].name).toBe("prod-account");
  });

  test("displays success message on successful account creation", async () => {
    Helper.apiPost.mockResolvedValue({ status: "created" });
    Helper.apiCall.mockResolvedValue({
      accounts: [
        {
          _id: "123",
          name: "new-account",
          region: "us-west-2",
          access_key_id: "AKIA456",
        },
      ],
    });

    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.form = {
      name: "new-account",
      region: "us-west-2",
      access_key_id: "AKIA456",
      secret_access_key: "secret123",
      session_token: "",
    };

    await wrapper.vm.addAccount();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.successMessage).toContain("added successfully");
    expect(Helper.apiPost).toHaveBeenCalled();
  });

  test("displays error on failed account creation", async () => {
    Helper.apiPost.mockRejectedValue(new Error("Network error"));

    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.form = {
      name: "test",
      region: "us-east-1",
      access_key_id: "AKIA123",
      secret_access_key: "secret",
      session_token: "",
    };

    await wrapper.vm.addAccount();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.errorMessage).toContain("Network error");
  });

  test("validates required fields before adding account", async () => {
    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.form = {
      name: "",
      region: "",
      access_key_id: "",
      secret_access_key: "",
      session_token: "",
    };

    await wrapper.vm.addAccount();

    expect(wrapper.vm.errorMessage).toContain("required fields");
    expect(Helper.apiPost).not.toHaveBeenCalled();
  });

  test("edits an existing account", async () => {
    Helper.apiPut.mockResolvedValue({ status: "updated" });
    Helper.apiCall.mockResolvedValue({
      accounts: [
        {
          _id: "123",
          name: "updated-account",
          region: "us-west-1",
          access_key_id: "AKIA789",
        },
      ],
    });

    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.editingAccountId = "123";
    wrapper.vm.form = {
      name: "updated-account",
      region: "us-west-1",
      access_key_id: "AKIA789",
      secret_access_key: "new-secret",
      session_token: "token",
    };

    await wrapper.vm.saveAccountEdit();
    await wrapper.vm.$nextTick();

    expect(Helper.apiPut).toHaveBeenCalled();
    expect(wrapper.vm.successMessage).toContain("updated successfully");
  });

  test("deletes an account with confirmation", async () => {
    global.confirm = jest.fn(() => true);
    Helper.apiDelete.mockResolvedValue({ status: "deleted" });
    Helper.apiCall.mockResolvedValue({ accounts: [] });

    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.deleteAccount("123");
    await wrapper.vm.$nextTick();

    expect(global.confirm).toHaveBeenCalled();
    expect(Helper.apiDelete).toHaveBeenCalledWith(
      "aws/accounts",
      "123",
      config.mocks["$auth"]
    );
    expect(wrapper.vm.successMessage).toContain("deleted successfully");
  });

  test("cancels account deletion if not confirmed", async () => {
    global.confirm = jest.fn(() => false);

    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.deleteAccount("123");

    expect(Helper.apiDelete).not.toHaveBeenCalled();
  });

  test("resets form when cancel button is clicked", async () => {
    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.editingAccountId = "123";
    wrapper.vm.form.name = "edited-name";
    wrapper.vm.successMessage = "Test success";

    await wrapper.vm.resetForm();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.editingAccountId).toBe(null);
    expect(wrapper.vm.form.name).toBe("");
    expect(wrapper.vm.successMessage).toBe("");
  });

  test("displays account list in table", async () => {
    Helper.apiCall.mockResolvedValue({
      accounts: [
        {
          _id: "123",
          name: "prod-account",
          region: "us-east-1",
          access_key_id: "AKIA123",
          created: "2024-01-01",
        },
      ],
    });

    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadAccounts();
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 100));

    expect(wrapper.vm.accounts.length).toBe(1);
    expect(wrapper.text()).toContain("prod-account");
  });

  test("parseMaybeJSON handles string and object input", () => {
    wrapper = mount(AwsSettings, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const jsonString = '{"accounts":[]}';
    const result1 = wrapper.vm.parseMaybeJSON(jsonString);
    expect(result1.accounts).toEqual([]);

    const obj = { accounts: [] };
    const result2 = wrapper.vm.parseMaybeJSON(obj);
    expect(result2.accounts).toEqual([]);
  });
});
