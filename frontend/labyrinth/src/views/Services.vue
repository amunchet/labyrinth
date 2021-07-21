<template>
  <b-container>
    <b-row>
      <b-col cols="7">
        <h4>Services</h4>
        <b-button variant="primary" class="m-2"
          >Load Services Template</b-button
        >

        <b-nav-form>
          <b-form-input
            size="sm"
            class="mr-sm-2"
            placeholder="Search"
            v-model="temp_filter"
            @blur="service_filter = temp_filter"
          ></b-form-input>
          <b-button
            size="sm"
            class="my-2 my-sm-0"
            @click="service_filter = temp_filter"
            >Search</b-button
          >
        </b-nav-form>
        <ServiceComponent
          v-for="(section, idx) in data"
          v-bind:key="idx"
          :name="idx"
          :data="section"
          :start_minimized="true"
          :isParent="true"
          :service_filter="service_filter"
        />
      </b-col>
      <b-col>
        <h4>Created Configuration File</h4>
        Hosts: <b-select />
        <b-button class="m-2">Save</b-button>
        <hr />
        <h4>Test Configuration File</h4>
        <b-button class="m-2">Run Test</b-button>
        <br />
        <textarea />
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
    };
  },
  methods: {
    loadStructure: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "get_structure", auth)
        .then((res) => {
          this.data = res;
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

<style scoped></style>
