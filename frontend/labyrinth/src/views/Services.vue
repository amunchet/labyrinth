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
            <b-select v-model="selected_host" :options="hosts" />
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
  components: {
    ServiceComponent,
  },
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
    selected_host: /* istanbul ignore next */ async function (val) {
      if (val != "" && val != "TEST") {
        var auth = this.$auth;
        await Helper.apiCall("load_service", val, auth)
          .then((res) => {
            if (res != "") {
              this.output_data = res;
            }
            this.loadSuggestedFields();
          })
          .catch((e) => {
            this.$store.commit("updateError", e);
          });
      }

      this.loadSuggestedFields();
    },
  },
  methods: {
    add: function (data) {
      // Handle undefined at top
      this.$forceUpdate();
      var output = JSON.parse(data);

      // Need to handle deep nests - assume every parent is an object, except for the arrays

      var item = output.item;
      var parent = output.parent.replace("undefined.", "") || "";
      var name = output.name;

      var temp = JSON.parse(JSON.stringify(this.output_data));
      this.output_data = "";
      this.$forceUpdate();

      const set = (obj, path, val) => {
        const keys = path.split(".");
        const lastKey = keys.pop();
        const lastObj = keys.reduce((obj, key) => {
          return (obj[key] = obj[key] || {});
        }, obj);
        lastObj[lastKey] = val;
      };
      var outtie = parent + "." + name;

      set(temp, outtie, item);

      if (temp[""] != undefined) {
        var keys = Object.keys(temp[""]);
        for (var i = 0; i < keys.length; i++) {
          var next_key = keys[i];
          if (temp[next_key] == undefined) {
            temp[next_key] = temp[""][next_key];
          }
        }
        delete temp[""];
      }

      this.output_data = temp;

      this.loadSuggestedFields();
      this.$forceUpdate();
    },

    loadDefaultBackendLocation: /* istanbul ignore next */ async function () {
      var auth = this.$auth;
      await Helper.apiCall("settings", "default_telegraf_backend", auth)
        .then((res) => {
          this.default_backend = res;
        })
        .catch((e) => {
          if (e.status == undefined || e.status != 481) {
            this.$store.commit("updateError", e);
          } else {
            this.$store.commit(
              "updateError",
              "Error: Please update default backend location in Settings."
            );
          }
        });
    },
    loadTelegrafKey: /* istanbul ignore next */ async function () {
      var auth = this.$auth;
      await Helper.apiCall("telegraf_key", "", auth)
        .then((res) => {
          this.telegraf_key = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadSuggestedFields: async function () {
      // Any time we add, force global tags to be host
      // Also add predetermined outputs

      if (this.output_data["global_tags"] == undefined) {
        this.output_data["global_tags"] = {};
      }

      if (this.output_data["outputs"] == undefined) {
        this.output_data["outputs"] = {};
      }

      if (this.default_backend == "") {
        await this.loadDefaultBackendLocation();
      }
      this.output_data["outputs"]["http"] = {
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

      var found_host = this.raw_hosts.filter(
        (x) => x.ip == this.selected_host
      )[0];
      var found_tags = {};
      var tag_names = ["mac", "host", "ip"];
      for (var i = 0; i < tag_names.length; i++) {
        if (
          found_host[tag_names[i]] != undefined &&
          found_host[tag_names[i]] != ""
        ) {
          found_tags[tag_names[i]] = found_host[tag_names[i]];
        }
      }
      this.output_data["global_tags"] = found_tags;
    },

    loadStructure: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "get_structure", auth)
        .then((res) => {
          this.data = res;
          this.loaded = true;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    putStructure: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "put_structure", auth)
        .then((res) => {
          this.$store.commit("updateError", res);
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    getAutosave: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "autosave", auth)
        .then((res) => {
          this.output_data = res;
        })
        .catch(() => {
          this.output_data = {};
        });
    },
    autoSave: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.output_data));
      Helper.apiPost("redis", "", "autosave", auth, formData).catch(() => {
        this.autoSaved = false;
      });
    },
    listHosts: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("hosts", "", auth)
        .then((res) => {
          this.raw_hosts = res;
          this.hosts = res.map((x) => {
            return {
              value: x.ip,
              text: x.ip,
            };
          });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadFile: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("load_service", this.selected_host + "/text", auth)
        .then((res) => {
          this.loadedFile = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    runTest: /* istanbul ignore next */ function (outputs) {
      var auth = this.$auth;
      Helper.apiCall("run_conf", this.selected_host + "/" + outputs, auth)
        .then((res) => {
          this.testOutput = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    saveRaw: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("raw", this.loadedFile);
      formData.append("data", "{}");
      this.saving_conf = true;
      Helper.apiPost("save_conf", "", this.selected_host, auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.saving_conf = false;
          Helper.apiCall("load_service", this.selected_host, auth)
            .then((res) => {
              this.output_data = res;
              this.loadSuggestedFields();
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        })
        .catch((e) => {
          this.saving_conf = false;
          this.$store.commit("updateError", e);
        });
    },
    saveConf: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.output_data));
      this.saving_conf = true;
      Helper.apiPost("save_conf", "", this.selected_host, auth, formData)
        .then((res) => {
          this.hasBeenSaved = true;
          this.loadFile();
          this.$store.commit("updateError", res);
          this.saving_conf = false;
        })
        .catch((e) => {
          this.saving_conf = false;
          this.$store.commit("updateError", e);
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
