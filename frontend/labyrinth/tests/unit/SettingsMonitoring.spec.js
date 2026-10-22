import { shallowMount } from "@vue/test-utils";
import Monitoring from "@/views/Settings/Monitoring.vue";
import Helper from "@/helper";

jest.mock("@/helper", () => ({
  apiCall: jest.fn(),
  apiPost: jest.fn(),
}));

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("Settings/Monitoring.vue", () => {
  let wrapper;
  let commit;

  const mountMonitoring = () =>
    shallowMount(Monitoring, {
      mocks: { $auth: {}, $store: { commit } },
      stubs: ["font-awesome-icon"],
    });

  beforeEach(() => {
    jest.clearAllMocks();
    commit = jest.fn();
  });

  afterEach(() => {
    wrapper.destroy();
  });

  test("loads port_stale_hours on mount", async () => {
    Helper.apiCall.mockResolvedValue("8");
    wrapper = mountMonitoring();
    await flush();

    expect(Helper.apiCall).toHaveBeenCalledWith(
      "settings",
      "port_stale_hours",
      {}
    );
    expect(wrapper.vm.port_stale_hours).toBe("8");
    expect(commit).not.toHaveBeenCalled();
  });

  test("an unset setting (481) is not reported as an error", async () => {
    Helper.apiCall.mockRejectedValue({ status: 481 });
    wrapper = mountMonitoring();
    await flush();

    expect(wrapper.vm.port_stale_hours).toBe("");
    expect(commit).not.toHaveBeenCalled();
  });

  test("saving posts the value as the port_stale_hours setting", async () => {
    Helper.apiCall.mockResolvedValue("12");
    Helper.apiPost.mockResolvedValue("Success");
    wrapper = mountMonitoring();
    await flush();

    wrapper.vm.port_stale_hours = "6";
    wrapper.vm.savePortStaleHours();
    await flush();

    const formData = Helper.apiPost.mock.calls[0][4];
    expect(formData.get("name")).toBe("port_stale_hours");
    expect(formData.get("value")).toBe("6");
    expect(commit).toHaveBeenCalledWith("updateError", "Success");
  });
});
