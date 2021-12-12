<template>
  <b-modal id="service_detail" title="Service Details" size="xl">
    <line-chart
      v-if="display"
      height="100px"
      :chart-data="datacollection"
    ></line-chart>

    <b-table
      :items="result_backwards"
      v-if="!loading"
      :fields="['name', 'tags', 'fields', 'timestamp', 'judgement']"
    >
      <template v-slot:cell(timestamp)="row">
        {{ formatDate(row.item.timestamp * 1000) }}
        {{ formatDate(row.item.timestamp * 1000, true) }}
      </template>
    </b-table>
    <b-spinner v-else />
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
    };
  },
  mounted() {},
  methods: {
    formatDate: Helper.formatDate,
  },
  watch: {
    data: /* istanbul ignore next */ async function (inp) {
      if (inp != "" && inp != undefined && inp) {
        var auth = this.$auth;
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
