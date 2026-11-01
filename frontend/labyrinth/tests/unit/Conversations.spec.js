import { config, shallowMount } from "@vue/test-utils";
import Vue from "vue";
import store from "@/store";
import Instance from "@/views/Conversations.vue";
import Helper from "@/helper";

Vue.use(store);

config.mocks["$auth"] = {
  profile: { name: "Test Name", picture: "Test.jpg" },
  idToken: 1,
  login: function () {},
  getAccessToken: function () {},
};

let wrapper;

const conversation = {
  conversation_id: "c1",
  title: "Patch web01",
  status: "open",
  needs_human: true,
  pending: [
    { type: "deploy", id: "r-new" },
    { type: "question", id: "m2" },
  ],
  messages: [],
  requests: {
    "r-new": { generated: true, runs: [] },
    "r-closed": { runs: [] },
    "r-declined": { declined_at: "2026-10-31T00:00:00+00:00", runs: [] },
    "r-running": { runs: [{ status: "running" }] },
    "r-ok": {
      runs: [
        { status: "completed", outcome: "failed" },
        { status: "completed", outcome: "success" },
      ],
    },
    "r-failed": { runs: [{ status: "error", outcome: "failed" }] },
  },
};

function mountAt(params) {
  jest.spyOn(Helper, "apiCall").mockResolvedValue([]);
  return shallowMount(Instance, {
    store,
    mocks: { $route: { params } },
    stubs: ["font-awesome-icon", "router-link", "b-container", "b-spinner"],
  });
}

afterEach(() => {
  wrapper.destroy();
  jest.restoreAllMocks();
});

describe("Conversations.vue", () => {
  test("conversation badges", () => {
    wrapper = mountAt({});
    expect(
      wrapper.vm.stateOf({ status: "closed", needs_human: true }).label
    ).toBe("Closed");
    expect(
      wrapper.vm.stateOf({ status: "open", needs_human: true }).label
    ).toBe("Needs you");
    expect(
      wrapper.vm.stateOf({ status: "open", needs_human: false }).label
    ).toBe("Open");
  });

  test("staged deployment states follow the latest run", () => {
    wrapper = mountAt({ id: "c1" });
    wrapper.vm.conversation = conversation;
    const label = (id) => wrapper.vm.requestState(id).label;
    expect(label("r-new")).toBe("Waiting for your vault password");
    // Not pending any more (the conversation was closed) and never launched
    expect(label("r-closed")).toBe("Not deployed");
    expect(label("r-declined")).toBe("Declined");
    expect(label("r-running")).toBe("Running");
    expect(label("r-ok")).toBe("Succeeded");
    expect(label("r-failed")).toBe("Failed");

    expect(wrapper.vm.isPending("deploy", "r-new")).toBe(true);
    expect(wrapper.vm.isPending("deploy", "r-ok")).toBe(false);
    expect(wrapper.vm.isPending("question", "m2")).toBe(true);
  });

  test("list previews and run stats", () => {
    wrapper = mountAt({});
    expect(wrapper.vm.preview(null)).toBe("");
    expect(
      wrapper.vm.preview({
        author: "agent",
        kind: "question",
        text: "OK tonight?",
      })
    ).toBe("Agent: OK tonight?");
    expect(
      wrapper.vm.preview({ author: "agent", kind: "deploy", playbook: "patch" })
    ).toBe("Agent: Staged deploy of patch.yml");
    expect(
      wrapper.vm.preview({ author: "system", kind: "run", text: "Run failed" })
    ).toBe("Ansible: Run failed");
    // Whatever was said with an action follows its label
    expect(
      wrapper.vm.preview({ author: "agent", kind: "closed", text: "All done" })
    ).toBe("Agent: Closed: All done");
    expect(
      wrapper.vm.preview({ author: "human", kind: "launched", text: "" })
    ).toBe("You: Run launched");
    expect(
      wrapper.vm.statsSummary({
        ok: { a: 3, b: 2 },
        changed: { a: 1 },
        failures: { b: 1 },
        dark: {},
      })
    ).toBe("5 ok, 1 changed, 1 failed");
  });

  test("the route picks the list or one conversation", () => {
    wrapper = mountAt({ id: "c1" });
    expect(wrapper.vm.conversation_id).toBe("c1");
    expect(Helper.apiCall).toHaveBeenCalledWith(
      "conversation",
      "c1",
      expect.anything()
    );
    wrapper.destroy();

    wrapper = mountAt({});
    expect(wrapper.vm.conversation_id).toBe("");
    expect(Helper.apiCall).toHaveBeenCalledWith(
      "conversations",
      "",
      expect.anything()
    );
  });
});
