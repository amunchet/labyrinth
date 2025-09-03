<template>
  <b-container style="min-width: 90%" class="mt-3">
    <b-modal
      id="test_configuration_file"
      title="Test Configuration File"
      size="lg"
    >
      <div class="ml-1 mr-1">
        <b-row>
          <b-col>
            Selected Host: <b>{{ selected_host }}</b>
          </b-col>
        </b-row>
        <b-row>
          <b-col>
            <div>
              <b-button
                variant="warning"
                class="mb-2 float-right"
                v-if="!saving_conf"
                @click="saveRaw()"
              >
                <font-awesome-icon icon="save" size="1x" />
              </b-button>
              <b-spinner class="float-right mb-2" v-else />
            </div>
            <b-textarea v-model="loadedFile" />
          </b-col>
        </b-row>
        <b-row class="mt-2">
          <b-col class="text-center">
            <b-button variant="success" @click="runTest(0)"
              >Test with NO outputs</b-button
            >
          </b-col>
          <b-col class="text-center">
            <b-button variant="warning" @click="runTest(1)"
              >Test WITH outputs</b-button
            >
          </b-col>
        </b-row>
        <hr />
        <b-row class="mt-2">
          <b-col>
            <div
              class="testOutput"
              v-html="$sanitize(testOutput).replace('\n', '<br />')"
            ></div>
          </b-col>
        </b-row>
      </div>
    </b-modal>

    <b-row>
      <b-col cols="6" class="border-right">
        <h4 class="text-left">Available Telegraf Services</h4>

        <b-row>
          <b-col>
            <b-form-input
              placeholder="Search (press tab to filter)"
              v-model="temp_filter"
              @blur="service_filter = temp_filter"
            ></b-form-input>
          </b-col>
          <b-col cols="5">
            <b-button
              variant="primary"
              @click="putStructure()"
              class="float-right"
            >
              Save Schema Changes
            </b-button>
          </b-col>
        </b-row>
        <hr />
        <div v-if="loaded">
          <ServiceComponent
            v-for="(section, idx) in data"
            v-bind:key="idx"
            :name="idx"
            :inp_data="section"
            :start_minimized="true"
            :isParent="true"
            :service_filter="service_filter"
            @add="add"
            depth="0"
          />
        </div>
        <b-spinner class="m-2" v-else />
      </b-col>
      <b-col class="ml-1">
        <b-row>
          <b-col class="text-left"><h4>Configuration File</h4></b-col>
          <b-col>
            <v-select
              v-model="selected_host"
              :options="hosts"
              label="text"
              :reduce="(x) => x.value"
            />
          </b-col>
          <b-col cols="1"
            ><b-button
              v-if="!saving_conf"
              variant="success"
              class="float-right"
              @click="saveConf()"
            >
              <font-awesome-icon icon="save" size="1x" />
            </b-button>
            <b-spinner v-else />
          </b-col> </b-row
        ><b-row class="mt-1">
          <b-col
            ><b-button
              class="float-left"
              variant="primary"
              v-if="selected_host && hasBeenSaved"
              @click="
                () => {
                  $bvModal.show('test_configuration_file');
                }
              "
              >Test Configuration File</b-button
            ></b-col
          >
        </b-row>
        <div class="overflow-hidden">
          <b-button
            class="float-right m-0 p-0 shadow-none"
            variant="link"
            @click="
              () => {
                output_data = {};
                this.loadSuggestedFields();
              }
            "
            >Clear All</b-button
          >
        </div>

        <hr />

        <div v-if="output_data && selected_host">
          <ServiceComponent
            v-for="(section, idx) in output_data"
            v-bind:key="idx"
            :name="idx"
            :inp_data="section"
            :start_minimized="true"
            :isParent="true"
            :isWrite="true"
            depth="0"
            @update="
              (name, val) => {
                output_data[name] = val;
                autoSave();
                $forceUpdate();
              }
            "
            @child_delete="
              (val) => {
                delete output_data[val];
                $forceUpdate();
              }
            "
          />
        </div>
        <div v-else>
          Please select a configuration file for a host from the dropdown.
        </div>
      </b-col>
    </b-row>
  </b-container>
</template>

<script>
import Helper from "@/helper";
import ServiceComponent from "@/components/Service";

