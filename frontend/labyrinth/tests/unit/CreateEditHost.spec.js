// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Instance from "@/components/CreateEditHost.vue";

import Vuelidate from "vuelidate";

Vue.use(store);
Vue.use(Vuelidate);

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
  wrapper = shallowMount(Instance, {
    propsData: {
      inpHost: "",

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
      "b-input",
      "b-row",
      "b-col",
      "b-form-checkbox",
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

describe("CreateEditHost.vue", () => {
  test("is a Vue instance", () => {
    expect(wrapper.isVueInstance).toBeTruthy();
  });
  test("inp_host", async () => {
    wrapper.vm.loadMetrics = () => {};
    wrapper.setProps({
      inp_host: "TEST",
    });
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.isNew).toBe(false);
    expect(wrapper.vm.$data.host).toBe("TEST");

    // Creates a new host
    wrapper.setProps({
      inp_host: "",
    });
    await wrapper.vm.$forceUpdate();
    expect(wrapper.vm.$data.isNew).toBe(true);
    expect(wrapper.vm.$data.host).toStrictEqual(wrapper.vm.$data.safe_host);
    expect(wrapper.vm.$data.metrics).toStrictEqual([]);
  });

  test("cloneHost", async () => {
    wrapper.setData({
      isNew: false,
      host: {
        _id: "abc123",
        ip: "192.168.1.10",
        mac: "aa:bb:cc:dd:ee:ff",
        subnet: "192.168.1",
        host: "test-server",
        services: [{ name: "ssh", state: true }],
        group: "servers",
      },
      metrics: [{ name: "cpu" }],
    });
    await wrapper.vm.$forceUpdate();

    wrapper.vm.cloneHost();
    await wrapper.vm.$forceUpdate();

    expect(wrapper.vm.$data.isNew).toBe(true);
    expect(wrapper.vm.$data.host._id).toBeUndefined();
    expect(wrapper.vm.$data.host.ip).toBe("");
    expect(wrapper.vm.$data.host.mac).toBe("");
    expect(wrapper.vm.$data.host.subnet).toBe("192.168.1");
    expect(wrapper.vm.$data.host.host).toBe("test-server");
    expect(wrapper.vm.$data.host.services).toStrictEqual([
      { name: "ssh", state: true },
    ]);
    expect(wrapper.vm.$data.metrics).toStrictEqual([]);
  });
});

describe("CreateEditHost.vue ingest counters", () => {
  const sampleIngest = {
    found: true,
    client_id: "02:42:AC:13:00:02",
    requests: 120,
    metrics: 4800,
    last_batch: 40,
    last_seen: 1753988580,
    skipped: 0,
    window_minutes: 60,
    requests_last_hour: 12,
    metrics_last_hour: 440,
    per_minute: [
      { minute: 1, timestamp: 60, requests: 0, metrics: 0 },
      { minute: 2, timestamp: 120, requests: 2, metrics: 40 },
      { minute: 3, timestamp: 180, requests: 10, metrics: 400 },
    ],
  };

  test("ingestId prefers the MAC and falls back to the IP", () => {
    wrapper.vm.$data.host = { mac: "AA:BB", ip: "1.2.3.4" };
    expect(wrapper.vm.ingestId()).toBe("AA:BB");

    wrapper.vm.$data.host = { mac: "", ip: "1.2.3.4" };
    expect(wrapper.vm.ingestId()).toBe("1.2.3.4");

    wrapper.vm.$data.host = {};
    expect(wrapper.vm.ingestId()).toBe("");
  });

  test("ingestPeak is the busiest minute", async () => {
    wrapper.vm.$data.ingest = sampleIngest;
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.ingestPeak).toBe(10);
  });

  test("ingestPeak is zero with no history", async () => {
    wrapper.vm.$data.ingest = { found: false, per_minute: [] };
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.ingestPeak).toBe(0);
  });

  test("bucketHeight scales against the peak and floors busy minutes", async () => {
    wrapper.vm.$data.ingest = sampleIngest;
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.bucketHeight(sampleIngest.per_minute[2])).toBe("100%");
    expect(wrapper.vm.bucketHeight(sampleIngest.per_minute[1])).toBe("20%");
    // Empty minutes collapse, so the sparkline shows real gaps.
    expect(wrapper.vm.bucketHeight(sampleIngest.per_minute[0])).toBe("0%");
    expect(wrapper.vm.bucketHeight(undefined)).toBe("0%");
  });

  test("bucketHeight never renders a busy minute as a gap", async () => {
    wrapper.vm.$data.ingest = {
      found: true,
      per_minute: [
        { minute: 1, timestamp: 60, requests: 1, metrics: 1 },
        { minute: 2, timestamp: 120, requests: 500, metrics: 5000 },
      ],
    };
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.bucketHeight({ requests: 1 })).toBe("4%");
  });

  test("bucketTitle describes the minute", () => {
    const title = wrapper.vm.bucketTitle({
      timestamp: 60,
      requests: 2,
      metrics: 40,
    });
    expect(title).toContain("2 request(s)");
    expect(title).toContain("40 metric(s)");
    expect(wrapper.vm.bucketTitle(undefined)).toBe("");
  });

  test("rates average over the minutes that actually reported", async () => {
    wrapper.vm.$data.ingest = sampleIngest;
    await wrapper.vm.$nextTick();

    // 12 requests and 440 metrics across the 2 non-empty minutes.
    expect(wrapper.vm.ingestRequestsPerMinute).toBe(6);
    expect(wrapper.vm.ingestMetricsPerMinute).toBe(220);
  });

  test("rates are zero before anything is recorded", async () => {
    wrapper.vm.$data.ingest = { found: false, per_minute: [] };
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.ingestRequestsPerMinute).toBe(0);
    expect(wrapper.vm.ingestMetricsPerMinute).toBe(0);
  });

  test("ingestLastSeen reports never when nothing has arrived", async () => {
    wrapper.vm.$data.ingest = { found: false, per_minute: [] };
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.ingestLastSeen).toBe("never");

    wrapper.vm.$data.ingest = sampleIngest;
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.ingestLastSeen).toMatch(
      /^\d{4}-\d{2}-\d{2} \d+:\d+:\d+$/
    );
  });

  test("switching to a new host clears the counters", async () => {
    wrapper.vm.loadMetrics = () => {};
    wrapper.vm.$data.ingest = sampleIngest;

    wrapper.setProps({ inp_host: "" });
    await wrapper.vm.$forceUpdate();

    expect(wrapper.vm.$data.ingest.found).toBe(false);
    expect(wrapper.vm.$data.ingest.per_minute).toStrictEqual([]);
  });
});
