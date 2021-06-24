<template>
  <div class="about">
    <div class="outer_left">
      <Connector
        verticals="10"
        horizontals="1"
        color="#375775"
        style="top: 325px; left: 32px; position: absolute; float: left"
      />
      <Connector
        verticals="20"
        horizontals="2"
        color="#db7077"
        style="position: absolute; top: 650px; left: 20px; float: left"
      />
    </div>
    <div class="outer_right">
      <div class="outer">
        <div class="left">
          <div class="corner">
            <Host icon="VMWare" />
          </div>
          <div class="routes">
            <Host passed_class="main" icon="Router" />
          </div>
        </div>

        <div class="right">
          <h2 class="text-right">192.168.0.*</h2>
          <div class="flexed">
            <div class="grouped">
              <h2>Linux</h2>
              <div class="flexed">
                <Host  passed_class="main" icon="Linux" />
                <Host passed_class="main"  icon="Linux" />
                <Host  passed_class="main" icon="Linux" />
                <Host passed_class="main"  icon="Linux" />
              </div>
            </div>
            <div class="grouped">
              <h2>Windows</h2>
              <div class="flexed">
                <Host  passed_class="main" icon="Windows" />
                <Host  passed_class="main" icon="Windows" />
                <Host  passed_class="main" icon="Windows" />
                <Host  passed_class="main" icon="Windows" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="outer orange-bg">
      <div class="left">
        <div class="corner">
          <Host icon="Cloud" />
        </div>
        <div class="routes">
          <Host passed_class="main" icon="Wireless" />
        </div>
      </div>

      <div class="right">
        <h2 class="text-right">192.168.0.*</h2>
        <div class="flexed">
          <div class="grouped">
            <h2>Linux</h2>
            <div class="flexed">
              <Host passed_class="main" icon="Phone" />
              <Host passed_class="main" icon="Phone" />
              <Host passed_class="main" icon="Phone" />
              <Host passed_class="main" icon="Phone" />
            </div>
          </div>
          <div class="grouped">
            <h2>Windows</h2>
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
  data() {},
  components: {
    Connector,
    Host,
  },
};
</script>
<style>
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
.text-right{
  text-align: right;
}
.outer_left {
  width: 10%;
  min-width: 100px;
  float: left;
}

.flexed {
  display: flex;
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
  width: 80%;
  overflow: hidden;
  padding-top: 10px;
}
.corner {
  position: relative;
  top: 0;
  left: 0;
  border-radius: 0 0 5rem 0;
  min-width: 150px;
  background-color: lightblue;
  box-shadow: 10px 10px 39px -12px rgba(0,0,0,0.75);
-webkit-box-shadow: 10px 10px 39px -12px rgba(0,0,0,0.75);
-moz-box-shadow: 10px 10px 39px -12px rgba(0,0,0,0.75);
  height: 250px;
  margin-right:20px;
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
  padding:20px;
  margin: 10px;
  flex-grow: 1;
}
.grouped .inner {
  display: flex;
}
.routes{
  padding: 20px;
  margin: 10px;
  text-align: center;
}
/* Color Theme Swatches in Hex */
.lightblue {
  color: #83d3df;
}
.red {
  color: #db7077;
}
.orange {
  color: #ffab71;
}
.darkblue {
  color: #375775;
}
.superlight {
  color: #d8faff;
}

.lightblue-bg {
  background-color: #83d3df;
}
.red-bg {
  background-color: #db7077;
}
.orange-bg {
  background-color: #ffab71;
}
.darkblue-bg {
  background-color: #375775;
}
.superlight-bg {
  background-color: #d8faff;
}
</style>
