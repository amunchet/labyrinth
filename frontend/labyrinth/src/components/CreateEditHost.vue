<template>
  <b-modal id="create_edit_host" title="Create/Edit Host" size="lg">
    <template #modal-footer="{ cancel }">
      <div style="width: 100%">
        <b-button class="float-left" variant="danger" @click="deleteHost()"
          >Delete</b-button
        >
        <b-button
          class="float-left ml-2"
          variant="secondary"
          v-if="!isNew"
          @click="cloneHost()"
          >Clone</b-button
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
      <b-row>
        <b-col>Tags</b-col>
        <b-col>
          <b-input v-model="host.tags" placeholder="E.g. proxmox, linux" />
          <div v-if="parsedTags.length" class="tags-preview mt-2 mb-1">
            <span
              v-for="tag in parsedTags"
              :key="tag"
              class="tag-badge bg-secondary text-light"
              >{{ tag }}</span
            >
          </div>
          <span class="text-small">
            Comma-separated tags (cross-subnet, unlike groups).
          </span>
        </b-col>
      </b-row>

      <b-row>
        <b-col>Proxmox Cluster</b-col>
        <b-col>
          <b-input
            v-model="host.proxmox_cluster"
            placeholder="Cluster name or ID"
          />
          <span class="text-small">
            If this host is a Proxmox cluster, specify which cluster it belongs
            to.
          </span>
        </b-col>
      </b-row>

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
          <template v-slot:cell(state)="key">
            <b-button
              v-if="key.item.state === true"
              variant="link"
              class="shadow-none text-success"
            >
              <font-awesome-icon icon="check" size="1x" />
            </b-button>
            <b-button
              v-else-if="key.item.state === false"
              variant="link"
              class="shadow-none text-danger"
            >
              <font-awesome-icon icon="times-circle" size="1x" />
            </b-button>
          </template>
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
            <td role="cell" @keydown.esc.stop="(e) => e.stopPropagation()">
              <v-select
                placeholder="Service:"
                label="text"
                :reduce="(x) => x.value"
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
        <hr />
        <h6>Host Level Expire Date</h6>
        <b-form-datepicker v-model="host.service_level_expire_date" />
        <div class="mt-2 text-small">
          Date on which the selected service level expires. This field will be
          removed, setting behaviour back to default.
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
                host.services
                  .map((x) => x.name)
                  .filter((x) => {
                    if (host.service_levels) {
                      return host.service_levels.indexOf(x) == -1;
                    }
                    return x;
                  })
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
    <b-row v-if="!isNew">
      <b-col>
        <h4>Telegraf Ingest</h4>
        <div v-if="ingest_loading" class="text-small">
          Loading ingest counters...
        </div>
        <div v-else-if="!ingest.found" class="text-small">
          No Telegraf traffic recorded for this host yet. Counters start once
          the host posts to /api/metrics/.
        </div>
        <div v-else>
          <div class="ingest-tiles">
            <div class="ingest-tile">
              <span class="ingest-value">{{ ingest.requests }}</span>
              <span class="ingest-label">Requests total</span>
            </div>
            <div class="ingest-tile">
              <span class="ingest-value">{{ ingest.metrics }}</span>
              <span class="ingest-label">Metrics total</span>
            </div>
            <div class="ingest-tile">
              <span class="ingest-value">{{ ingestRequestsPerMinute }}</span>
              <span class="ingest-label">Requests / min</span>
            </div>
            <div class="ingest-tile">
              <span class="ingest-value">{{ ingestMetricsPerMinute }}</span>
              <span class="ingest-label">Metrics / min</span>
            </div>
            <div class="ingest-tile">
              <span class="ingest-value">{{ ingest.last_batch }}</span>
              <span class="ingest-label">Last batch size</span>
            </div>
          </div>

          <div class="ingest-chart">
            <div class="ingest-chart-head">
              <span
                >Requests per minute, last
                {{ ingest.window_minutes }} minutes</span
              >
              <span class="text-small">peak {{ ingestPeak }}</span>
            </div>
            <div class="ingest-bars">
              <div
                v-for="bucket in ingest.per_minute"
                :key="bucket.minute"
                class="ingest-bar-slot"
                :title="bucketTitle(bucket)"
              >
                <div
                  class="ingest-bar"
                  :style="{ height: bucketHeight(bucket) }"
                ></div>
              </div>
            </div>
          </div>

          <div class="ingest-footer">
            <span class="text-small">
              Counted as <code>{{ ingest.client_id }}</code
              >, last seen {{ ingestLastSeen }}.
              <template v-if="ingest.skipped">
                {{ ingest.skipped }} metric(s) rejected for missing name/tags.
              </template>
            </span>
            <b-button
              size="sm"
              variant="outline-secondary"
              @click="resetIngestCounts()"
              >Reset counters</b-button
            >
          </div>
        </div>
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

      ingest: { found: false, per_minute: [] },
      ingest_loading: false,

      safe_host: {
        ip: "",
        subnet: "",
        mac: "",
        host: "",
        group: "",
        tags: "",
        proxmox_cluster: "",
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
        this.ingest = { found: false, per_minute: [] };
      } else {
        this.isNew = false;
        this.host = val;
        try {
          this.loadMetrics();
          this.loadServices();
          this.loadIngestCounts();
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
      const auth = this.$auth;
      Helper.apiCall("services", "all", auth)
        .then((res = []) => {
          const seen = new Set();
          const unique = [];

          for (const x of res) {
            const name = (x?.display_name || "").trim();
            if (!name) continue; // skip empties
            const key = name.toLowerCase(); // case-insensitive dedupe
            if (seen.has(key)) continue; // already added
            seen.add(key);
            unique.push({ text: name, value: name });
          }

          this.services = unique;
        })
        .catch((e) => this.$store.commit("updateError", e));
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
    ingestId: function () {
      // The ingest service counts a host by MAC when its Telegraf config sets
      // one and by IP otherwise; the backend resolves whichever we send.
      return (this.host && (this.host.mac || this.host.ip)) || "";
    },
    loadIngestCounts: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      let id = this.ingestId();
      if (!id) {
        return;
      }

      this.ingest_loading = true;
      Helper.apiCall("metrics_counts", id, auth)
        .then((res) => {
          this.ingest = res;
          this.ingest_loading = false;
        })
        .catch((e) => {
          this.ingest_loading = false;
          this.$store.commit("updateError", e);
        });
    },
    resetIngestCounts: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      let id = this.ingestId();
      if (!id) {
        return;
      }

      Helper.apiDelete("metrics_counts", id, auth)
        .then(() => {
          this.loadIngestCounts();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    ingestRate: function (field) {
      // Averaged over the window actually recorded, so a host that only
      // started reporting ten minutes ago is not diluted by fifty empty ones.
      let buckets = this.ingestBuckets.filter((bucket) => bucket.requests > 0);
      if (!buckets.length) {
        return 0;
      }
      let total = (this.ingest && this.ingest[field]) || 0;
      return Math.round((total / buckets.length) * 10) / 10;
    },
    bucketHeight: function (bucket) {
      let peak = this.ingestPeak;
      if (!peak || !bucket || !bucket.requests) {
        return "0%";
      }
      // Floor at 4% so a minute with traffic never renders as a gap.
      return Math.max(4, Math.round((bucket.requests / peak) * 100)) + "%";
    },
    bucketTitle: function (bucket) {
      if (!bucket) {
        return "";
      }
      let when = new Date(bucket.timestamp * 1000);
      return (
        Helper.formatDate(when, true) +
        " - " +
        bucket.requests +
        " request(s), " +
        bucket.metrics +
        " metric(s)"
      );
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
    cloneHost: function () {
      let cloned = JSON.parse(JSON.stringify(this.host));
      delete cloned._id;
      cloned.ip = "";
      cloned.mac = "";
      this.host = cloned;
      this.isNew = true;
      this.metrics = [];
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
  computed: {
    ingestBuckets() {
      return (this.ingest && this.ingest.per_minute) || [];
    },
    ingestPeak() {
      return this.ingestBuckets.reduce(
        (peak, bucket) => Math.max(peak, bucket.requests || 0),
        0
      );
    },
    ingestRequestsPerMinute() {
      return this.ingestRate("requests_last_hour");
    },
    ingestMetricsPerMinute() {
      return this.ingestRate("metrics_last_hour");
    },
    ingestLastSeen() {
      if (!this.ingest || !this.ingest.last_seen) {
        return "never";
      }
      let when = new Date(this.ingest.last_seen * 1000);
      return Helper.formatDate(when) + " " + Helper.formatDate(when, true);
    },
    parsedTags() {
      const raw = (this.host && this.host.tags) || "";
      return raw
        .split(",")
        .map((x) => x.trim())
        .filter((x) => x);
    },
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
.tags-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag-badge {
  display: inline-block;
  background-color: #e9ecef;
  color: #495057;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 9pt;
  white-space: nowrap;
}

/* Telegraf ingest counters.  One measure, one hue: values stay in text ink
   and the bars carry the only colour, so the panel reads at a glance. */
$ingest-hue: #38595e;

.ingest-tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ingest-tile {
  display: flex;
  flex-direction: column;
  flex: 1 1 90px;
  padding: 6px 10px;
  border: 1px solid #e0e3e6;
  border-radius: 4px;
  text-align: left;
}
.ingest-value {
  font-size: 15pt;
  font-weight: 600;
  line-height: 1.1;
  color: #212529;
}
.ingest-label {
  font-size: 8.5pt;
  color: #6c757d;
}

.ingest-chart {
  margin-top: 12px;
}
.ingest-chart-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 9pt;
  color: #6c757d;
  margin-bottom: 3px;
}
.ingest-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 56px;
  padding-bottom: 2px;
  border-bottom: 1px solid #e0e3e6;
}
.ingest-bar-slot {
  flex: 1 1 0;
  height: 100%;
  display: flex;
  align-items: flex-end;
  min-width: 2px;
}
.ingest-bar {
  width: 100%;
  background-color: $ingest-hue;
  border-radius: 2px 2px 0 0;
}

.ingest-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
</style>
