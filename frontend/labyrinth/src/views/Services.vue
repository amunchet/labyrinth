<template>
  <b-container style="min-width: 90%">
    <b-row>
      <b-col cols="7">
        <h4>Available Telegraf Services</h4>

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
      <b-col class="ml-1">
        <b-row>
          <b-col class="text-left"><h4>Created Configuration File</h4></b-col>
          <b-col >
            <b-select 
              v-model="selected_host"
              :options="hosts"
            />
          </b-col>
          <b-col
            cols="1"
            ><b-button variant="success" class="float-right">
              <font-awesome-icon icon="save" size="1x" @click="saveConf"/> </b-button
          ></b-col> </b-row
        ><b-row class="mt-1">
          <b-col 
            ><b-button class="float-left" variant="primary">Test Configuration File</b-button></b-col
          >
        </b-row>
        <div class="overflow-hidden">
          <b-button
            class="float-right m-0 p-0 shadow-none"
            variant="link"
            @click="output_data = {}"
            >Clear All</b-button
          >
        </div>

        <hr />

        <div v-if="output_data">
          <ServiceComponent
            v-for="(section, idx) in output_data"
            v-bind:key="idx"
            :name="idx"
            :data="section"
            :start_minimized="true"
            :isParent="true"
            :isWrite="true"
            depth="0"
            @update="
              (name, val) => {
                output_data[name] = val;
                autoSave();
                $forceUpdate();
              }
            "
            @child_delete="
              (val) => {
                delete output_data[val];
                $forceUpdate();
              }
            "
          />
        </div>
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
      autoSaved: false,
      selected_host: "",
      hosts: [],
    };
  },
  watch: {
    selected_host: function(val){
      if(val != ""){
        this.forceGlobalTag()
      }
    }
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

      var temp = JSON.parse(JSON.stringify(this.output_data));
      this.output_data = "";
      this.$forceUpdate();

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

      this.output_data = temp;
      this.forceGlobalTag()
      this.$forceUpdate();
    },

    forceGlobalTag: function(){
      // Any time we add, force global tags to be host
      if(this.output_data["global_tags"] == undefined){
        this.output_data["global_tags"] = {}
      }
      this.output_data["global_tags"]["id"] = this.selected_host


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

    getAutosave: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("redis", "autosave", auth)
        .then((res) => {
          this.output_data = res;
        })
        .catch(() => {
          this.output_data = {};
        });
    },
    autoSave: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.output_data));
      Helper.apiPost("redis", "", "autosave", auth, formData).catch(() => {
        this.autoSaved = false;
      });
    },
    listHosts: /* istanbul ignore next */ function(){
      var auth = this.$auth
      Helper.apiCall("hosts", "", auth).then(res=>{
        this.hosts = res.map(x=>{
          return{
            value: x.ip,
            text: x.ip
          } 
        })
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    saveConf: /* istanbul ignore next */ function(){
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.output_data));
      Helper.apiPost("save_conf","", this.selected_host, auth, formData).then(res=>{
        this.$store.commit('updateError', res)
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    }
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadStructure();
      this.getAutosave();
      this.listHosts()
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
h2{
  width: 100%;
}
</style>
