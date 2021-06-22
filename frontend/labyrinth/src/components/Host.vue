<template>
  <div class="main">
    <div class="top">
        <div v-for="(icon, idx) in icons" v-bind:key="idx">
          <component :is="myComponent[icon]" /> 

        </div>
      <h3>192.168.0.7</h3>
    </div>
    <div class="bottom">
      <div class="row">
        <div class="first">All Statuses</div>
        <div class="second">OK</div>
      </div>
    </div>
  </div>
</template>
<script>
export default {
  name: "Host",
  data() {
    return {
      icons: ["Phone", "VMWare"],
      components: {}, 
      myComponent: {},
    };
  },
  created() {
    for(var i = 0; i<this.icons.length; i++){
      let componentName = this.icons[i]
      this.myComponent[this.icons[i]] = () => import('../components/icons/' + componentName + '.vue')
    }
  },
};
</script>
<style scoped>
.main {
  border: 1px solid red;
  border-radius: 0.25rem;
  width: 150px;
  display: block;
}
.top {
  padding-top: 10px;
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
