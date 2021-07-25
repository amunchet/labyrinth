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
            @add="add"
            depth="0"
          />
        </div>
        <b-spinner class="m-2" v-else />
      </b-col>
      <b-col>
        <h4>Created Configuration File</h4>
        <b-select />
        <b-button class="m-2">Save</b-button>
        <hr />
        <br />
        <div 
          v-if="output_data"
          >
        <ServiceComponent
          v-for="(section, idx) in output_data"
          v-bind:key="idx"
          :name="idx"
          :data="section"
          :start_minimized="true"
          :isParent="true"
          depth="0"
        />
        </div>

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
      output_data: {},
      temp_filter: "",
      data: [],
      loaded: false,
    };
  },
  methods: {
    add: function (data) {
      // Handle undefined at top
      this.$forceUpdate();
      var output = JSON.parse(data);

      // Need to handle deep nests - assume every parent is an object, except for the arrays

      var item = output.item;
      var parent = output.parent.replace("undefined.", "") || "";
      var name = output.name;

      var temp = JSON.parse(JSON.stringify(this.output_data))
      this.output_data = ""
      this.$forceUpdate()

      const set = (obj, path, val) => {
        const keys = path.split(".");
        const lastKey = keys.pop();
        const lastObj = keys.reduce((obj, key) => {
          return (obj[key] = obj[key] || {});
        }, obj);
        lastObj[lastKey] = val;
      };
      var outtie = parent + "." + name;

      set(temp, outtie, item);

      if (temp[""] != undefined) {
        var keys = Object.keys(temp[""]);
        for (var i = 0; i < keys.length; i++) {
          var next_key = keys[i];
          if (temp[next_key] == undefined) {
            temp[next_key] = temp[""][next_key];
          }
        }
        delete temp[""];
      }

      this.output_data = temp

      this.$forceUpdate();
    },

    loadStructure: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "get_structure", auth)
        .then((res) => {
          this.data = res;
          this.loaded = true;
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
textarea {
  width: 100%;
  min-height: 400px;
}
</style>
