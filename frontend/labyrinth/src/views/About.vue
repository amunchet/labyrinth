<template>
  <div class="about">
    <hr />

    <Connector
      verticals="10"
      horizontals="2"
      color="green"
      style="top: 120px; left: 15px; position: absolute; float: left"
    />
    <Connector verticals="20" horizontals="2" color="orange" style="position:absolute; top:150px; left:40px;" />

    <div class="outer">
      <div class="left">
        <div class="corner">
          <Host icon="VMWare"/>
        </div>
        <div class="routes">
          <Host icon="Router" />
        </div>
      </div>

      <div class="right">
        <h2>192.168.0.*</h2>
        <div class="grouped">
          <h2>Linux</h2>
          <div>
            <Host icon="Linux" />
            <Host icon="Linux" />
            <Host icon="Linux" />
            <Host icon="Linux" />
          </div>
        </div>
        <div class="grouped">
          <h2>Windows</h2>
          <div>
            <Host icon="Windows"/>
            <Host icon="Windows"/>
            <Host icon="Windows"/>
            <Host icon="Windows"/>
          </div>
        </div>
      </div>
    </div>

    <div class="outer orange-bg">
      <div class="left">
        <div class="corner">
          <Host icon="Cloud"/>
        </div>
        <div class="routes">
          <Host icon="Wireless"/>
        </div>
      </div>

      <div class="right">
        <h2>192.168.0.*</h2>
        <div class="grouped">
          <h2>Linux</h2>
          <div>
            <Host icon="Phone"/>
            <Host icon="Phone"/>
            <Host icon="Phone"/>
            <Host icon="Phone"/>
          </div>
        </div>
        <div class="grouped">
          <h2>Windows</h2>
          <div>
            <Host icon="Tower" />
            <Host icon="Tower" />
            <Host icon="Tower" />
            <Host icon="Tower" />
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
}

.outer {
  background-color: #efefed;
  min-height: 300px;
  overflow: hidden;
  margin: auto;
  margin-left: 100px;
  margin-right: 1%;
  margin-top: 20px;
  border-radius: 0.25rem;
}

.left {
  width: 25%;
  min-width: 150px;
  float: left;
  display: flex;
  min-height: 300px;
}
.corner {
  position: relative;
  top: 0;
  left: 0;
  border-radius: 0.25rem;
  background-color: #375775;
  color: white;
  min-width: 150px;
  height: 250px;
  border-right: 4px solid lightgrey;
  border-bottom: 4px solid lightgrey;
}
.routes {
  width: 100%;
}
.grouped {
    background-color: lightblue;
  float: right;
  min-width: 300px;
}
.grouped div {
  display: inline-flex;
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

.lightblue-bg{
  background-color: #83d3df;
}
.red-bg{
  background-color: #db7077;
}
.orange-bg{
  background-color: #ffab71;
}
.darkblue-bg{
  background-color: #375775;
}
.superlight-bg{
  background-color: #d8faff;
}
</style>
