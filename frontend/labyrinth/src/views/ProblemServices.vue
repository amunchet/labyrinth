<template>
  <b-container fluid class="mt-3">
    <h4 class="text-left">Problem Services</h4>
    <p class="text-left text-muted">
      Grid of services currently failing or reporting no data. Mark a service as
      a warning to downgrade its alert severity without silencing it.
    </p>
    <b-row class="text-left mb-3">
      <b-col md="4">
        <b-form-input
          v-model="filter"
          placeholder="Filter by host, group, or service..."
        />
      </b-col>
    </b-row>
    <div v-if="loading">
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
          :class="'problem-card text-left ' + cardClass(item)"
        >
          <div class="d-flex justify-content-between align-items-start">
            <strong>{{ item.host_name || item.ip }}</strong>
            <b-badge :variant="item.state === -1 ? 'warning' : 'danger'">
              {{ item.state === -1 ? "Unknown" : "Critical" }}
            </b-badge>
          </div>
          <div class="text-muted small">
            {{ item.ip }} &middot; {{ item.group }} &middot; {{ item.subnet }}
          </div>
          <hr class="my-2" />
          <div>{{ item.service_name.replace(/_/g, " ") }}</div>
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
      filter: "",
    };
  },
  computed: {
    problems: function () {
      let output = [];
      (this.full_data || []).forEach((subnet) => {
        (subnet.groups || []).forEach((group) => {
          (group.hosts || []).forEach((host) => {
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
      if (!this.filter) {
        return this.problems;
      }
      let needle = this.filter.toLowerCase();
      return this.problems.filter((item) =>
        [item.host_name, item.ip, item.group, item.service_name]
          .filter((x) => x)
          .some((x) => x.toLowerCase().indexOf(needle) !== -1)
      );
    },
  },
  methods: {
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
    cardClass: function (item) {
      if (item.state === -1) {
        return item.is_warning ? "orange-border" : "orange-bg";
      }
      return item.is_warning ? "red-border" : "red-bg";
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
