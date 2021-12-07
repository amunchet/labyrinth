<template>
  <b-container class="text-left">
    <h2>Create/Edit a Service</h2>

    <b-modal id="add_service" title="Add/Edit Service" @ok="saveCheck">
      <template #modal-footer="{ ok, cancel }">
        <div style="width: 100%">
          <b-button
            @click="deleteService(selected_service.name)"
            variant="danger"
            v-if="selected_service['_id'] != undefined"
            class="float-left"
            >Delete</b-button
          >
          <b-button variant="primary" @click="ok()" class="ml-2 float-right">
            OK
          </b-button>

          <b-button @click="cancel()" class="float-right"> Cancel </b-button>
        </div>
      </template>

      <b-row>
        <b-col
          ><b>Name</b><br />
          <span class="helptext">Name of the service</span>
        </b-col>
        <b-col>
          <b-input v-model="selected_service.name" placeholder="E.g. cpu"
        /></b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Type</b><br />
          <span class="helptext">Service type</span>
        </b-col>
        <b-col>
          <b-input
            disabled
            v-model="selected_service.type"
            placeholder="E.g. check"
        /></b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Metric</b><br />
          <span class="helptext">Specific service metric</span>
        </b-col>
        <b-col>
          <b-input v-model="selected_service.metric" placeholder="E.g. usage_user" 
        /></b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Field</b><br />
          <span class="helptext">Child field - usually the same as Metric.</span>
        </b-col>
        <b-col>
          <b-input
            v-model="selected_service.field"
            placeholder="E.g. usage_user"
        /></b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Comparison</b><br />
          <span class="helptext">Comparison operator on the service</span>
        </b-col>
        <b-col>
          <b-select
            :options="comparison_types"
            v-model="selected_service.comparison"
          />
        </b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Value</b><br />
          <span class="helptext">Target value of the service</span>
        </b-col>
        <b-col>
          <b-input v-model="selected_service.value" placeholder="E.g. 100"
        /></b-col>
      </b-row>
    </b-modal>

    <div class="metrics-table">
      <b-row class="ml-0 pl-0">
        <b-col class="ml-0 pl-0">
          <b-input class="float-left" v-model="services_filter" placeholder="Filter Services" />
        </b-col>
        <b-col>
          <b-button
            @click="
              () => {
                selected_service = {
                  type: 'check',
                };
                $bvModal.show('add_service');
              }
            "
            variant="success"
            class="float-right"
            >+ Add Service</b-button
          >
        </b-col>
      </b-row>
      <b-spinner class="m-2" v-if="servicesLoading" />
      <b-table
        :filter="services_filter"
        :fields="service_fields"
        :items="services"
        striped
        v-else
      >
        <template v-slot:cell(name)="row">
          <b-button
            variant="link"
            class="shadow-none"
            @click="
              () => {
                selected_service = row.item;
                $bvModal.show('add_service');
              }
            "
          >
            <font-awesome-icon icon="edit" size="1x" />
          </b-button>
          {{ row.item.name }}
        </template>
      </b-table>
    </div>
    <hr />
    <h2 class="mt-2 mb-2">Latest Metrics</h2>
    <div class="metrics-table mb-2">
      <b-row class="ml-0 pl-0">
        <b-col cols="6" class="ml-0 pl-0">
      <b-input class="mt-2 mb-2" v-model="metrics_filter"  placeholder="Filter metrics" />
        </b-col>
      </b-row>
      <b-table
        :items="metrics"
        striped
        :filter="metrics_filter"
        :fields="['name', 'tags', 'fields', 'timestamp']"
        v-if="checksLoaded"
      >
        <template v-slot:cell(fields)="row">
          <div v-for="(item, idx) in row.item.fields" v-bind:key="idx">
            {{ idx }} : {{ item }} <br />
          </div>
        </template>
        <template v-slot:cell(tags)="row">
          <div v-for="(item, idx) in row.item.tags" v-bind:key="idx">
            {{ idx }} : {{ item }} <br />
          </div>
        </template>
        <template v-slot:cell(timestamp)="cell">
          {{ new Date(cell.item.timestamp * 1000).toLocaleDateString() }}
          {{ new Date(cell.item.timestamp * 1000).toLocaleTimeString() }}
        </template>
      </b-table>
      <b-spinner v-else class="m-2" />
    </div>
    <hr />
  </b-container>
</template>
<script>
import Helper from "@/helper";
export default {
  data() {
    return {
      services_filter: "",
      metrics_filter: "",

      servicesLoading: false,
      selected_service: {
        type: "check",
      },
      services: [],
      comparison_types: ["greater", "less", "equal"],
      service_fields: [
        "name",
        "type",
        "field",
        "metric",
        "comparison",
        "value",
      ],
      metrics: [],
      checksLoaded: true,
    };
  },
  methods: {
    deleteService: /* istanbul ignore next */ function (name) {
      var auth = this.$auth;

      this.$bvModal
        .msgBoxConfirm("Confirm deleting service " + name + "?")
        .then((value) => {
          if (!value) {
            return false;
          }
          Helper.apiDelete("service", name, auth)
            .then((res) => {
              this.$store.commit("updateError", res);
              this.loadServices();
              this.$bvModal.hide("add_service");
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        })
        .catch((err) => {
          this.$store.commit("updateError", err);
        });
    },
    loadServices: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      this.servicesLoading = true;
      Helper.apiCall("services", "all", auth)
        .then((res) => {
          this.services = res;
          this.servicesLoading = false;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
          this.servicesLoading = false;
        });
    },
    loadMetrics: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      this.checksLoaded = false;
      Helper.apiCall("metrics", "25", auth)
        .then((res) => {
          this.metrics = res;
          this.checksLoaded = true;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
          this.checksLoaded = true;
        });
    },
    saveCheck: /* istanbul ignore next */ function (e) {
      e.preventDefault();
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.selected_service));
      Helper.apiPost("service", "", "", auth, formData)
        .then((res) => {
          this.loadServices();
          this.$store.commit("updateError", res);
          this.$bvModal.hide("add_service");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadServices();
      this.loadMetrics();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
.row {
  margin: 1rem;
}
.helptext {
  font-size: 8pt;
  color: grey;
  font-family: Arial, sans-serif;
}
.metrics-table {
  height: 400px;
  overflow-y: scroll;
  overflow-x: hidden;
}
</style>
