<template>
  <b-modal id="service_detail" title="Service Details" size="xl">
    <b-spinner
      class="d-block ml-auto mr-auto mt-4 mb-4"
      v-if="historyLoading"
    />

    <div class="d-flex justify-content-end mb-2" v-if="display">
      <b-button-group size="sm">
        <b-button
          v-for="option in granularityOptions"
          :key="option.value"
          :variant="
            granularity === option.value ? 'primary' : 'outline-primary'
          "
          @click="granularity = option.value"
        >
          {{ option.label }}
        </b-button>
      </b-button-group>
    </div>
    <uptime-graph
      v-if="display"
      :records="result"
      :granularity="granularity"
    ></uptime-graph>

    <div style="overflow-x: scroll" class="mt-2">
      <h4>Current Result</h4>

      <b-table
        :items="latest_metric"
        v-if="!loading"
        :fields="['name', 'tags', 'fields', 'timestamp', 'judgement']"
      >
        <template v-slot:cell(name)="row">
          {{ row.item.name }}<br />
          <b-button
            @click="deleteMetric(row.item._id)"
            variant="link"
            class="text-danger mt-4 p-0 ml-0 mr-0"
          >
            <font-awesome-icon icon="trash" size="1x" />&nbsp; Delete Metric
          </b-button>
        </template>
        <template v-slot:cell(timestamp)="row">
          {{ formatDate(row.item.timestamp * 1000) }}
          {{ formatDate(row.item.timestamp * 1000, true) }}
        </template>

        <template v-slot:cell(fields)="row">
          <b-table
            :items="Object.keys(row.item.fields)"
            :fields="['name', 'value']"
            striped
            bordered
            small
          >
            <template v-slot:cell(name)="x">
              {{ x.item.replace(/_/g, " ") }}
            </template>
            <template v-slot:cell(value)="x">
              {{ row.item.fields[x.item] }}
            </template>
          </b-table>
        </template>
        <template v-slot:cell(tags)="row">
          <b-table
            :items="Object.keys(row.item.tags)"
            :fields="['name', 'value']"
            striped
            bordered
            small
          >
            <template v-slot:cell(name)="x">
              {{ x.item.replace(/_/g, " ") }}
            </template>
            <template v-slot:cell(value)="x">
              {{ row.item.tags[x.item].replace(/_/g, " ") }}
            </template>
          </b-table>
        </template>
      </b-table>

      <hr />
      <b-button
        variant="link"
        class="p-0 mb-2"
        @click="showHistory = !showHistory"
      >
        <font-awesome-icon
          :icon="showHistory ? 'chevron-down' : 'chevron-right'"
          size="1x"
        />&nbsp; {{ showHistory ? "Hide" : "Show" }} Full History
        <span v-if="!loading">({{ result_backwards.length }} records)</span>
      </b-button>

      <b-collapse v-model="showHistory">
        <h4>History</h4>
        <b-table
          :items="result_backwards"
          v-if="!loading"
          :fields="['name', 'tags', 'fields', 'timestamp', 'judgement']"
        >
          <template v-slot:cell(timestamp)="row">
            {{ formatDate(row.item.timestamp * 1000) }}
            {{ formatDate(row.item.timestamp * 1000, true) }}
          </template>

          <template v-slot:cell(fields)="row">
            <b-table
              :items="Object.keys(row.item.fields)"
              :fields="['name', 'value']"
              striped
              bordered
              small
            >
              <template v-slot:cell(name)="x">
                {{ x.item.replace(/_/g, " ") }}
              </template>
              <template v-slot:cell(value)="x">
                {{ row.item.fields[x.item] }}
              </template>
            </b-table>
          </template>
          <template v-slot:cell(tags)="row">
            <b-table
              :items="Object.keys(row.item.tags)"
              :fields="['name', 'value']"
              striped
              bordered
              small
            >
              <template v-slot:cell(name)="x">
                {{ x.item.replace(/_/g, " ") }}
              </template>
              <template v-slot:cell(value)="x">
                {{ row.item.tags[x.item].replace(/_/g, " ") }}
              </template>
            </b-table>
          </template>
        </b-table>
        <b-spinner v-else />
      </b-collapse>
    </div>
  </b-modal>
</template>

<script>
import UptimeGraph from "./charts/UptimeGraph";

import Helper from "@/helper";

// Enough history to make day/hour bucketing in the uptime graph meaningful,
// not just the last handful of checks.
const HISTORY_FETCH_COUNT = 1000;

export default {
  name: "HostMetric",
  props: ["data"],
  components: {
    UptimeGraph,
  },
  data() {
    return {
      display: false,
      result: [],
      result_backwards: [],
      loading: false,
      historyLoading: false,
      latest_metric: [],
      granularity: "day",
      granularityOptions: [
        { value: "day", label: "Day" },
        { value: "hour", label: "Hour" },
        { value: "check", label: "Check" },
      ],
      showHistory: false,
    };
  },
  mounted() {},
  methods: {
    formatDate: Helper.formatDate,
    loadLatestMetric: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      this.loading = true;
      Helper.apiCall(
        "metrics",
        this.data.ip + "/" + this.data.name + "/latest",
        auth
      )
        .then((res) => {
          this.latest_metric = res;
          this.loading = false;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
          this.loading = false;
        });
    },
    deleteMetric: /* istanbul ignore next */ function (metric_id) {
      let auth = this.$auth;
      Helper.apiDelete("metrics", metric_id, auth)
        .then(() => {
          this.loadLatestMetric();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  watch: {
    data: /* istanbul ignore next */ async function (inp) {
      if (inp != "" && inp != undefined && inp) {
        this.loadLatestMetric();

        let auth = this.$auth;
        this.loading = true;
        this.historyLoading = true;
        this.display = false;
        this.showHistory = false;
        await Helper.apiCall(
          "metrics",
          this.data.ip + "/" + this.data.name + "/" + HISTORY_FETCH_COUNT,
          auth
        )
          .then((res) => {
            this.result = res;
            this.result_backwards = JSON.parse(JSON.stringify(res)).reverse();
            this.loading = false;
            this.historyLoading = false;
            this.display = true;
          })
          .catch((e) => {
            this.$store.commit("updateError", e);
            this.loading = false;
            this.historyLoading = false;
          });
      }
    },
  },
};
</script>

<style scoped>
.small {
  max-width: 600px;
  margin: 150px auto;
}
</style>
