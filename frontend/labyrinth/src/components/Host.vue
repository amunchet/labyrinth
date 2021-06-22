<template>
  <div class="main">
    <div class="top">
      <span>.176</span>
      <br />
      <component :is="myComponent[icon]" />
    </div>
    <div class="bottom">
      <table>
        <tr v-for="j in 5" v-bind:key="j">
          <div v-if="j % 2" class="padding:1px;">
            <td class="lightblue-bg" v-for="i in 5" v-bind:key="i">&nbsp;&nbsp;&nbsp;</td>
          </div>
          <div v-else class="padding:1px;">
            <td class="red-bg" v-for="i in 5" v-bind:key="i">&nbsp;&nbsp;&nbsp;</td>
          </div>
        </tr>
      </table>
    </div>
  </div>
</template>
<script>
export default {
  name: "Host",
  props: ["icon"],
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
      this.myComponent[this.icons[i]] = () =>
        import("../components/icons/" + componentName + ".vue");
    }
  },
};
</script>
<style scoped>
.main {
  border: 1px dotted #efefed;
  padding: 5px;
  margin: 3px;
  border-radius: 0.25rem;
  width: 150px;
  display: block;
}
.top {
  padding-top: 10px;
  display: block;
}
.row {
  width: 100%;
  overflow: hidden;
  border-top: 1px solid #b6b6be;
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
