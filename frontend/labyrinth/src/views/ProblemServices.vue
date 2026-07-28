<template>
  <b-container fluid class="mt-3">
    <h4 class="text-left">Problem Services</h4>
    <p class="text-left text-muted">
      Grid of services currently failing or reporting no data. Mark a service as
      a warning to downgrade its alert severity without silencing it.
    </p>
    <b-row class="text-left mb-3 align-items-end">
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
        <b-form-checkbox v-model="monitored_only" switch>
          Monitored hosts only
        </b-form-checkbox>
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
        >
          <div class="d-flex justify-content-between align-items-start">
            <strong>{{ item.host_name || item.ip }}</strong>
            <b-badge :variant="severity(item).variant">
              {{ severity(item).text }}
            </b-badge>
          </div>
          <div class="text-muted small">
            {{ item.ip }} &middot; {{ item.group }} &middot; {{ item.subnet }}
          </div>
          <hr class="my-2" />
          <div :class="severity(item).textClass">
            {{ item.service_name.replace(/_/g, " ") }}
          </div>
          <div class="mt-2">
            <b-button
              size="sm"
              variant="outline-secondary"
              v-if="!item.is_warning"
              @click="setWarning(item, 'warning')"
            >
              Mark as Warning
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
                  service_name: service.name,
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
    filteredProblems: function () {
      if (!this.applied_filter) {
        return this.problems;
      }
      let needle = this.applied_filter.toLowerCase();
      return this.problems.filter((item) =>
        [item.host_name, item.ip, item.group, item.service_name]
          .filter((x) => x)
          .some((x) => x.toLowerCase().indexOf(needle) !== -1)
      );
    },
  },
  methods: {
    applyFilter: function () {
      this.applied_filter = this.filter_input;
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
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}
.problem-card {
  margin: 0;
}
</style>
