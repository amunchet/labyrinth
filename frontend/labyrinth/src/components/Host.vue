<template>
  <div
    draggable
    :class="'noselect ' + passed_class + ' ' + drag_class"
    @dragstart="drag_start(ip)"
    @dragend="drag_end"
  >
    <div class="top">
      <div :class="monitor ? 'number' : 'number unmonitored'">
        .{{ ip.split(".")[ip.split(".").length - 1] }}
      </div>

      <div
        v-if="host != undefined && host != '' && host.length > 15"
        class="title"
      >
        {{ host.substr(0, 15) }}...
      </div>
      <div v-else-if="host != ''" class="title">{{ host }}</div>
      <div class="title" v-else>-</div>
      <div class="pt-1" style="height: 50px">
        <img
          v-if="
            icons.indexOf(icon.charAt(0).toUpperCase() + icon.slice(1)) != -1
          "
          :src="
            '/icons/' +
            myComponent[icon.charAt(0).toUpperCase() + icon.slice(1)]
          "
        />
        <img v-else :src="'/icons/' + myComponent['Default']" />
      </div>
    </div>
    <div class="bottom" v-if="show_ports != 0">
      <div class="table mb-0">
        <div class="host_row">
          <div
            class="host_col text-success"
            v-if="services.filter((x) => x.name == cpu).length"
          >
            <font-awesome-icon
              :class="
                services.filter((x) => x.name == cpu).map((x) => x.state)[0]
                  ? 'text-success'
                  : 'text-danger'
              "
              icon="chart-area"
              size="1x"
            />
          </div>
          <div
            class="host_col text-warning"
            v-if="services.filter((x) => x.name == mem).length"
          >
            <font-awesome-icon
              :class="
                services.filter((x) => x.name == mem).map((x) => x.state)[0]
                  ? 'text-success'
                  : 'text-danger'
              "
              icon="memory"
              size="1x"
            />
          </div>
          <div
            class="host_col"
            v-if="services.filter((x) => x.name == hd).length"
          >
            <font-awesome-icon
              :class="
                services.filter((x) => x.name == hd).map((x) => x.state)[0]
                  ? 'text-success'
                  : 'text-danger'
              "
              icon="database"
              size="1x"
            />
          </div>
        </div>
      </div>

      <div class="table">
        <div class="host_row">
          <div class="host_col flexed">
            <div
              :class="'overflow-hidden ' + determineClass(service)"
              style="height: 24px"
              v-for="(service, idx) in services"
              @mouseover="
                () => {
                  service['hover'] = true;
                  $forceUpdate();
                }
              "
              @mouseleave="
                () => {
                  service['hover'] = false;
                  $forceUpdate();
                }
              "
              v-bind:key="idx"
              @click="
                () => {
                  $emit('service', service);
                  $bvModal.show('service_detail');
                }
              "
            >
              <span v-if="service['hover']" class="small_text">
                {{ service.name.replace("_", " ") }}
              </span>
              <span v-else>&nbsp;&nbsp;&nbsp;</span>
            </div>
          </div>
        </div>
        <b-button
          class="add_button"
          @click="
            () => {
              this.$emit('hostClicked');
              $bvModal.show('create_edit_host');
            }
          "
        >
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
  props: [
    "icon",
    "passed_class",
    "show_ports",
    "ip",
    "services",
    "cpu",
    "mem",
    "hd",
    "host",
    "monitor",
  ],
  data() {
    return {
      icons: [
        "Default",
        "Camera",
        "Cloud",
        "Linux",
        "NAS",
        "Phone",
        "Printer",
        "CellPhone",
        "Router",
        "Speaker",
        "Tower",
        "VMWare",
        "Microsoft",
        "Wireless",
      ],
      drag_class: "",
      dragging_ip: "",
      components: {},
      myComponent: {},
    };
  },
  methods: {
    drag_start: function (ip) {
      this.drag_class = "dragging";
      this.dragging_ip = ip;
      this.$emit("dragStart", this.dragging_ip);
    },
    drag_end: function () {
      this.drag_class = "";
      this.dragging_ip = "";
      this.$emit("dragEnd");
    },
    determineClass: function (service) {
      if (service.state == -1) {
        return "orange-bg host_col darkgrey hover";
      }
      if (service.state == false) {
        return "red-bg host_col darkgrey hover";
      }
      return "green-bg host_col darkgrey hover";
    },
  },
  created() {
    for (var i = 0; i < this.icons.length; i++) {
      let componentName = this.icons[i];
      this.myComponent[this.icons[i]] = componentName + ".svg";
    }
  },
};
</script>
<style scoped>
.small_text {
  font-size: 8pt;
  line-height: 10px !important;
  color: #65656e;
}
.main {
  padding: 10px;
  border-radius: 1rem;
  margin: 1%;
  text-align: center;
  display: block;
  border: 1px solid #fefefd;
  min-width: 120px;
  max-width: 150px;
  box-shadow: 5px 5px 30px -12px rgba(0, 0, 0, 0.75);
  -webkit-box-shadow: 5px 5px 30px -12px rgba(0, 0, 0, 0.75);
  -moz-box-shadow: 5px 5px 30px -12px rgba(0, 0, 0, 0.75);
}
.dragging {
  border: 5px dashed rgba(0, 0, 0, 0.5) !important;
}
.noselect {
  user-select: none;
}
.top {
  padding-top: 10px;
  display: block;
}
.title {
  color: darkgrey;
  font-family: Helvetica, Arial;
  font-size: 12pt;
  min-width: 120px;
  width: 100%;
}
.number {
  /* border: 1px solid white; */
  width: 50px;
  margin: auto;
  border-radius: 0 0 5px 5px;
  margin-top: -20px;
  background-color: #fbfbfe;
  color: #34343e;
  font-weight: bold;
  /* box-shadow: 0 3px #cfcfce; */
  height: 25px;
  /* position: relative; */
  /* top: 0; */
  margin-bottom: 0.5rem;
  cursor: pointer;
}
.unmonitored {
  color: #dfdfde;
}
.hover {
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
