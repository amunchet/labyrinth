<template>
  <b-modal id="service_detail" title="Service Details" size="xl">
    <line-chart
      v-if="display"
      height="100px"
      :chart-data="datacollection"
    ></line-chart>

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
    </div>
  </b-modal>
</template>

<script>
import LineChart from "./charts/BarChart";

import Helper from "@/helper";

export default {
  name: "HostMetric",
  props: ["data"],
  components: {
    LineChart,
  },
  data() {
    return {
      datacollection: null,
      display: false,
      result: [],
      result_backwards: [],
      loading: false,
      latest_metric: [],
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
        this.display = false;
        await Helper.apiCall(
          "metrics",
          this.data.ip + "/" + this.data.name,
          auth
        )
          .then((res) => {
            this.result = res;
            this.result_backwards = JSON.parse(JSON.stringify(res)).reverse();
            this.loading = false;
            this.datacollection = {
              labels: this.result.map((x) =>
                this.formatDate(x["timestamp"] * 1000, true)
              ),
              datasets: [
                {
                  label: "Success",
                  backgroundColor: "green",
                  data: this.result.map((x) => {
                    if (x["judgement"] == true) {
                      return 1;
                    } else {
                      return 0;
                    }
                  }),
                },
                {
                  label: "Failure",
                  backgroundColor: "red",
                  data: this.result.map((x) => (x["judgement"] != true) * 1),
                },
              ],
            };
            this.display = true;
          })
          .catch((e) => {
            this.$store.commit("updateError", e);
            this.loading = false;
          });
      }
    },
  },
};
</script>

<style>
.small {
  max-width: 600px;
  margin: 150px auto;
}
</style>
