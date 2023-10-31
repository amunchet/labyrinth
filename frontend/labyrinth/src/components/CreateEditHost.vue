<template>
  <b-modal id="create_edit_host" title="Create/Edit Host" size="lg">
    <template #modal-footer="{ cancel }">
      <div style="width: 100%">
        <b-button class="float-left" variant="danger" @click="deleteHost()"
          >Delete</b-button
        >
        <b-button class="float-right ml-2" variant="primary" @click="saveHost()"
          >OK</b-button
        >
        <b-button class="float-right" @click="cancel()">Cancel</b-button>
      </div>
    </template>
    <b-modal id="checks" size="xl" @hide="loadServices()">
      <Checks />
    </b-modal>
    <b-container>
      <b-row>
        <b-col> Monitor </b-col>
        <b-col>
          <b-form-checkbox
            size="lg"
            v-model="host.monitor"
            name="check-button"
            switch
          >
          </b-form-checkbox>
        </b-col>
      </b-row>
      <b-row>
        <b-col> IP </b-col>
        <b-col>
          <b-input
            v-model="host.ip"
            :state="
              !$v.host.ip.$invalid && (inp_host != '' || !all_ips.has(host.ip))
            "
            placeholder="E.g. 192.168.0.1"
          />
          <span
            v-if="inp_host == '' && all_ips && all_ips.has(host.ip)"
            class="text-danger"
          >
            Error: IP Address already exists!
          </span>
        </b-col>
      </b-row>
      <b-row>
        <b-col> Hostname </b-col>
        <b-col>
          <b-input v-model="host.host" />
        </b-col>
      </b-row>

      <b-row
        ><b-col>MAC </b-col><b-col><b-input v-model="host.mac" /></b-col
      ></b-row>
      <b-row
        ><b-col>Group </b-col><b-col><b-input v-model="host.group" /></b-col
      ></b-row>
      <b-row
        ><b-col>Subnet</b-col
        ><b-col
          ><b-input
            v-model="host.subnet"
            placeholder="E.g. 192.168.0"
            :state="!$v.host.subnet.$invalid" /></b-col
      ></b-row>
      <b-row
        ><b-col>Check TCP Port</b-col
        ><b-col
          ><b-input
            v-model="host.check_alive_port"
            placeholder="E.g. 22 for SSH"
          />
          <span class="text-small">
            Leave blank to ping host for alive check. Requires Monitor.
          </span>
        </b-col></b-row
      >

      <b-row
        ><b-col>Icon</b-col
        ><b-col><b-select :options="icons" v-model="host.icon" /></b-col
      ></b-row>
      <b-row
        ><b-col>Class</b-col><b-col><b-input v-model="host.class" /></b-col
      ></b-row>

      <b-row>
        <b-col> Notes</b-col>
        <b-col>
          <b-textarea style="min-height: 100px" v-model="host.notes" />
        </b-col>
      </b-row>
    </b-container>
    <hr />
    Service Icons:
    <b-row>
      <b-col style="display: flex">
        <font-awesome-icon
          class="mt-2 mr-3"
          icon="chart-area"
          size="1x"
        /><br />
        <b-select
          v-model="host.cpu_check"
          v-if="host.services != undefined"
          :options="[
            { text: '[No Service]', value: '' },
            ...host.services.map((x) => {
              return { text: x.name, value: x.name };
            }),
          ]"
          size="sm"
        />
      </b-col>

      <b-col style="display: flex">
        <font-awesome-icon class="mt-2 mr-3" icon="memory" size="1x" /><br />
        <b-select
          v-model="host.mem_check"
          v-if="host.services != undefined"
          :options="[
            { text: '[No Service]', value: '' },
            ...host.services.map((x) => {
              return { text: x.name, value: x.name };
            }),
          ]"
          size="sm"
        />
      </b-col>

      <b-col style="display: flex">
        <font-awesome-icon class="mt-2 mr-3" icon="database" size="1x" /><br />
        <b-select
          v-model="host.hd_check"
          v-if="host.services != undefined"
          :options="[
            { text: '[No Service]', value: '' },
            ...host.services.map((x) => {
              return { text: x.name, value: x.name };
            }),
          ]"
          size="sm"
        />
      </b-col>
    </b-row>

    <hr />
    <b-row>
      <b-col>
        <h5>
          Expected Open Ports
          <b-button
            variant="link"
            class="float-right mt-0 pt-1 shadow-none"
            @click="show_add_port = !show_add_port"
          >
            <font-awesome-icon icon="plus" size="1x" />
          </b-button>
        </h5>
        <b-table
          v-if="host.open_ports"
          :items="
            [...host.open_ports].sort().map((x) => {
              return { port: x };
            })
          "
          striped
          :fields="['port', '_']"
        >
          <template v-slot:cell(_)="key">
            <b-button
              @click="
                () => {
                  host.open_ports = host.open_ports.filter(
                    (x) => x != key.item.port
                  );
                  $forceUpdate();
                }
              "
              variant="link"
              class="shadow-none float-right text-danger"
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </template>

          <template v-slot:top-row="" v-if="show_add_port">
            <td role="cell">
              <b-input placeholder="Port:" v-model="new_port" />
            </td>
            <td role="cell">
              <b-button
                variant="success"
                class="float-right p-1 pl-2 pr-2"
                @click="
                  () => {
                    if (new_port != '') {
                      host.open_ports.push(new_port);
                    }
                    new_port = '';
                    show_add_port = false;
                    $forceUpdate();
                  }
                "
              >
                <font-awesome-icon icon="check" size="1x" />
              </b-button>
            </td>
          </template>
        </b-table>
      </b-col>
      <b-col>
        <h5>
          <a href="#" @click="$bvModal.show('checks')">Services</a>
          <b-button
            variant="link"
            class="shadow-none float-right mt-0 pt-1"
            @click="show_add_service = !show_add_service"
          >
            <font-awesome-icon icon="plus" size="1x" />
          </b-button>
        </h5>
        <b-table
          :items="host.services"
          striped
          :fields="['name', 'state', '_']"
        >
          <template v-slot:cell(_)="key">
            <b-button
              @click="
                () => {
                  host.services = host.services.filter(
                    (x) => x.name != key.item.name
                  );
                  $forceUpdate();
                }
              "
              variant="link"
              class="shadow-none float-right text-danger"
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </template>
          <template v-slot:top-row="" v-if="show_add_service">
            <td role="cell">
              <b-select
                placeholder="Service:"
                :options="services"
                v-model="new_services"
              />
            </td>

            <td>-</td>
            <td role="cell">
              <b-button
                variant="success"
                class="float-right p-1 pl-2 pr-2"
                @click="
                  () => {
                    if (new_services && new_services != '') {
                      host.services.push({
                        name: new_services,
                        state: '',
                      });
                    }
                    new_services = '';
                    show_add_service = false;
                    $forceUpdate();
                  }
                "
              >
                <font-awesome-icon icon="check" size="1x" />
              </b-button>
            </td>
          </template>
        </b-table>
      </b-col>
    </b-row>
    <hr />
    <b-row>
      <b-col>
        <h5>Host Reporting Level</h5>

        <b-select
          v-model="host.service_level"
          :options="['error', 'warning']"
        />
        <div class="mt-2 text-small">
          This overrides all reporting level settings for this host if set to
          warning. If set to error, then each service can have its level set
          individually.
        </div>
      </b-col>
      <b-col>
        <h5>
          Service Reporting Levels
          <b-button
            variant="link"
            class="float-right mt-0 pt-1 shadow-none"
            @click="show_add_service_level = !show_add_service_level"
          >
            <font-awesome-icon icon="plus" size="1x" />
          </b-button>
        </h5>
        <b-table
          v-if="host.service_levels"
          striped
          :items="host.service_levels.map((x) => x).filter((x) => x)"
          :fields="['_', 'service', 'level']"
        >
          <template v-slot:cell(_)="item">
            <b-button
              variant="link"
              @click="
                () => {
                  host.service_levels.splice(item.index, 1);
                  $forceUpdate();
                }
              "
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </template>
        </b-table>
        <b-row v-if="show_add_service_level" class="text-left ml-0 pl-0">
          <b-col class="text-left ml-0 pl-0">
            <b-select
              :options="
                ['check_alive'].concat(host.services
                  .map((x) => x.name)
                  .filter((x) => {
                    if (host.service_levels) {
                      return host.service_levels.indexOf(x) == -1;
                    }
                    return x;
                  }))
              "
              v-model="new_service_level"
            />
          </b-col>
          <b-col class="text-left">
            <b-select
              :options="['error', 'warning']"
              v-model="new_service_level_value"
            />
          </b-col>
          <b-col class="text-left">
            <b-button
              @click="
                () => {
                  if (host.service_levels == undefined) {
                    host.service_levels = [];
                  }
                  host.service_levels.push({
                    service: new_service_level + '',
                    level: new_service_level_value + '',
                  });
                  new_service_level = '';
                  new_sevice_level_value = 'error';
                  show_add_service_level = false;
                  $forceUpdate();
                }
              "
            >
              <font-awesome-icon icon="save" size="1x" />
            </b-button>
          </b-col>
        </b-row>
      </b-col>
    </b-row>
    <b-row class="overflow-scroll" v-if="metrics.length">
      <h4>Latest Host Metrics</h4>
      <div style="max-height: 400px; overflow-y: scroll">
        <b-table
          :fields="['name', 'fields', 'tags', 'timestamp']"
          :items="metrics"
          striped
        >
          <template v-slot:cell(timestamp)="cell">
            {{ cell.item.timestamp.split(".")[0] }}
          </template>
        </b-table>
      </div>
    </b-row>
  </b-modal>
