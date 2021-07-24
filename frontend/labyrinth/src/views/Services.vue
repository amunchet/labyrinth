<template>
  <b-container>
    <b-row>
      <b-col cols="7">
        <h4>Services</h4>

        <b-row>
          <b-form-input
            placeholder="Search (press tab to filter)"
            v-model="temp_filter"
            @blur="service_filter = temp_filter"
          ></b-form-input>
          
        </b-row>
        <hr />
        <div v-if="loaded">
        <ServiceComponent
          v-for="(section, idx) in data"
          v-bind:key="idx"
          :name="idx"
          :data="section"
          :start_minimized="true"
          :isParent="true"
          :service_filter="service_filter"
        />
        </div>
        <b-spinner class="m-2" v-else />
      </b-col>
      <b-col>
        <h4>Created Configuration File</h4>
        <b-select />
        <b-button class="m-2">Save</b-button>
        <hr />
        <h4>Test Configuration File</h4>
        <br />
        <textarea />

        <b-button class="m-2 mt-4">Run Test</b-button>
      </b-col>
    </b-row>
  </b-container>
</template>

<script>
import Helper from "@/helper";
import ServiceComponent from "@/components/Service";
export default {
  name: "Services",
  components: {
    ServiceComponent,
  },
  data() {
    return {
      service_filter: "",
      temp_filter: "",
      data: [],
      loaded: false,
    };
  },
  methods: {
    loadStructure: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "get_structure", auth)
        .then((res) => {
          this.data = res;
          this.loaded = true
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadStructure();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>

<style scoped>
textarea{
  width: 100%;
  min-height: 400px;
}
</style>
