import { shallowMount } from "@vue/test-utils";
import Instance from "@/components/UnifiSettings.vue";

jest.mock("@/helper", () => {
  const actual = jest.requireActual("@/helper").default;
  return {
    ...actual,
    apiCall: jest.fn(() => new Promise(() => {})),
  };
});

const controller = {
  _id: "1",
  name: "HQ console",
  url: "https://10.0.0.1",
  auth: "api_key",
  has_api_key: true,
  has_password: false,
  protect: true,
  add_devices: true,
  verify_ssl: false,
  sites: [
    { site: "default", location: "HQ", monitor: true },
    { site: "lab", location: "", monitor: false },
  ],
};

const status = {
  controllers: [
    {
      _id: "1",
      sites: [
        { site: "default", name: "Default" },
        { site: "lab", name: "Lab" },
        { site: "new", name: "New site" },
      ],
    },
  ],
};

let wrapper;

beforeEach(() => {
  wrapper = shallowMount(Instance, {
    propsData: { status: { controllers: [] } },
    mocks: { $auth: {}, $store: { commit: jest.fn() } },
    stubs: [
      "b-row",
      "b-col",
      "b-card",
      "b-card-title",
      "b-form",
      "b-form-group",
      "b-input",
      "b-form-radio-group",
      "b-form-checkbox",
      "b-button",
      "b-alert",
      "b-select",
    ],
  });
});

afterEach(() => {
  wrapper.destroy();
});

describe("UnifiSettings.vue", () => {
  test("each site the controller reported gets its saved location, new ones monitored", async () => {
    wrapper.setData({ controllers: [controller], locations: [{ name: "HQ" }] });
    await wrapper.setProps({ status: status });
    expect(wrapper.vm.sites["1"]).toStrictEqual([
      { site: "default", name: "Default", location: "HQ", monitor: true },
      { site: "lab", name: "Lab", location: "", monitor: false },
      { site: "new", name: "New site", location: "", monitor: true },
    ]);
    expect(wrapper.vm.location_options).toStrictEqual([
      { value: "", text: "No location" },
      "HQ",
    ]);
  });

  test("the form is checked before saving", () => {
    let check = (fields) => {
      wrapper.setData({ form: { ...wrapper.vm.form, ...fields } });
      return wrapper.vm.form_problem;
    };
    expect(check({ name: " " })).toBe("Give it a name.");
    expect(check({ name: "HQ", url: "10.0.0.1" })).toBe(
      "The URL is just the address, like https://192.168.1.1"
    );
    expect(check({ url: "https://10.0.0.1/manage" })).toBe(
      "The URL is just the address, like https://192.168.1.1"
    );
    expect(check({ url: "https://unifi.example.com:8443/" })).toBe(
      "Enter the API key."
    );
    expect(check({ api_key: "KEY" })).toBe("");
    expect(check({ auth: "login", username: "viewer" })).toBe(
      "Enter the local account's username and password."
    );
    expect(check({ password: "secret" })).toBe("");
  });

  test("editing keeps saved secrets out of the form", () => {
    wrapper.vm.edit(controller);
    expect(wrapper.vm.form._id).toBe("1");
    expect(wrapper.vm.form.api_key).toBe("");
    // The saved key is kept, so the form is complete without one
    expect(wrapper.vm.form_problem).toBe("");
    wrapper.vm.resetForm();
    expect(wrapper.vm.form._id).toBe("");
  });
});
