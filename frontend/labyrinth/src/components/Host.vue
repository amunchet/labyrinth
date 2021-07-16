<template>
  <div :class="passed_class">
    <div class="top">
      <span>{{ ip }}</span>
      <br />
      <component :is="myComponent[icon]" />
    </div>
    <div class="bottom" v-if="show_ports != 0">
      <div class="table mb-0">
        <div class="host_row">
          <div class="host_col text-success">
            <font-awesome-icon icon="chart-area" size="1x" />
          </div>
          <div class="host_col text-warning">
            <font-awesome-icon icon="memory" size="1x" />
          </div>
          <div class="host_col text-danger">
            <font-awesome-icon icon="database" size="1x" />
          </div>
        </div>
      </div>

      <div class="table">
        <div class="host_row">
          <div class="host_col">
            <div
              :class="determineClass(service)"
              v-for="(service, idx) in services"
              v-bind:key="idx"
              @click="()=>{
                  $bvModal.show('service_detail')
                  }"
            >
              &nbsp;&nbsp;&nbsp;
            </div>
          </div>
        </div>
        <b-button class="add_button" @click="()=>{
            this.$emit('hostClicked')
            $bvModal.show('create_edit_host')
            }">
          <font-awesome-icon icon="cog" size="1x" />
        </b-button>
      </div>
    </div>
  </div>
</template>
<script>
// Vue 3 code
//import { defineAsyncComponent } from "vue";
export default {
  name: "Host",
  props: ["icon", "passed_class", "show_ports", "ip", "services"],
  data() {
    return {
      icons: [
        "Camera",
        "Cloud",
        "Linux",
        "NAS",
        "Phone",
        "Router",
        "Speaker",
        "Tower",
        "VMWare",
        "Windows",
        "Wireless",
      ],
      components: {},
      myComponent: {},
    };
  },
  methods: {
    determineClass: function (service) {
      if (service.state == false) {
        return "red-bg host_col darkgrey hover";
      }
      return "green-bg host_col darkgrey hover";
    },
  },
  created() {
    for (var i = 0; i < this.icons.length; i++) {
      let componentName = this.icons[i];
      // Vue 3 code
      /*
      this.myComponent[this.icons[i]] = defineAsyncComponent(() =>
        import("../components/icons/" + componentName + ".vue")
      );
      */
      this.myComponent[this.icons[i]] = () =>
        import("../components/icons/" + componentName + ".vue");
    }
  },
};
</script>
<style scoped>
.main {
  padding: 10px;
  border-radius: 1rem;
  margin: 1%;
  text-align: center;
  display: block;
  border: 1px solid #fefefd;
  min-width: 120px;
  max-width: 150px;
  box-shadow: 5px 5px 39px -12px rgba(0, 0, 0, 0.75);
  -webkit-box-shadow: 5px 5px 39px -12px rgba(0, 0, 0, 0.75);
  -moz-box-shadow: 5px 5px 39px -12px rgba(0, 0, 0, 0.75);
}
.top {
  padding-top: 10px;
  display: block;
}
.hover{
    cursor: pointer;
}
.host_row {
  width: 100%;
  overflow: hidden;
  border-top: 1px solid #b6b6be;
  display: flex;
  justify-content: space-around;
}
.host_col {
  float: left;
  width: 31.33%;
  margin: 1%;
  flex-grow: 1;
}
.first {
  float: left;

  padding-top: 10px;
  padding-bottom: 10px;
  text-align: center;
}
.second {
  float: right;
  background-color: #83d3df;

  padding-top: 10px;
  padding-bottom: 10px;
  text-align: center;
  min-width: 25%;
  font-weight: bold;
}
.add_button {
  width: 100%;
  margin-top: 10px;
  background-color: #efefed;
  border: 1px dotted #bfbfbd;
  color: darkgrey;
  padding: 0;
}
</style>
