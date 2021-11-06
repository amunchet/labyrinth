<template>
  <b-container style="min-width: 90%">
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
            <b-button variant="primary" @click="putStructure()" class="float-right">
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
            variant="success" class="float-right">
              <font-awesome-icon
                icon="save"
                size="1x"
                @click="saveConf()"
              /> 
              </b-button
          >
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
            @click="()=>{
              output_data = {}
              }"
            >Clear All</b-button
          >
        </div>

        <hr />

        <div v-if="output_data">
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
        await this.$bvModal
          .msgBoxConfirm(
            "Do you want to overwrite working configuration from disk?"
          )
          .then(async (res) => {
            if (!res) {
              return;
            }
            var auth = this.$auth;
            await Helper.apiCall("load_service", val, auth)
              .then((res) => {
                this.output_data = res;
                this.loadSuggestedFields();
              })
              .catch((e) => {
                this.$store.commit("updateError", e);
              });
          })
          .catch((e) => {
            this.$store.commit("updateError", e);
          });

        this.loadSuggestedFields();
      }
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

    loadSuggestedFields: function () {
      // Any time we add, force global tags to be host
      // Also add predetermined outputs

      if (this.output_data["global_tags"] == undefined) {
        this.output_data["global_tags"] = {};
      }

      if(this.output_data["outputs"] == undefined){
        this.output_data["outputs"] = {}
      }

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
      this.saving_conf = true
      Helper.apiPost("save_conf", "", this.selected_host, auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.saving_conf = false
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
          this.saving_conf = false
          this.$store.commit("updateError", e);
        });
    },
    saveConf: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.output_data));
      this.saving_conf = true
      Helper.apiPost("save_conf", "", this.selected_host, auth, formData)
        .then((res) => {
          this.hasBeenSaved = true;
          this.loadFile();
          this.$store.commit("updateError", res);
          this.saving_conf = false
        })
        .catch((e) => {
          this.saving_conf = false
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadStructure();
      this.getAutosave();
      this.listHosts();
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
</style>
