<template>
  <div class="dashboard">
    <!-- Modals -->
    <CreateEditSubnet :inp_subnet="selected_subnet" @update="loadData()" />

    <CreateEditHost :inp_host="selected_host" @update="loadData()" />
    <HostMetric @update="loadData()" :data="selected_metric" />

    <GroupModal
      :selected_group="selected_group"
      :selected_subnet="selected_subnet"
      @updated="loadData()"
    />
    <!-- Main page -->

    {{
      full_data.map((x) => {
        return {
          subnet: x.subnet,
          orign: x.origin,
          link: x.links,
        };
      })
    }}
    <hr />
    {{ Object.keys($refs) }}
    <hr />
    {{ connectorBottom }}

    <hr />
    Connector count: {{ connector_count }}

    <div v-if="!loading">
      <div class="outer_left">
        <!-- set verticals to some number to see the connector -->
        <!-- old: 
          :verticals="connectorBottom[0]"
        -->
        
        <Connector
          v-if="$refs.start_1 != undefined && $refs.start_2 != undefined"
          color="green"
          horizontal_width="100"
          :top_1="$refs.start_0[0].offsetTop"
          :top_2="$refs.start_1[0].offsetTop"
          left="20"
          :key="$refs.start_0[0].offsetTop && $refs.start_1[0].offsetTop"

        />
        <Connector
          v-if="$refs.start_1 != undefined && $refs.start_2 != undefined"
          color="orange"
          horizontal_width="100"
          :top_1="$refs.start_0[0].offsetTop"
          :top_2="$refs.start_2[0].offsetTop"
          left="40"
          :key="$refs.start_0[0].offsetTop && $refs.start_2[0].offsetTop"

        />
        <!--
        <Connector
          horizontal_width="100px"  # This is how long the horizontal component is
          left  = "20px"      # Left offset (for more than 1 connector)
          top_1 = "200px"     # One of the top points
          top_2 = "150px"     # The other top point - can be greater or less
          color = "orange"    # Whatever the color is 

        />
        -->
      </div>
      <div class="outer_right">
        <b-button
          variant="link"
          class="add-button"
          @click="
            () => {
              selected_subnet = '';
              $bvModal.show('create_edit_subnet');
            }
          "
        >
          <font-awesome-icon icon="plus" size="1x" /> New Subnet
        </b-button>
        <div
          :class="findClass(subnet)"
          v-for="(subnet, i) in full_data.sort((a, b) => {
            if (a.subnet > b.subnet) {
              return 1;
            }
            if (a.subnet == b.subnet) {
              return 0;
            }
            return -1;
          })"
          v-bind:key="i"
        >
          <div
            class="left"
            v-if="
              (subnet.origin.ip != undefined && subnet.origin.ip != '') ||
              (subnet.links.ip != undefined && subnet.links.ip != '')
            "
          >
            <div class="corner" :ref="'start_' + i">
              <Host
                :ip="subnet.origin.ip"
                :icon="subnet.origin.icon"
                show_ports="0"
              />
              <br />
              <img :src="'/icons/' + capitalize(subnet.origin.icon) +'.svg'" /><br />
              {{subnet.origin.ip}}
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
              :class="findTitleClass(subnet)"
            >
              {{ subnet.subnet }}
            </h2>
            <div class="flexed">
              <div
                class="grouped"
                v-for="(group, j) in subnet.groups"
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
                <div class="flexed">
                  <Host
                    v-for="(host, k) in group.hosts"
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
export default {
  data() {
    return {
      loading: false,

      offsetTop: [],
      connectorBottom: [],
      connector_count: 1,
      full_data: [],

      selected_subnet: "",
      selected_host: "",
      selected_metric: {},

      dragged_ip: "",
      selected_group: "",
    };
  },
  components: {
    Connector,
    Host,
    CreateEditSubnet,
    CreateEditHost,
    HostMetric,
    GroupModal,
  },
  methods: {
    capitalize: Helper.capitalize,
    onDrop: /* istanbul ignore next */ function (name) {
      var auth = this.$auth;
      Helper.apiCall(
        "host_group_rename",
        this.dragged_ip + "/" + name + "/",
        auth
      )
        .then(() => {
          this.loadData();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadData: /* istanbul ignore next */ async function (showLoading) {
      var auth = this.$auth;
      var url = "";
      if (showLoading) {
        this.loading = true;
        url = "1";
      }
      await Helper.apiCall("dashboard", url, auth)
        .then((res) => {
          this.full_data = res;

          for (var i = 0; i < this.full_data.length; i++) {
            var temp = this.full_data[i];
            if (temp.groups != undefined) {
              temp.groups.sort((prev, next) => {
                if (prev.name == "") {
                  return 1;
                }
                if (next.name == "") {
                  return -1;
                }

                if (prev.starred) {
                  return -1;
                }
                if (next.starred) {
                  return 1;
                }
                return prev.name > next.name;
              });
            }
          }
          setTimeout(() => {
            this.loadData(false);
          }, 2000);
          this.loading = false;
          this.findTop();
        })
        .catch((e) => {
          setTimeout(() => {
            this.loadData(false);
          }, 2000);
          this.$store.commit("updateError", e);
        });
    },
    findClass: function (subnet) {
      if (subnet.color == undefined) {
        return "outer";
      } else {
        return "outer " + subnet.color + "-bg";
      }
    },
    findTitleClass: function (subnet) {
      if (subnet.color == undefined) {
        return "text-right subnet";
      } else {
        return "text-right subnet " + subnet.color + "";
      }
    },
    // NOTE: I'm not sure how to test this function, since it relies on external DOM
    findTop: /* istanbul ignore next */ function () {
      try {
        for (var i = 0; i < this.connector_count; i++) {
          var height = this.$refs["start_" + i][0].offsetHeight;

          this.offsetTop[i] =
            this.$refs["start_" + i][0].offsetTop - 0.25 * height;
          var bottom = this.$refs["start_" + (i + 1)][0].offsetTop * 1;

          this.connectorBottom[i] =
            Math.ceil((bottom - this.offsetTop[i]) / 50) * 1;
        }
        this.$forceUpdate();
      } catch (e) {
        console.log(e);
        //setTimeout(this.findTop, 50);
      }
    },
  },
  watch: {
    $refs: {
      start_1: /* istanbul ignore next */ function (val) {
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
    try {
      this.loadData(1);
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss">
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

.flexed {
  display: flex;
  flex-wrap: wrap;
  justify-content: start;
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
  width: 5%;
  min-width: 140px;
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
  width: 30%;
  width: 400px !important;
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
