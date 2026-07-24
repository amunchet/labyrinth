import { config, mount } from "@vue/test-utils";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import AiAlerts from "@/views/Settings/AiAlerts.vue";
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
}));

const defaultSettings = {
  prompt: "Default prompt text",
  model: "gpt-5-mini",
  recipients: ["a@example.com", "b@example.com"],
  subject_template: "Labyrinth IT AI ALERT [{time}]",
  from_name: "Labyrinth AI",
};

describe("AiAlerts.vue", () => {
  let wrapper;

  beforeEach(() => {
    jest.clearAllMocks();
    Helper.apiCall.mockResolvedValue(defaultSettings);
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.destroy();
    }
  });

  test("loads settings on mount and populates the form", async () => {
    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    expect(Helper.apiCall).toHaveBeenCalledWith(
      "ai",
      "settings",
      config.mocks["$auth"]
    );
    expect(wrapper.vm.prompt).toBe("Default prompt text");
    expect(wrapper.vm.model).toBe("gpt-5-mini");
    expect(wrapper.vm.recipientsText).toBe("a@example.com, b@example.com");
    expect(wrapper.vm.subjectTemplate).toBe("Labyrinth IT AI ALERT [{time}]");
    expect(wrapper.vm.fromName).toBe("Labyrinth AI");
  });

  test("loadSettings handles a JSON string response", async () => {
    Helper.apiCall.mockResolvedValue(JSON.stringify(defaultSettings));

    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    expect(wrapper.vm.model).toBe("gpt-5-mini");
  });

  test("save posts the form fields and reloads returned settings", async () => {
    Helper.apiPost.mockResolvedValue({
      ...defaultSettings,
      model: "gpt-4.1-mini",
    });

    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    wrapper.vm.prompt = "Updated prompt";
    wrapper.vm.model = "gpt-4.1-mini";
    wrapper.vm.recipientsText = "ops@example.com";
    wrapper.vm.subjectTemplate = "Custom [{time}]";
    wrapper.vm.fromName = "Custom Bot";

    await wrapper.vm.save();

    expect(Helper.apiPost).toHaveBeenCalledWith(
      "ai/settings",
      "",
      "",
      config.mocks["$auth"],
      JSON.stringify({
        prompt: "Updated prompt",
        model: "gpt-4.1-mini",
        recipients: "ops@example.com",
        subject_template: "Custom [{time}]",
        from_name: "Custom Bot",
      })
    );
    expect(wrapper.vm.model).toBe("gpt-4.1-mini");
    expect(wrapper.vm.successMessage).toContain("saved successfully");
  });

  test("save surfaces an error message on failure", async () => {
    Helper.apiPost.mockRejectedValue(new Error("Network error"));

    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    await wrapper.vm.save();

    expect(wrapper.vm.errorMessage).toContain("Network error");
    expect(wrapper.vm.saving).toBe(false);
  });

  test("loadSettings surfaces an error message on failure", async () => {
    Helper.apiCall.mockRejectedValue(new Error("boom"));

    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    expect(wrapper.vm.errorMessage).toContain("boom");
  });

  test("parseMaybeJSON handles string and object input", async () => {
    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();

    const jsonString = '{"model":"gpt-5-mini"}';
    expect(wrapper.vm.parseMaybeJSON(jsonString).model).toBe("gpt-5-mini");

    const obj = { model: "gpt-5-mini" };
    expect(wrapper.vm.parseMaybeJSON(obj).model).toBe("gpt-5-mini");
  });

  test("renders the AI Alerts heading and fields", async () => {
    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    expect(wrapper.text()).toContain("AI Alerts");
    expect(wrapper.find("#ai-prompt").exists()).toBe(true);
    expect(wrapper.find("#ai-model").exists()).toBe(true);
    expect(wrapper.find("#ai-recipients").exists()).toBe(true);
    expect(wrapper.find("#ai-subject-template").exists()).toBe(true);
    expect(wrapper.find("#ai-from-name").exists()).toBe(true);
  });

  test("sendTestEmail requires a recipient before calling the API", async () => {
    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    wrapper.vm.recipientsText = "";
    await wrapper.vm.sendTestEmail("simple");

    expect(wrapper.vm.errorMessage).toContain("Enter at least one recipient");
    expect(Helper.apiPost).not.toHaveBeenCalled();
  });

  test("sendTestEmail simple mode posts recipients and shows success", async () => {
    Helper.apiPost.mockResolvedValue({ status: "sent", mode: "simple" });

    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    wrapper.vm.recipientsText = "a@example.com, b@example.com";
    await wrapper.vm.sendTestEmail("simple");

    expect(Helper.apiPost).toHaveBeenCalledWith(
      "ai/test-email",
      "",
      "",
      config.mocks["$auth"],
      JSON.stringify({
        mode: "simple",
        recipients: ["a@example.com", "b@example.com"],
      })
    );
    expect(wrapper.vm.successMessage).toContain("Test email sent");
    expect(wrapper.vm.sendingSimpleTest).toBe(false);
  });

  test("sendTestEmail full mode reports the AI verdict on success", async () => {
    Helper.apiPost.mockResolvedValue({
      status: "sent",
      mode: "full",
      wake_up_it_director: true,
      host_alerts_count: 2,
    });

    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    wrapper.vm.recipientsText = "a@example.com";
    await wrapper.vm.sendTestEmail("full");

    expect(wrapper.vm.successMessage).toContain("wake_up_it_director: true");
    expect(wrapper.vm.successMessage).toContain("2 host alert(s)");
    expect(wrapper.vm.sendingFullTest).toBe(false);
  });

  test("sendTestEmail surfaces an error message on failure", async () => {
    Helper.apiPost.mockRejectedValue(new Error("boom"));

    wrapper = mount(AiAlerts, {
      mocks: { $auth: config.mocks["$auth"] },
    });
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 0));

    wrapper.vm.recipientsText = "a@example.com";
    await wrapper.vm.sendTestEmail("simple");

    expect(wrapper.vm.errorMessage).toContain("boom");
    expect(wrapper.vm.sendingSimpleTest).toBe(false);
  });
});
