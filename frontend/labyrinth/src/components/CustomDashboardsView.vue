<template>
  <b-container class="text-center">
    <b-row>
      <b-col cols="2">
        <b-select :options="custom_dashboards" v-model="selected_dashboard" />
      </b-col>
    </b-row>
    <hr />

    <b-container>
      <div
        class="outer"
        :style="'background-image: url(' + generateBackgroundImage() + ');'"
      >
        <img :src="generateBackgroundImage()" style="visibility: hidden" />
        <div
          v-for="(host, k) in computed_filtered_data"
          v-bind:key="k"
          :style="generateHostStyle(host)"
        >
          <Host
            :ip="host.ip"
            passed_class="main"
            :icon="host.icon"
            :services="host.services"
            @hostClicked="() => (selected_host = host)"
            :cpu="host.cpu_check"
            :mem="host.mem_check"
            :hd="host.hd_check"
            :monitor="host.monitor"
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
    </b-container>
  </b-container>
</template>
<script>
import Helper from "@/helper";
import Host from "@/components/Host";

export default {
  name: "CustomDashboardViews",
  components: {
    Host,
  },
  data() {
    return {
      custom_dashboards: [],
      selected_dashboard: "",

      full_data: {},
    };
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadCustomDashboards();
      this.loadData();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  computed: {
    computed_filtered_data: function () {
      try {
        if (this.selected_dashboard && this.selected_dashboard.components) {
          let temp =  {};
          this.selected_dashboard.components.forEach((x) => {
            temp[x.subnet + x.name] = 1;
          });

          return this.full_data.filter(
            (x) => temp[x.subnet + x.ip] != undefined
          );
        }
      } catch (e) {
        return [];
      }
      return [];
    },
  },
  methods: {
    generateHostStyle: function (host) {
      // Generates the offsets from the given host data
      let offsets =  this.selected_dashboard.components.filter(
        (x) => x.name == host.ip && x.subnet == host.subnet
      );
      if (offsets.length > 0) {
        return (
          "position:relative; height:0; left:" +
          offsets[0].x +
          "px; top:" +
          offsets[0].y +
          "px; transform: scale(" +
          offsets[0].scaleX +
          ", " +
          offsets[0].scaleY +
          ") rotate(" +
          offsets[0].rotation +
          "deg); float: left;"
        );
      }
      return "";
    },
    generateBackgroundImage: function () {
      let url = 
        "/api/custom_dashboard_images/" +
        this.$auth.accessToken +
        "/" +
        this.selected_dashboard.background_image;

      return url;
    },
    loadCustomDashboards: /* istanbul ignore next */ function () {
     let auth = this.$auth;
      Helper.apiCall("custom_dashboards", "", auth)
        .then((res) => {
          this.custom_dashboards = res.map((x) => {
            return {
              text: x.name,
              value: x,
            };
          });

          res.forEach((x) => {
            if (x.default) {
              this.selected_dashboard = x;
              this.$forceUpdate();
            }
          });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadData: /* istanbul ignore next */ async function (showLoading) {
     let auth = this.$auth;
      let url =  "";
      if (showLoading) {
        this.loading = true;
        url = "1";
      }
      await Helper.apiCall("dashboard", url, auth)
        .then((res) => {
          let temp =  [];
          res.forEach((subnet) => {
            if (subnet.groups != undefined) {
              subnet.groups.forEach((subnet) => {
                if (subnet.hosts != undefined) {
                  subnet.hosts.forEach((host) => {
                    temp.push(host);
                  });
                }
              });
            }
          });
          this.full_data = temp;

          setTimeout(() => {
            this.loadData(false);
          }, 2000);
          this.loading = false;
        })
        .catch((e) => {
          setTimeout(() => {
            this.loadData(false);
          }, 2000);
          this.$store.commit("updateError", e);
        });
    },
  },
};
</script>
<style lang="scss" scoped>
.outer {
  background-repeat: no-repeat;
  margin: auto;
}
.main {
  background-color: white;
}
</style>
