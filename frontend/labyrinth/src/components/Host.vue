<template>
  <div :class="passed_class">
    <div class="top">
      <span>{{ip}}</span>
      <br />
      <component :is="myComponent[icon]" />
    </div>
    <div class="bottom" v-if="show_ports != 0">
      <div class="table">
        <div class="row" v-for="j in 5" v-bind:key="j">
          <div v-if="j % 2" class="col">
            <div class="lightblue-bg col" v-for="i in 3" v-bind:key="i">
              &nbsp;&nbsp;&nbsp;
            </div>
          </div>
          <div v-else class="col">
            <div class="red-bg col" v-for="i in 3" v-bind:key="i">
              &nbsp;&nbsp;&nbsp;
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import {defineAsyncComponent} from 'vue'
export default {
  name: "Host",
  props: ["icon", "passed_class", "show_ports", "ip"],
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
  created() {
    for (var i = 0; i < this.icons.length; i++) {
      let componentName = this.icons[i];
      this.myComponent[this.icons[i]] = defineAsyncComponent(() =>
        import("../components/icons/" + componentName + ".vue"));
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
.row {
  width: 100%;
  overflow: hidden;
  border-top: 1px solid #b6b6be;
  display: flex;
  justify-content: space-around;
}
.col {
  float: left;
  width: 30%;
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
</style>