export default {
  name: "Services",
  components: { ServiceComponent },

  data() {
    return {
      default_backend: "",
      telegraf_key: "",
      service_filter: "",
      saving_conf: false,
      output_data: {},
      temp_filter: "",
      data: [],
      loaded: false,
      autoSaved: false,
      selected_host: "",
      hosts: [],
      raw_hosts: [],
      hasBeenSaved: false,
      loadedFile: "",
      testOutput: "",
    };
  },

  watch: {
    // Load existing conf for selected host (skip TEST),
    // then (once) apply suggested fields.
    selected_host: /* istanbul ignore next */ async function (val) {
      try {
        if (val && val !== "TEST") {
          const res = await this.apiCall("load_service", val);
          if (res) this.output_data = res;
        }
      } catch (e) {
        /* apiCall already commits error */
      } finally {
        await this.loadSuggestedFields();
      }
    },
  },

  methods: {
    // ---------- DRY helpers (kill duplicate chunks) ----------
    async apiCall(name, arg = "") {
      try {
        return await Helper.apiCall(name, arg, this.$auth);
      } catch (e) {
        this.$store.commit("updateError", e);
        throw e;
      }
    },
    async apiPost(route, subpath, param, formData) {
      try {
        return await Helper.apiPost(route, subpath, param, this.$auth, formData);
      } catch (e) {
        this.$store.commit("updateError", e);
        throw e;
      }
    },
    async withSaving(fn) {
      this.saving_conf = true;
      try {
        return await fn();
      } finally {
        this.saving_conf = false;
      }
    },
    ensureOutputScaffold() {
      if (!this.output_data["global_tags"]) this.output_data["global_tags"] = {};
      if (!this.output_data["outputs"]) this.output_data["outputs"] = {};
    },
    buildHttpOutput() {
      return {
        url: this.default_backend,
        timeout: "5s",
        method: "POST",
        insecure_skip_verify: true,
        data_format: "json",
        content_encoding: "identity",
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          idle_conn_timeout: "0",
          Authorization: this.telegraf_key,
        },
      };
    },
    computeHostTags(host = {}) {
      const tag_names = ["mac", "host", "ip"];
      const tags = {};
      for (const k of tag_names) {
        const v = host?.[k];
        if (v) tags[k] = v;
      }
      return tags;
    },

    // ---------- Existing actions, now using helpers ----------
    add(data) {
      this.$forceUpdate();
      const output = JSON.parse(data);
      const item = output.item;
      const parent = output.parent.replace("undefined.", "") || "";
      const name = output.name;

      const temp = JSON.parse(JSON.stringify(this.output_data));
      this.output_data = ""; // force reactivity reset
      this.$forceUpdate();

      const set = (obj, path, val) => {
        const keys = path.split(".");
        const lastKey = keys.pop();
        const lastObj = keys.reduce((o, k) => (o[k] = o[k] || {}), obj);
        lastObj[lastKey] = val;
      };

      set(temp, `${parent}.${name}`, item);

      if (temp[""] !== undefined) {
        for (const next_key of Object.keys(temp[""])) {
          if (temp[next_key] === undefined) temp[next_key] = temp[""][next_key];
        }
        delete temp[""];
      }

      this.output_data = temp;
      this.loadSuggestedFields();
      this.$forceUpdate();
    },

    async loadDefaultBackendLocation() {
      try {
        this.default_backend = await this.apiCall("settings", "default_telegraf_backend");
      } catch (e) {
        // Keep prior behavior / messaging
        if (!e.status || e.status !== 481) {
          // already committed in apiCall
        } else {
          this.$store.commit(
            "updateError",
            "Error: Please update default backend location in Settings."
          );
        }
      }
    },

    async loadTelegrafKey() {
      this.telegraf_key = await this.apiCall("telegraf_key", "");
    },

    async loadSuggestedFields() {
      this.ensureOutputScaffold();

      if (!this.default_backend) await this.loadDefaultBackendLocation();
      if (!this.telegraf_key) await this.loadTelegrafKey();

      // outputs.http (canonicalized in one place)
      this.output_data["outputs"]["http"] = this.buildHttpOutput();

      // global_tags for selected host
      const found_host =
        this.raw_hosts.find((x) => x.ip === this.selected_host) || {};
      this.output_data["global_tags"] = this.computeHostTags(found_host);
    },

    async loadStructure() {
      this.data = await this.apiCall("redis", "get_structure");
      this.loaded = true;
    },

    async putStructure() {
      const res = await this.apiCall("redis", "put_structure");
      this.$store.commit("updateError", res);
    },

    async getAutosave() {
      try {
        this.output_data = await this.apiCall("redis", "autosave");
      } catch {
        this.output_data = {};
      }
    },

    async autoSave() {
      const formData = new FormData();
      formData.append("data", JSON.stringify(this.output_data));
      try {
        await this.apiPost("redis", "", "autosave", formData);
      } catch {
        this.autoSaved = false;
      }
    },

    async listHosts() {
      const res = await this.apiCall("hosts", "");
      this.raw_hosts = res;
      // Deduplicate IPs succinctly
      const seen = new Set();
      this.hosts = res.reduce((acc, x) => {
        const ip = (x.ip || "").trim();
        if (ip && !seen.has(ip)) {
          seen.add(ip);
          acc.push({ value: ip, text: ip });
        }
        return acc;
      }, []);
    },

    async loadFile() {
      this.loadedFile = await this.apiCall("load_service", `${this.selected_host}/text`);
    },

    async runTest(outputs) {
      this.testOutput = await this.apiCall("run_conf", `${this.selected_host}/${outputs}`);
    },

    async saveRaw() {
      await this.withSaving(async () => {
        const fd = new FormData();
        fd.append("raw", this.loadedFile);
        fd.append("data", "{}");
        const res = await this.apiPost("save_conf", "", this.selected_host, fd);
        this.$store.commit("updateError", res);
        // Refresh structured view to reflect saved raw
        const after = await this.apiCall("load_service", this.selected_host);
        this.output_data = after;
        await this.loadSuggestedFields();
      });
    },

    async saveConf() {
      await this.withSaving(async () => {
        const fd = new FormData();
        fd.append("data", JSON.stringify(this.output_data));
        const res = await this.apiPost("save_conf", "", this.selected_host, fd);
        this.hasBeenSaved = true;
        await this.loadFile(); // keep previous flow
        this.$store.commit("updateError", res);
      });
    },
  },

  mounted: /* istanbul ignore next */ async function () {
    try {
      this.loadStructure();
      this.getAutosave();
      this.listHosts();
      await this.loadDefaultBackendLocation();
      await this.loadTelegrafKey();
    } catch (e) {
      // apiCall already commits errors
      this.$store.commit("updateError", e);
    }
  },
};
</script>

