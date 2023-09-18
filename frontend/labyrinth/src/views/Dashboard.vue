<template>
  <div class="dashboard">
    <!-- Modals -->
    <div class="overflow-hidden">
      <CreateEditSubnet :inp_subnet="selected_subnet" @update="loadData()" />
    </div>
    <CreateEditHost
      :inp_host="selected_host"
      @update="loadData()"
      :all_ips="all_ips_computed"
    />
    <HostMetric @update="loadData()" :data="selected_metric" />

    <GroupModal
      :selected_group="selected_group"
      :selected_subnet="selected_subnet"
      @updated="loadData()"
    />
    <!-- Main page -->

    <div v-if="!loading">
      <div class="outer_left">
        <!-- set verticals to some number to see the connector -->
        <!-- old: 
          :verticals="connectorBottom[0]"
        -->

        <div v-for="(item, idx) in originLinks" v-bind:key="idx">
          <Connector
            v-if="
              $refs['start_' + item.top_1] != undefined &&
              $refs['start_' + item.top_2] != undefined
            "
            :color="item.color"
            horizontal_width="50"
            :top_1="$refs['start_' + item.top_1][0].offsetTop"
            :top_2="$refs['start_' + item.top_2][0].offsetTop"
            :left="item.left"
            :key="
              $refs['start_' + item.top_1] +
              $refs['start_' + item.top_2] +
              item.color
            "
          />
        </div>
      </div>
      <div class="outer_right">
        <b-row class="outer pt-1 smartbar">
          <b-col cols="4">
            <b-input
              v-model="smartbar"
              lazy
              placeholder="Enter filter (i.e. port=22)"
            />
          </b-col>
          <b-col class="text-right">
            <b-button
              variant="link"
              @click="
                () => {
                  selected_subnet = '';
                  $bvModal.show('create_edit_subnet');
                }
              "
            >
              <font-awesome-icon icon="plus" size="1x" /> New Subnet
            </b-button>
          </b-col>
        </b-row>

        <div
          :class="'outer ' + (subnet.minimized ? 'minimized' : '')"
          :style="findClass(subnet)"
          v-for="(subnet, i) in parsed_data"
          v-bind:key="i"
        >
          <div
            class="left"
            v-if="
              (subnet.origin.ip != undefined && subnet.origin.ip != '') ||
              (subnet.links.ip != undefined && subnet.links.ip != '')
            "
          >
            <div class="corner pt-3" :ref="'start_' + subnet.origin.ip">
              <img
                :src="'/icons/' + capitalize(subnet.origin.icon) + '.svg'"
              /><br />
              {{ subnet.origin.ip }}
            </div>
          </div>
          <div class="right">
            <h2
              @click="
                () => {
                  $bvModal.show('create_edit_subnet');
                  selected_subnet = subnet;
                }
              "
              :style="findClass(subnet, 1)"
              class="text-right subnet"
            >
              {{ subnet.subnet }}
            </h2>
            <div
              class="flexed"
              v-if="subnet.groups != undefined && !subnet.minimized"
            >
              <div
                class="grouped"
                v-for="(group, j) in filterMonitored(
                  subnet.groups,
                  subnet.monitored
                )"
                v-bind:key="j"
                @drop="onDrop(group.name)"
                @dragover.prevent
                @dragenter.prevent
              >
                <div class="overflow-hidden light p-0">
                  <h2
                    class="group_headers float-left"
                    @click="
                      () => {
                        selected_group = group.name;
                        selected_subnet = subnet;
                        $bvModal.show('group_edit');
                      }
                    "
                  >
                    {{ group.name }}&nbsp;
                  </h2>
                  <font-awesome-icon
                    class="float-right p-1 mt-1 hover"
                    icon="plus"
                    size="2x"
                    @click="
                      () => {
                        selected_host = '';
                        $bvModal.show('create_edit_host');
                      }
                    "
                  />
                </div>
                <div class="chart" v-if="subnet.display == 'summary'">
                  <DoughnutChart
                    :chart-data="group.chart"
                    :options="chartOptions"
                  />
                </div>
                <div
                  v-if="
                    subnet.display == 'summary' &&
                    group.chart != undefined &&
                    group.chart.datasets != undefined &&
                    group.chart.datasets &&
                    group.chart.datasets[0].data != undefined &&
                    group.chart.datasets[0].data.length == 3
                  "
                >
                  <b-table
                    :fields="[
                      {
                        key: 'OK',
                        thStyle: { width: '33%' },
                      },
                      {
                        key: 'Warning',
                        thStyle: { width: '33%' },
                      },
                      ,
                      'Critical',
                    ]"
                    bordered
                    striped
                    :items="[group.chart.datasets[0].data]"
                  >
                    <template v-slot:cell(OK)="row">
                      {{ row.item[0] }}
                    </template>
                    <template v-slot:cell(Warning)="row">
                      {{ row.item[1] }}
                    </template>
                    <template v-slot:cell(Critical)="row">
                      {{ row.item[2] }}
                    </template>
                  </b-table>
                </div>

                <div class="flexed" v-if="subnet.display != 'summary'">
                  <Host
                    v-for="(host, k) in group.hosts.filter(
                      (x) => x.display != false
                    )"
                    v-bind:key="k"
                    :ip="host.ip"
                    passed_class="main"
                    :icon="host.icon"
                    :services="host.services"
                    @hostClicked="() => (selected_host = host)"
                    :cpu="host.cpu_check"
                    :mem="host.mem_check"
                    :hd="host.hd_check"
                    :monitor="host.monitor"
                    :monitored_only="subnet.monitored"
                    @dragStart="(ip) => (dragged_ip = ip)"
                    @dragEnd="dragged_ip = ''"
                    @service="
                      (val) => {
                        selected_metric = val;
                        selected_metric['ip'] = host.ip;
                        $forceUpdate();
                      }
                    "
                    :host="host.host"
                    :display="host.display"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <b-spinner v-else class="m-2" />
  </div>