</template>
<script>
import Helper from "@/helper";
import Checks from "@/views/Checks";

import { required } from "vuelidate/lib/validators";

export default {
  name: "CreateEditHost",
  components: {
    Checks,
  },
  props: ["inp_host", "all_ips"],
  data() {
    return {
      isNew: true,
      host: {},
      metrics: [],

      safe_host: {
        ip: "",
        subnet: "",
        mac: "",
        group: "",
        icon: "",
        services: [],
        class: "",
      },
      new_port: "",
      new_service: "",

      new_services: [],
      new_service_level: "",
      new_service_level_value: "",

      show_add_port: false,
      show_add_service: false,
      show_add_service_level: false,

      services: [],
      icons: [],
    };
  },
  watch: {
    inp_host: function (val) {
      if (val == "") {
        this.isNew = true;
        this.host = JSON.parse(JSON.stringify(this.safe_host));
        this.metrics = [];
      } else {
        this.isNew = false;
        this.host = val;
        try {
          this.loadMetrics();
          this.loadServices();
        } catch (e) {
          this.$store.commit("updateError", e);
        }
      }
    },
  },
  methods: {
    listIcons: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiCall("icons", "", auth)
        .then((res) => {
          this.icons = res.map((x) => {
            return {
              text: x,
              value: x,
            };
          });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadServices: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiCall("services", "all", auth)
        .then((res) => {
          this.services = res.map((x) => {
            return {
              text: x.display_name,
              value: x.display_name,
            };
          });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadMetrics: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiCall("metrics", this.host.mac, auth)
        .then((res) => {
          this.metrics = res;
          this.metrics.reverse();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    saveHost: /* istanbul ignore next  */ function () {
      let auth = this.$auth;
      let formData = new FormData();

      if (this.$v.host.$invalid) {
        this.$store.commit(
          "updateError",
          "Error: Please correct fields before saving."
        );
        return -1;
      }

      if (this.inp_host == "" && this.all_ips.has(this.host.ip)) {
        this.$store.commit("updateError", "Error: IP Address already exists.");
        return -1;
      }

      let host = JSON.parse(JSON.stringify(this.host));
      host["services"] = host["services"].map((x) => x["name"]);
      formData.append("data", JSON.stringify(host));
      Helper.apiPost("host", "", "", auth, formData)
        .then((res) => {
          this.$emit("update");
          this.$store.commit("updateError", res);
          this.$bvModal.hide("create_edit_host");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    deleteHost: /* istanbul ignore next */ function () {
      let host = this.host;
      let auth = this.$auth;
      this.$bvModal
        .msgBoxConfirm("Are you sure you want to delete this host?")
        .then((res) => {
          if (!res) {
            return;
          }

          let url = host.mac;
          if (host.mac == "") {
            url = host.ip;
          }
          Helper.apiDelete("host", url, auth)
            .then((res) => {
              this.$store.commit("updateError", res);
              this.$bvModal.hide("create_edit_host");
              this.$emit("update");
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadServices();
      this.listIcons();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  validations: {
    host: {
      ip: {
        required,
        ipValidation: (val) => Helper.validateIP(val),
      },
      subnet: {
        required,
        ipValidation: (val) => Helper.validateIP(val, 3),
      },
    },
  },
};
</script>
<style lang="scss" scoped>
.row {
  margin: 1rem;
}
h4 {
  text-align: center;
}
.overflow-scroll {
  overflow-x: scroll;
}
.text-small {
  font-size: 9pt;
  color: grey;
}
</style>