<style lang="scss">
textarea {
  width: 100%;
  min-height: 400px;
}
h2 {
  width: 99%;
}
.testOutput b {
  color: red !important;
}

.testOutput {
  width: 100%;
  max-height: 400px;
  overflow: scroll;
  background-color: #efefed;
  padding: 1rem;
}
@media screen and (max-width: 991px) {
  .row {
    display: block;
  }
  .col-1,
  .col-2,
  .col-3,
  .col-4,
  .col-5,
  .col-6,
  .col-7,
  .col-8,
  .col-9,
  .col-10,
  .col-11,
  .col-12,
  .col,
  .col-auto,
  .col-sm-1,
  .col-sm-2,
  .col-sm-3,
  .col-sm-4,
  .col-sm-5,
  .col-sm-6,
  .col-sm-7,
  .col-sm-8,
  .col-sm-9,
  .col-sm-10,
  .col-sm-11,
  .col-sm-12,
  .col-sm,
  .col-sm-auto,
  .col-md-1,
  .col-md-2,
  .col-md-3,
  .col-md-4,
  .col-md-5,
  .col-md-6,
  .col-md-7,
  .col-md-8,
  .col-md-9,
  .col-md-10,
  .col-md-11,
  .col-md-12,
  .col-md,
  .col-md-auto,
  .col-lg-1,
  .col-lg-2,
  .col-lg-3,
  .col-lg-4,
  .col-lg-5,
  .col-lg-6,
  .col-lg-7,
  .col-lg-8,
  .col-lg-9,
  .col-lg-10,
  .col-lg-11,
  .col-lg-12,
  .col-lg,
  .col-lg-auto,
  .col-xl-1,
  .col-xl-2,
  .col-xl-3,
  .col-xl-4,
  .col-xl-5,
  .col-xl-6,
  .col-xl-7,
  .col-xl-8,
  .col-xl-9,
  .col-xl-10,
  .col-xl-11,
  .col-xl-12,
  .col-xl,
  .col-xl-auto {
    max-width: 100% !important;
    width: 100% !important;
    overflow: hidden;
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
    text-align: center;
  }
}
</style>