</template>
<script>
import Helper from "@/helper";
import Connector from "@/components/Connector";
import Host from "@/components/Host";
import CreateEditSubnet from "@/components/CreateEditSubnet";
import CreateEditHost from "@/components/CreateEditHost";
import HostMetric from "@/components/HostMetric";
import GroupModal from "@/components/GroupModal.vue";
import DoughnutChart from "@/components/charts/DoughnutChart";

export default {
  data() {
    return {
      loading: false,
      smartbar: "",

      offsetTop: [],
      full_data: [],

      selected_subnet: "",
      selected_host: "",
      selected_metric: {},

      dragged_ip: "",
      selected_group: "",

      originLinks: [],

      themes: [],

      chartOptions: {
        responsive: true,
        maintainAspectRatio: true,
        legend: {
          display: false,
        },
        tooltips: { enabled: false },
        hover: { mode: null },
      },

      timeout: null,
    };
  },
  components: {
    Connector,
    Host,
    CreateEditSubnet,
    CreateEditHost,
    HostMetric,
    GroupModal,
    DoughnutChart,
  },
  computed: {
    parsed_data: function () {
      let data = this.full_data;
      if (this.smartbar == "") {
        return this.sortSubnets(data);
      }

      let search = {
        service: "",
        host: null,
        tag: [],
        field: [],
        port: null,
        group: null,
        ip: null,

        invert: false,
      };

      let searches = [];

      let search_parts = this.smartbar.split(" ").map((x) => x.toLowerCase());

      search_parts.forEach((part) => {
        let temp = JSON.parse(JSON.stringify(search));

        let splits = part.split("=");
        if (splits.length == 2) {
          let left = splits[0];
          let right = splits[1];

          if (left.indexOf("tag:") != -1) {
            let tag_name = left.replace("tag:", "");
            temp.tag.push({ tag: tag_name, value: right });
          } else if (left.indexOf("field:") != -1) {
            let field_name = left.replace("field:", "");
            temp.field.push({ field: field_name, value: right });
          } else {
            switch (left) {
              case "service":
                temp.service = right;
                break;
              case "host":
                temp.host = right;
                break;
              case "port":
                temp.port = right;
                break;
              case "group":
                temp.group = right;
                break;
              case "ip":
                temp.ip = right;
                break;
              default:
                break;
            }
          }

          searches.push(temp);
        }
      });

      data.forEach((subnet) => {
        if (subnet.groups) {
          subnet.groups.forEach((group) => {
            if (group.hosts) {
              group.hosts.forEach((host) => {
                if (this.checkHostFilter(host, searches)) {
                  host.display = true;
                } else {
                  host.display = false;
                }
              });
            }
          });
        }
      });
      return data;
    },

    all_ips_computed: function () {
      let retval = new Set();
      this.full_data.forEach((subnet) => {
        if (subnet.groups) {
          subnet.groups.forEach((group) => {
            if (group.hosts) {
              group.hosts.forEach((host) => {
                if (host.ip) {
                  retval.add(host.ip);
                }
              });
            }
          });
        }
      });
      return retval;
    },
  },
  methods: {
    capitalize: Helper.capitalize,
    convertSubnet(subnet) {
      try {
        let splits = subnet.split(".");
        if (splits.length != 3) {
          return -1;
        }
        let output = splits[0] * 100000 + splits[1] * 1000 + splits[2] * 10;
        return output;
      } catch (e) {
        return -1;
      }
    },
    sortSubnets(all_items) {
      // Returns 1 (a after b), 0 (a==b), -1 (b after a)
      let temp = JSON.parse(JSON.stringify(all_items));
      return temp.sort((a, b) => {
        if (a.subnet == undefined || b.subnet == undefined) {
          return 0;
        }

        if (this.convertSubnet(a.subnet) == this.convertSubnet(b.subnet)) {
          return 0;
        }
        let outcome =
          this.convertSubnet(a.subnet) < this.convertSubnet(b.subnet) ? -1 : 1;
        return outcome;
      });
    },
    checkHostFilter(host, searches) {
      let retval = false;
      searches.forEach((search) => {
        // Services Search
        if (
          host.services
            .map((x) => (x ? x.name.toLowerCase() : ""))
            .indexOf(search.service.toLowerCase()) != -1
        ) {
          retval = true;
        }
        // Open Ports Search
        if (host.open_ports != undefined && host.open_ports.map(x=>parseInt(x)).indexOf(parseInt(search.port)) != -1) {
          retval = true;
        }

        // Tags Search
        try{
          search.tag.forEach(tag=>{
            host.services.map(x=>x.latest_metric).forEach(field=>{
              if (field != undefined && field["tags"] != undefined && [tag["tag"]] != undefined && String(field.tags[tag["tag"]]) == String(tag["value"])){
                retval = true
              }
            })
          })
        }catch(e){
          console.log("Tags parse failed")
          console.log(e)
        }

        // Fields Search
        try{
          search.field.forEach(search_field=>{
            host.services.map(x=>x.latest_metric).forEach(field=>{
              if (field["fields"] != undefined && [search_field["fields"]] != undefined && String(field.fields[search_field["field"]]) == String(search_field["value"])){
                retval = true
              }
            })
          })
        }catch(e){
          console.log("Fields parse failed")
          console.log(e)
        }

        // Other search
        const names = ["ip", "group", "host"]
        names.forEach(found_name => {
          if(host[found_name] && search[found_name] && host[found_name].toLowerCase() == search[found_name].toLowerCase()){
            retval = true
          }
        })
        
      });
      return retval;
    },
    filterMonitored: function (group, subnet) {
      if (!subnet) {
        return group;
      }

      let temp = JSON.parse(JSON.stringify(group));

      return temp.filter((x) => {
        if (x.hosts == undefined) {
          return false;
        }
        if (x.hosts.filter((y) => y.monitor).length) {
          return true;
        }
      });
    },

    parseCommandLine: function () {
      // Parses the command line
    },

    loadThemes: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      Helper.apiCall("themes", "", auth)
        .then((res) => {
          this.themes = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    onDrop: /* istanbul ignore next */ function (name) {
      let auth = this.$auth;
      let url = this.dragged_ip;
      if (name != "") {
        url += "/" + name + "/";
      }
      Helper.apiCall("host_group_rename", url, auth)
        .then(() => {
          this.loadData();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    processGroupChart: function (group) {
      // Generates the datastructure for the doughnut chart for the group
      let output = {};
      output.labels = ["OK", "Warning", "Critical"];

      let total_green = 0;
      let total_orange = 0;
      let total_red = 0;
      // Process the group
      group.hosts.forEach((host) => {
        if (host.services != undefined) {
          host.services.forEach((service) => {
            if (service.state != undefined) {
              switch (service.state) {
                case -1:
                  total_orange += 1;
                  break;
                case true:
                  total_green += 1;
                  break;
                case false:
                  total_red += 1;
                  break;
              }
            }
          });
        }
      });
      output.datasets = [
        {
          backgroundColor: ["#49d184", "#f5b65f", "#db7077"],
          data: [total_green, total_orange, total_red],
        },
      ];
      return output;
    },
    loadData: /* istanbul ignore next */ async function (showLoading) {
      let auth = this.$auth;
      let url = "";
      if (showLoading) {
        this.loading = true;
        url = "1";
      }
      await Helper.apiCall("dashboard", url, auth)
        .then((res) => {
          this.full_data = res.sort((a, b) => {
            if (a.subnet > b.subnet) {
              return 1;
            }
            if (a.subnet == b.subnet) {
              return 0;
            }
            return -1;
          });

          this.originLinks = this.prepareOriginsLinks(this.full_data);

          for (let i = 0; i < this.full_data.length; i++) {
            let temp = this.full_data[i];
            if (temp.groups != undefined) {
              // Sort the groups
              temp.groups.sort((prev, next) => {
                if (prev.name == "") {
                  return 1;
                }
                if (next.name == "") {
                  return -1;
                }
                return prev.name > next.name;
              });

              // Build the necessary chart data
              temp.groups.forEach((group) => {
                group.chart = this.processGroupChart(group);
              });
              this.$forceUpdate();
            }
          }
          this.timeout = setTimeout(() => {
            this.loadData(false);
          }, 2000);
          this.loading = false;
        })
        .catch((e) => {
          clearTimeout(this.timeout);
          this.timeout = setTimeout(() => {
            this.loadData(false);
          }, 2000);
          this.$store.commit("updateError", e);
        });
    },
    findClass: function (subnet, isTitle) {
      let retval = "";

      // Color
      if (subnet.color != undefined && this.themes != []) {
        let found_theme = this.themes.find((x) => x.name == subnet.color);
        if (!found_theme) {
          return "";
        }
        try {
          retval = "background-color: " + found_theme.background.hex + ";";
          if (!isTitle) {
            retval += "border: 1px solid " + found_theme.border.hex + ";";
          } else {
            retval += "color: " + found_theme.text.hex + ";";
          }
        } catch (e) {
          return "";
        }
      }

      return retval;
    },

    prepareOriginsLinks: function (subnets) {
      let retval = [];
      const width = 7;
      subnets = subnets.filter(
        (x) =>
          x.links != undefined &&
          x.origin != undefined &&
          x.origin.ip != undefined &&
          x.origin.ip != "" &&
          x.links.ip != undefined &&
          x.links.ip != ""
      );

      subnets.forEach((x, idx) => {
        let found = this.themes.find(
          (y) => x.links.color != undefined && y.name == x.links.color
        );
        if (!found) {
          found = "white";
        } else {
          if (
            found.connection != undefined &&
            found.connection.hex != undefined
          ) {
            found = found.connection.hex;
          } else {
            found = "white";
          }
        }
        retval.push({
          color: found,
          top_1: x.origin.ip,
          top_2: x.links.ip,
          left: idx * width,
        });
      });
      return retval;
    },
  },

  created: function () {
    //window.addEventListener("resize", this.findTop);
  },
  mounted: async function () {
    try {
      this.loadThemes();
      await this.loadData(1);
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  destroyed: function () {
    clearTimeout(this.timeout);
  },
};
</script>
<style lang="scss" scoped>
@import "@/assets/variables.scss";

body,
html {
  padding: 0;
  margin: 0;
  background-color: #fffeff;
}

.hover {
  cursor: pointer;
}

.hover:hover {
  color: darkgrey;
}

.dashboard {
  margin-bottom: 20px;
}
.add-button {
  position: absolute;
  top: 70px;
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
.group_headers {
  width: auto !important;
  text-transform: capitalize;
  cursor: pointer;
}
.group_headers:hover {
  color: #cdcdce;
}
.light {
  text-align: left;
  color: #bdbdbf;
  padding-bottom: 5px;
  border-bottom: 1px solid #bdbdbf;
  margin-bottom: 15px;
}
h2.subnet {
  font-family: system-ui, "sans-serif";
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
  width: 5%;
  min-width: 75px;
  float: left;
}

.outer {
  background-color: #efefed;
  min-height: 150px;
  margin: auto;
  margin-left: 100px;
  margin-right: 1%;
  margin-top: 20px;
  border-radius: 1.25rem;
  clear: both;
}

.smartbar {
  min-height: 50px !important;
  background-color: unset !important;
}

.left {
  width: 5%;
  min-width: 160px;
  float: left;
}
.right {
  overflow: hidden;
  padding-top: 10px;
  margin: 20px;
  margin-top: 0;
}
.corner {
  position: relative;
  top: -1px;
  left: -1px;
  border-radius: 0 0 3rem 0;
  min-width: 75px;
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
  /* width: 30%; */
  /* width: 400px !important; */
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

.chart {
  height: 100px;
  width: 100px;
  text-align: center;
  margin: auto;
}

/* Minimized */
.minimized {
  min-height: 75px;
  margin-bottom: 0.25rem;
  margin-top: 0.25rem !important;
}
.minimized .corner {
  height: 70px;
  border-radius: 0.5rem;
  color: transparent;
  width: 100px;
}
.minimized .corner img {
  height: 30px !important;
}

/* Mobile */
.mobile {
  display: none !important;
}
@media screen and (max-width: 991px) {
  .corner {
    width: 50%;
    border-radius: 0.5rem;
    margin: auto;
    margin-top: 0.5rem;
  }
  .left {
    width: 100%;
  }
  .right {
    width: 100%;
    margin-left: 0 !important;
  }
  .connector {
    display: none;
  }
  .outer {
    margin: auto !important;
    width: 99%;
    overflow: hidden;
    margin-bottom: 0.5rem !important;
  }
  .right h2 {
    text-align: center !important;
  }
  .mobile {
    display: block !important;
  }
  .main {
    width: 100%;
    max-width: 100%;
    min-width: 100%;
  }
  .grouped {
    width: 100% !important;
  }
}
</style>
