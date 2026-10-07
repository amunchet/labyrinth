<template>
  <b-container fluid class="mt-3">
    <h4 class="text-left">Problem Services</h4>
    <p class="text-left text-muted">
      Grid of services currently failing or reporting no data. Mark a service as
      a warning to downgrade its alert severity without silencing it.
    </p>
    <b-row class="text-left mb-2 align-items-end">
      <b-col md="4">
        <b-input-group>
          <b-form-input
            v-model="filter_input"
            placeholder="Filter by host, group, or service..."
            @keyup.enter="applyFilter"
          />
          <b-input-group-append>
            <b-button variant="primary" @click="applyFilter"> Filter </b-button>
          </b-input-group-append>
        </b-input-group>
      </b-col>
      <b-col md="auto">
        <label class="mb-0 mr-1 small text-muted">Type</label>
        <b-form-select
          v-model="service_type_filter"
          :options="typeOptions"
          size="sm"
        />
      </b-col>
      <b-col md="auto" class="ml-auto">
        <b-button
          variant="outline-secondary"
          :disabled="loading"
          @click="loadData()"
        >
          <b-spinner small v-if="loading" class="mr-1" />
          Refresh
        </b-button>
      </b-col>
    </b-row>
    <b-row class="text-left mb-3">
      <b-col md="auto">
        <b-form-checkbox v-model="monitored_only" switch>
          Monitored hosts only
        </b-form-checkbox>
      </b-col>
      <b-col md="auto">
        <b-form-checkbox v-model="critical_only" switch>
          Critical only
        </b-form-checkbox>
      </b-col>
    </b-row>
    <div v-if="loading && !full_data.length">
      <b-spinner class="m-2" />
    </div>
    <div v-else>
      <p v-if="filteredProblems.length === 0" class="text-muted text-left">
        No problem services found.
      </p>
      <div class="problem-grid" v-else>
        <b-card
          v-for="item in filteredProblems"
          :key="item.ip + '-' + item.service_name"
          class="problem-card text-left"
          body-class="p-2"
        >
          <div class="d-flex align-items-center">
            <img
              :src="iconSrc(item)"
              @error="onIconError"
              class="host-icon mr-2"
            />
            <div class="flex-grow-1 overflow-hidden">
              <div class="d-flex justify-content-between align-items-center">
                <strong class="host-name" :title="item.host_name || item.ip">
                  {{ shortHostName(item) }}
                </strong>
                <b-badge :variant="severity(item).variant" class="ml-1">
                  {{ severity(item).text }}
                </b-badge>
              </div>
              <div class="text-muted meta-line">
                {{ item.ip }} &middot; {{ item.group }}
              </div>
              <div :class="severity(item).textClass + ' service-name'">
                {{ item.service_name.replace(/_/g, " ") }}
              </div>
            </div>
          </div>
          <div class="mt-1 text-right">
            <b-button
              size="sm"
              variant="outline-secondary"
              v-if="!item.is_warning"
              @click="setWarning(item, 'warning')"
            >
              Mark Warning
            </b-button>
            <b-button
              size="sm"
              variant="outline-secondary"
              v-else
              @click="setWarning(item, '')"
            >
              Clear Warning
            </b-button>
          </div>
        </b-card>
      </div>
    </div>
  </b-container>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "ProblemServices",
  data() {
    return {
      loading: false,
      full_data: [],
      filter_input: "",
      applied_filter: "",
      monitored_only: true,
      critical_only: true,
      service_type_filter: "all",
      icons: [
        "Default",
        "Camera",
        "Cloud",
        "Linux",
        "NAS",
        "Phone",
        "Printer",
        "CellPhone",
        "Router",
        "Speaker",
        "Tower",
        "VMWare",
        "Microsoft",
        "Wireless",
      ],
    };
  },
  computed: {
    problems: function () {
      let output = [];
      (this.full_data || []).forEach((subnet) => {
        (subnet.groups || []).forEach((group) => {
          (group.hosts || []).forEach((host) => {
            if (this.monitored_only && !this.isMonitored(host)) {
              return;
            }
            (host.services || []).forEach((service) => {
              if (service.state === false || service.state === -1) {
                output.push({
                  ip: host.ip,
                  host_name: host.host,
                  group: group.name,
                  subnet: subnet.subnet,
                  icon: host.icon,
                  service_name: service.name,
                  service_type: this.serviceType(service),
                  state: service.state,
                  is_warning: this.isWarning(host, service.name),
                });
              }
            });
          });
        });
      });
      return output;
    },
    availableServiceTypes: function () {
      let types = new Set();
      this.problems.forEach((item) => types.add(item.service_type));
      return Array.from(types).sort();
    },
    typeOptions: function () {
      return [{ value: "all", text: "All types" }].concat(
        this.availableServiceTypes.map((t) => ({
          value: t,
          text: this.capitalize(t),
        }))
      );
    },
    filteredProblems: function () {
      let items = this.problems;
      if (this.critical_only) {
        items = items.filter((item) => this.severity(item).text === "Critical");
      }
      if (this.service_type_filter !== "all") {
        items = items.filter(
          (item) => item.service_type === this.service_type_filter
        );
      }
      if (this.applied_filter) {
        let needle = this.applied_filter.toLowerCase();
        items = items.filter((item) =>
          [item.host_name, item.ip, item.group, item.service_name]
            .filter((x) => x)
            .some((x) => x.toLowerCase().indexOf(needle) !== -1)
        );
      }
      return items;
    },
  },
  methods: {
    applyFilter: function () {
      this.applied_filter = this.filter_input;
    },
    capitalize: function (word) {
      if (!word) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    },
    shortHostName: function (item) {
      let name = item.host_name || item.ip || "";
      return name.split(".")[0];
    },
    serviceType: function (service) {
      if (service.name === "open_ports" || service.name === "closed_ports") {
        return "port";
      }
      if (
        service.found_service &&
        typeof service.found_service === "object" &&
        service.found_service.type
      ) {
        return service.found_service.type;
      }
      return "other";
    },
    iconSrc: function (item) {
      let icon = item.icon || "";
      let titled = this.capitalize(icon);
      if (this.icons.indexOf(titled) !== -1) {
        return "/icons/" + titled + ".svg";
      }
      if (icon) {
        return "/icons/" + icon + ".svg";
      }
      return "/icons/Default.svg";
    },
    onIconError: function (event) {
      event.target.src = "/icons/Default.svg";
    },
    isMonitored: function (host) {
      return String(host.monitor).toLowerCase() === "true";
    },
    isWarning: function (host, service_name) {
      if (host.service_level === "warning") {
        return true;
      }
      if (host.service_levels) {
        return host.service_levels.some(
          (x) => x.service === service_name && x.level === "warning"
        );
      }
      return false;
    },
    severity: function (item) {
      if (item.is_warning) {
        return {
          text: "Warning",
          variant: "warning",
          textClass: "text-warning",
        };
      }
      if (item.state === false) {
        return {
          text: "Critical",
          variant: "danger",
          textClass: "text-danger",
        };
      }
      return { text: "Unknown", variant: "secondary", textClass: "text-muted" };
    },
    setWarning: /* istanbul ignore next */ function (item, level) {
      let auth = this.$auth;
      let url = item.ip + "/" + item.service_name + "/";
      if (level) {
        url += level + "/";
      }
      Helper.apiCall("host_service_level", url, auth)
        .then(() => {
          this.loadData();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadData: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      this.loading = true;
      Helper.apiCall("dashboard", "", auth)
        .then((res) => {
          this.full_data = res;
          this.loading = false;
        })
        .catch((e) => {
          this.loading = false;
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.loadData();
  },
};
</script>
<style scoped>
.problem-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
}
.problem-card {
  margin: 0;
}
.host-icon {
  width: 24px;
  height: 24px;
  object-fit: contain;
  flex-shrink: 0;
}
.host-name {
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-line {
  font-size: 0.72rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.service-name {
  font-size: 0.85rem;
}
</style>
