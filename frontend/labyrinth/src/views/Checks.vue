<template>
  <b-container class="text-left mt-3">
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
          ><b>Display Name</b><br />
          <span class="helptext">Display name. E.g. cpu-34</span>
        </b-col>
        <b-col>
          <b-input
            lazy
            :state="!$v.selected_service.display_name.$invalid"
            v-model="selected_service.display_name"
            placeholder="E.g. cpu-32"
        /></b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Exact Service Name</b><br />
          <span class="helptext">Name of the service.</span>
        </b-col>
        <b-col>
          <b-input
            lazy
            :state="!$v.selected_service.name.$invalid"
            v-model="selected_service.name"
            placeholder="E.g. cpu"
        /></b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Type</b><br />
          <span class="helptext">Service type</span>
        </b-col>
        <b-col>
          <b-input
            lazy
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
          <b-input
            lazy
            :state="!$v.selected_service.metric.$invalid"
            v-model="selected_service.metric"
            placeholder="E.g. usage_user"
        /></b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Field</b><br />
          <span class="helptext"
            >Child field - usually the same as Metric.</span
          >
        </b-col>
        <b-col>
          <b-input
            lazy
            :state="!$v.selected_service.field.$invalid"
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
            :state="!$v.selected_service.comparison.$invalid"
          />
          <div
            v-if="selected_service.comparison == 'time'"
            class="helptext mt-2"
          >
            Time means number of seconds before current time. For example, if
            the metric time is 100 seconds in the past, setting a value of 101
            would result in false. A value of 99 would be true.
          </div>
        </b-col>
      </b-row>
      <b-row>
        <b-col
          ><b>Value</b><br />
          <span class="helptext">Target value of the service</span>
        </b-col>
        <b-col>
          <b-input
            lazy
            v-model="selected_service.value"
            :state="!$v.selected_service.value.$invalid"
            placeholder="E.g. 100"
        /></b-col>
      </b-row>
      <hr />
      <b-row>
        <b-col>
          <b>Tags</b>
          <div class="helptext mt-2">
            Additional tags to match. Used for when there are multiple services
            checking different resources (i.e. multiple disks being checked for
            space)
          </div>
        </b-col>
        <b-col>
          Name: <br />
          <b-input
            lazy
            class="mb-2"
            v-model="selected_service.tag_name"
            placeholder="E.g. cpu"
          />
          Value: <br />
          <b-input
            lazy
            v-model="selected_service.tag_value"
            placeholder="E.g. cpu-total"
          />
        </b-col>
      </b-row>
    </b-modal>
    <b-row class="ml-0 pl-0 mr-0 pr-0">
      <b-col class="ml-0 pl-0">
        <b-input
          lazy
          class="float-left"
          v-model="services_filter"
          placeholder="Filter Services"
        />
      </b-col>
      <b-col class="mr-0 pr-0">
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
    <div class="metrics-table">
      <b-spinner class="m-2" v-if="servicesLoading" />
      <b-table
        responsive
        :filter="services_filter"
        :fields="service_fields"
        :items="services"
        striped
        v-else
      >
        <template v-slot:cell(display_name)="row">
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
          {{ row.item.display_name }}
        </template>
        <template v-slot:cell(value)="row">
          {{ row.item.comparison }}&nbsp;{{ row.item.value }}
        </template>
      </b-table>
    </div>
    <hr />
    <h2 class="mt-2 mb-2">Latest Metrics</h2>
    <b-row class="ml-0 pl-0 mt-2 mb-2 mr-0 pr-0">
      <b-col cols="6" class="ml-0 pl-0 pr-0 mr-0">
        <b-input lazy v-model="metrics_filter" placeholder="Filter metrics" />
      </b-col>
      <b-col class="text-right overflow-hidden mr-0 pr-0">
        <b-button variant="primary" @click="loadMetrics()" class="float-right">
          <font-awesome-icon icon="sync" size="1x" />
        </b-button>
      </b-col>
    </b-row>

    <div class="metrics-table mb-2">
      <b-table
        :items="metrics"
        responsive
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
          {{ ("" + cell.item.timestamp).split(".")[0] }}
        </template>
      </b-table>
      <b-spinner v-else class="m-2" />
    </div>
    <hr />
  </b-container>
</template>
<script>
import Helper from "@/helper";
import { required } from "vuelidate/lib/validators";
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
      comparison_types: ["greater", "less", "equals", "time"],
      service_fields: [
        "display_name",
        "name",
        "type",
        "field",
        "metric",
        "value",
      ],
      metrics: [],
      checksLoaded: true,
    };
  },
  validations: {
    selected_service: {
      display_name: { required },
      type: { required },
      name: { required },
      metric: { required },
      field: { required },
      comparison: { required },
      value: { required },
    },
  },
  methods: {
    deleteService: /* istanbul ignore next */ function (name) {
      let auth = this.$auth;

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
      let auth = this.$auth;
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
      let auth = this.$auth;
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

      if (this.$v.selected_service.$invalid) {
        this.$store.commit(
          "updateError",
          "Error: Please correct fields before submitting"
        );
        return -1;
      }

      let auth = this.$auth;
      let formData = new FormData();
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
