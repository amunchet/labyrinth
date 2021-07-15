<template>
  <div class="dashboard">
    <div class="outer_left">
      <Connector 
        :verticals="connectorBottom[0]" 
        horizontals="1" 
        color="orange" 
        :style="
          'top: ' +
          offsetTop[0] +
          'px; left: ' + 32 + 
          'px; position: absolute; float: left;'
        " />
    </div>
    <div class="outer_right">
      <b-button variant="link" class="add-button">
        <font-awesome-icon icon="plus" size="1x" /> New Subnet
      </b-button>
      <div :class="findClass(subnet)" v-for="(subnet, i) in full_data" v-bind:key="i">
        <div class="left">
          <div class="corner" :ref="'end_' + i">
            <Host :ip="subnet.origin.ip" :icon="subnet.origin.icon" show_ports="0"/>
          </div>
          <div class="routes">
            <Host :ip="subnet.links.ip" show_ports="0" passed_class="main" :ref="'start_' + i" :icon="subnet.links.icon" />
          </div>
        </div>
        <div class="right">
          <h2 :class="findTitleClass(subnet)">{{subnet.subnet}}</h2>
          <div class="flexed">
            <div class="grouped" v-for="(group, j) in subnet.groups" v-bind:key="j">
              <div class="overflow-hidden light p-0">
                <h2 class="float-left">{{group.name}}</h2>
                <font-awesome-icon class="float-right p-1 mt-1" icon="plus" size="2x" />
              </div>
              <div class="flexed">
                <Host v-for="(host, k) in group.hosts" v-bind:key="k" :ip="host.ip" passed_class="main" :icon="host.icon"/>
              </div>
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
      offsetTop: [],
      connectorBottom: [],
      connector_count: 1,
      full_data: [
        {
          subnet: "192.168.0",
          origin: {
            ip: "127.0.0.1",
            icon : "VMWare"
          },
          groups: [
            {
              name: "Linux Servers",
              hosts: [
                {
                  "ip" : "176",
                  "icon" : "Linux"
                },
                {
                  "ip" : "176",
                  "icon" : "Linux"
                },
                {
                  "ip" : "176",
                  "icon" : "Linux"
                },
                {
                  "ip" : "176",
                  "icon" : "Linux"
                },
              ]
            },
            {
              name: "Windows Servers",
              hosts: [
                {
                  "ip" : "176",
                  "icon" :  "Windows",
                },
                {
                  "ip" : "176",
                  "icon" : "Windows",
                },
                {
                  "ip" : "176",
                  "icon" : "Windows",
                },
                {
                  "ip" : "176",
                  "icon" : "Windows",
                },
              ]
            }
          ],
          links: {
            ref: "start_1",
            ip: ".175",
            icon: "Router",
            color: "orange"
          }
        },
        {
          subnet: "192.168.1",
          color: "orange",
          origin: {
            ref: "end_1",
            icon: "Cloud",
            ip: "10.8.0.6"
          },
          groups: [
            {
              name: "Linux Servers",
              hosts: [
                {
                  "ip" : "176",
                  "icon" : "Phone"
                },
                {
                  "ip" : "176",
                  "icon" : "Phone"
                },
                {
                  "ip" : "176",
                  "icon" : "Phone"
                },
                {
                  "ip" : "176",
                  "icon" : "Phone"
                },
              ]
            },
            {
              name: "Windows Servers",
              hosts: [
                {
                  "ip" : "176",
                  "icon" :  "Tower",
                },
                {
                  "ip" : "176",
                  "icon" : "Tower",
                },
                {
                  "ip" : "176",
                  "icon" : "Tower",
                },
                {
                  "ip" : "176",
                  "icon" : "Tower",
                },
              ]
            }
          ],
          links: {
            ref: "start_2",
            ip: ".176",
            icon: "Wireless",
            color: "blue"
          }
        }
      ]
    };
  },
  components: {
    Connector,
    Host,
  },
  methods: {
    findClass: function(subnet){
      if (subnet.color == undefined){
        return "outer"
      }else{
        return "outer " + subnet.color + "-bg"
      }
    },
    findTitleClass: function(subnet){
    if (subnet.color == undefined){
        return "text-right subnet"
      }else{
        return "text-right subnet " + subnet.color + ""
      }
    },
    findTop: function () {
      console.log(this.$refs)
      console.log("Connector count: " + this.connector_count)
      for(var i = 0; i<this.connector_count; i++){
        console.log("I: " + i)
        console.log("Top item")
        console.log(this.$refs["start_" + i][0].$el)
        this.offsetTop[i] = this.$refs["start_" + i][0].$el.offsetTop
        console.log("Top location:")
        console.log(this.offsetTop[i])
        var bottom = this.$refs["end_" + (i+1)][0].offsetTop * 1
        console.log("Bottom item:")
        console.log(this.$refs["end_" + (i+1)][0])
        console.log("Bottom location: ")
        console.log(bottom)
        this.connectorBottom[i] = Math.ceil((bottom - this.offsetTop[i])/50) * 1 -1
        console.log(this.connectorBottom[i])
      }
      this.$forceUpdate()

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
  created: function () {
    window.addEventListener("resize", this.findTop);
  },
  mounted: function () {
    this.findTop();
  },
};
</script>
<style lang="scss">
@import '@/assets/variables.scss';


body,
html {
  padding: 0;
  margin: 0;
  background-color: #fffeff;
}

.dashboard{
  margin-bottom: 20px;
}
.add-button{
  position: absolute;
  top: 55px;
  right: 2%;
  
}
h2 {
  width: 50%;
  clear: both;
  font-family: Helvetica Neue, Helvetica, Arial, sans-serif;
  font-weight: 1;
  margin: 0;
  padding: 0;
  margin-bottom: 5px;
}
.light {
  text-align: left;
  color: #bdbdbf;
  padding-bottom: 5px;
  border-bottom: 1px solid #bdbdbf;
  margin-bottom: 15px;
}
h2.subnet {
  font-family: fantasy, system-ui, "sans-serif";
  font-size: 28pt;
  color: #5b5b56;
  font-weight: 100;
  cursor: pointer;
  width: 100%;
}
h2.subnet:hover {
  text-decoration: underline;
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
  border-radius: 0 0 3rem 0;
  min-width: 150px;
  background-color: #fafafe;
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
