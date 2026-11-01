import { shallowMount } from "@vue/test-utils";
import Notifications from "@/views/Settings/Notifications.vue";
import Helper from "@/helper";

jest.mock("@/helper", () => ({
  apiCall: jest.fn(),
  apiPost: jest.fn(),
}));

const flush = () => new Promise((r) => setTimeout(r, 0));

const defaults = {
  enabled: true,
  first_minutes: 60,
  multiplier: 2,
  max_hours: 24,
};

describe("Settings/Notifications.vue", () => {
  let wrapper;
  let commit;

  const mountNotifications = async (saved) => {
    Helper.apiCall.mockResolvedValue(JSON.stringify(saved));
    wrapper = shallowMount(Notifications, {
      mocks: { $auth: {}, $store: { commit } },
    });
    await flush();
  };

  beforeEach(() => {
    jest.clearAllMocks();
    commit = jest.fn();
  });

  afterEach(() => {
    wrapper.destroy();
  });

  test("loads the saved settings and previews the reminder schedule", async () => {
    await mountNotifications(defaults);

    expect(Helper.apiCall).toHaveBeenCalledWith(
      "alert-backoff",
      "settings",
      {}
    );
    expect(wrapper.vm.settings).toEqual(defaults);
    expect(wrapper.vm.schedule).toBe(
      "1h, 3h, 7h, 15h, 31h, 55h, then every 24h"
    );
    expect(wrapper.text()).toContain("55h, then every 24h");
  });

  test("a multiplier of 1 previews a fixed interval", async () => {
    await mountNotifications({ ...defaults, first_minutes: 30, multiplier: 1 });
    expect(wrapper.vm.schedule).toBe("30m, then every 30m");
  });

  test("a schedule still growing after six reminders trails off", async () => {
    await mountNotifications({ ...defaults, first_minutes: 10, max_hours: 72 });
    expect(wrapper.vm.schedule).toBe("10m, 30m, 1.2h, 2.5h, 5.2h, 10.5h, ...");
  });

  test.each([
    [{ first_minutes: "" }, "more than 0 minutes"],
    [{ first_minutes: 0 }, "more than 0 minutes"],
    [{ multiplier: 0.5 }, "between 1 and 100"],
    [{ multiplier: 1000 }, "between 1 and 100"],
    [{ max_hours: 10000 }, "at most 8760 hours"],
    [{ first_minutes: 120, max_hours: 1 }, "can't be shorter"],
  ])("rejects %o before saving", async (change, message) => {
    await mountNotifications(defaults);
    Object.assign(wrapper.vm.settings, change);
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.error).toContain(message);
    expect(wrapper.text()).toContain(message);
  });

  test("saving posts the settings as JSON and shows what was stored", async () => {
    await mountNotifications(defaults);
    const stored = { ...defaults, enabled: false };
    Helper.apiPost.mockResolvedValue(JSON.stringify(stored));

    wrapper.vm.settings.enabled = false;
    wrapper.vm.save();
    await flush();

    const [url, service, command, , body] = Helper.apiPost.mock.calls[0];
    expect([url, service, command]).toEqual(["alert-backoff", "", "settings"]);
    expect(JSON.parse(body)).toEqual(stored);
    expect(wrapper.vm.settings).toEqual(stored);
    expect(wrapper.vm.saving).toBe(false);
    expect(commit).toHaveBeenCalledWith(
      "updateError",
      "Notification backoff saved"
    );
  });
});
