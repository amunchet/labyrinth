<template>
  <div class="about">
    <div class="outer_left">
      <Connector
        :verticals="connectorBottom"
        horizontals="1"
        color="orange"
        :style="
          'top: ' +
          offsetTop +
          'px; left: 32px; position: absolute; float: left;'
        "
      />
    </div>
    <div class="outer_right">
      <div class="outer">
        <div class="left">
          <div class="corner">
            <Host icon="VMWare" show_ports=0 />
          </div>
          <div class="routes">
            <Host passed_class="main" icon="Router" ref="start_1"/>
          </div>
        </div>

        <div class="right">
          <h2 class="text-right subnet">192.168.0</h2>
          <div class="flexed">
            <div class="grouped">
              <h2 class="light">Linux Servers</h2>
              <div class="flexed">
                <Host passed_class="main" icon="Linux" />
                <Host passed_class="main" icon="Linux" />
                <Host passed_class="main" icon="Linux" />
                <Host passed_class="main" icon="Linux"  />
              </div>
            </div>
            <div class="grouped">
              <h2 class="light">Windows Servers</h2>
              <div class="flexed">
                <Host passed_class="main" icon="Windows" />
                <Host passed_class="main" icon="Windows" />
                <Host passed_class="main" icon="Windows" />
                <Host passed_class="main" icon="Windows" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="outer orange-bg">
      <div class="left">
        <div class="corner" ref="end_1">
          <Host icon="Cloud" show_ports=0 />
        </div>
        <div class="routes">
          <Host passed_class="main" icon="Wireless"/>
        </div>
      </div>

      <div class="right">
        <h2 class="text-right subnet orange">192.168.1</h2>
        <div class="flexed">
          <div class="grouped">
            <h2 class="light">Linux Servers</h2>
            <div class="flexed">
              <Host passed_class="main" icon="Phone" />
              <Host passed_class="main" icon="Phone" />
              <Host passed_class="main" icon="Phone" />
              <Host passed_class="main" icon="Phone" />
            </div>
          </div>
          <div class="grouped">
            <h2 class="light">Windows Clients</h2>
            <div class="flexed">
              <Host passed_class="main" icon="Tower" />
              <Host passed_class="main" icon="Tower" />
              <Host passed_class="main" icon="Tower" />
              <Host passed_class="main" icon="Tower" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import Connector from "@/components/Connector";
import Host from "@/components/Host";
export default {
  data() {
    return {
      offsetTop: 10,
      connectorBottom: 10,
    };
  },
  components: {
    Connector,
    Host,
  },
  methods: {
    findTop: function () {
      console.log(this.$refs);
      console.log(this.$refs["start_1"].$el.offsetTop);
      this.offsetTop =
        this.$refs["start_1"].$el.offsetTop * 1;
      
      console.log(this.$refs["end_1"])
      var bottom = this.$refs["end_1"].offsetTop * 1
      console.log(bottom)
      this.connectorBottom = Math.ceil((this.offsetTop - this.$refs["end_1"].offsetTop * 1)/50) * -1 - 1
      this.$forceUpdate();
    },
  },
  watch: {
    $refs: {
      start_1: function (val) {
        if (val.$el != undefined) {
          this.findTop();
        }
      },
    },
  },
  created: function(){
    window.addEventListener('resize', this.findTop)
  },
  mounted: function () {
    this.findTop();
  },
};
</script>
<style lang="scss">
body,
html {
  padding: 0;
  margin: 0;
  background-color: #fffeff;
}

h2 {
  width: 100%;
  clear: both;
  font-family: Helvetica Neue, Helvetica, Arial, sans-serif;
  font-weight: 1;
  margin: 0;
  padding: 0;
  margin-bottom: 5px;
}
h2.light{
  text-align: left;
  color: #bdbdbf;
  padding-bottom: 5px;
  border-bottom: 1px solid #bdbdbf;
  margin-bottom: 15px;
}
h2.subnet{
    font-family: fantasy, system-ui, 'sans-serif';
    font-size: 28pt;
    color: #5b5b56;
    font-weight: 100;
}
.text-right {
  text-align: right;
}
.outer_left {
  width: 10%;
  min-width: 100px;
  float: left;
}

.flexed {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-around;
  align-items: stretch;
}

.outer {
  background-color: #efefed;
  min-height: 300px;
  overflow: hidden;
  margin: auto;
  margin-left: 100px;
  margin-right: 1%;
  margin-top: 20px;
  border-radius: 1.25rem;
}

.left {
  width: 15%;
  min-width: 150px;
  float: left;
  min-height: 300px;
}
.right {
  overflow: hidden;
  padding-top: 10px;
  margin: 20px;
  margin-top: 0;
}
.corner {
  position: relative;
  top: 0;
  left: 0;
  border-radius: 0 0 2rem 0;
  min-width: 150px;
  background-color: lightblue;
  box-shadow: 10px 10px 39px -12px rgba(0, 0, 0, 0.75);
  -webkit-box-shadow: 10px 10px 39px -12px rgba(0, 0, 0, 0.75);
  -moz-box-shadow: 10px 10px 39px -12px rgba(0, 0, 0, 0.75);
  height: 100px;
  margin-right: 20px;
}
.routes {
  width: 100%;
}
.grouped {
  border-radius: 1rem;
  width: 30%;
  margin: 1%;
  text-align: center;
  background-color: #dfdfde;
  padding: 20px;
  margin: 10px;
  flex-grow: 1;
}
.grouped .inner {
  display: flex;
}
.routes {
  padding: 20px;
  margin: 10px;
  text-align: center;
}

</style>
