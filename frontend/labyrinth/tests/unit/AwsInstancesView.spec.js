import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import AwsInstancesView from "@/components/AWS/AwsInstancesView.vue";
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
}));

describe("AwsInstancesView.vue", () => {
  let wrapper;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("renders component correctly", async () => {
    Helper.apiCall.mockResolvedValue({
      instances: [],
      account_errors: [],
      summary: {
        account_count: 0,
        instance_count: 0,
        matched_instance_count: 0,
        unmatched_instance_count: 0,
      },
    });

    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".p-3").exists()).toBe(true);
    expect(wrapper.text()).toContain("EC2 Inventory");
  });

  test("displays instances loaded from API", async () => {
    Helper.apiCall.mockResolvedValue({
      instances: [
        {
          instance_id: "i-123456",
          name: "web-server",
          account_name: "prod",
          region: "us-east-1",
          state: "running",
          private_ip: "10.0.0.5",
          public_ip: "203.0.113.5",
          matched: true,
          monitoring_enabled: true,
          labyrinth_matches: [
            {
              ip: "10.0.0.5",
              host: "web-server-01",
              match_reasons: ["IP match"],
            },
          ],
          tags: { Name: "web-server", Env: "prod" },
        },
      ],
      account_errors: [],
      summary: {
        account_count: 1,
        instance_count: 1,
        matched_instance_count: 1,
        unmatched_instance_count: 0,
      },
    });

    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadInstances();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.instances.length).toBe(1);
    expect(wrapper.vm.instances[0].name).toBe("web-server");
    expect(wrapper.vm.summary.instance_count).toBe(1);
  });

  test("displays error when API call fails", async () => {
    Helper.apiCall.mockRejectedValue(new Error("API Error"));

    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadInstances();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.errorMessage).toContain("API Error");
  });

  test("displays account errors from API response", async () => {
    Helper.apiCall.mockResolvedValue({
      instances: [],
      account_errors: [
        {
          account_name: "staging",
          region: "us-west-2",
          error: "Invalid credentials",
        },
      ],
      summary: {
        account_count: 0,
        instance_count: 0,
        matched_instance_count: 0,
        unmatched_instance_count: 0,
      },
    });

    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadInstances();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.accountErrors.length).toBe(1);
    expect(wrapper.vm.accountErrors[0].account_name).toBe("staging");
  });

  test("stateVariant returns correct variant for instance state", () => {
    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    expect(wrapper.vm.stateVariant("running")).toBe("success");
    expect(wrapper.vm.stateVariant("stopped")).toBe("secondary");
    expect(wrapper.vm.stateVariant("terminated")).toBe("danger");
    expect(wrapper.vm.stateVariant("unknown")).toBe("warning");
  });

  test("formatTags converts tag object to array", () => {
    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const tags = { Name: "web-server", Env: "prod", Team: "backend" };
    const formatted = wrapper.vm.formatTags(tags);

    expect(formatted.length).toBe(3);
    expect(formatted).toContainEqual({ key: "Name", value: "web-server" });
    expect(formatted).toContainEqual({ key: "Env", value: "prod" });
  });

  test("monitoringDetails returns correct status text", () => {
    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    const monitored = {
      monitoring_enabled: true,
      labyrinth_matches: [{ host: "server-01" }],
    };
    expect(wrapper.vm.monitoringDetails(monitored)).toContain("Monitored");

    const notMonitored = {
      monitoring_enabled: false,
      labyrinth_matches: [{ host: "server-01" }],
    };
    expect(wrapper.vm.monitoringDetails(notMonitored)).toContain(
      "Not monitored"
    );
  });

  test("refresh button is disabled while loading", async () => {
    Helper.apiCall.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                instances: [],
                account_errors: [],
                summary: {
                  account_count: 0,
                  instance_count: 0,
                  matched_instance_count: 0,
                  unmatched_instance_count: 0,
                },
              }),
            100
          )
        )
    );

    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    wrapper.vm.loadInstances();
    await wrapper.vm.$nextTick();

    const refreshButton = wrapper.find("button");
    expect(refreshButton.attributes("disabled")).toBe("disabled");
  });

  test("displays summary statistics", async () => {
    Helper.apiCall.mockResolvedValue({
      instances: [],
      account_errors: [],
      summary: {
        account_count: 2,
        instance_count: 5,
        matched_instance_count: 3,
        unmatched_instance_count: 2,
      },
    });

    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadInstances();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.summary.account_count).toBe(2);
    expect(wrapper.vm.summary.instance_count).toBe(5);
    expect(wrapper.vm.summary.matched_instance_count).toBe(3);
  });

  test("displays empty state when no instances", async () => {
    Helper.apiCall.mockResolvedValue({
      instances: [],
      account_errors: [],
      summary: {
        account_count: 0,
        instance_count: 0,
        matched_instance_count: 0,
        unmatched_instance_count: 0,
      },
    });

    wrapper = mount(AwsInstancesView, {
      mocks: { $auth: config.mocks["$auth"] },
    });

    await wrapper.vm.loadInstances();
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("No EC2 instances found");
  });
});
