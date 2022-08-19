<template>
  <div>
    <h4>Custom Dashboard Views</h4>
    <hr />
    {{ selected_dashboard }}
    <hr />
    {{full_data}}
    <hr />
    <b-row>
      <b-col cols="2">
        <b-select :options="custom_dashboards" v-model="selected_dashboard" />
      </b-col>
    </b-row>
    <hr />

    <div class="main" :style="'background-image: url(' + generateBackgroundImage() + ');'">
      <img :src="generateBackgroundImage()" style="visibility:hidden" />
    </div>

  </div>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "CustomDashboardViews",
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
      this.loadData()
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  methods: {
    generateBackgroundImage: function(){
      var url = '/api/custom_dashboard_images/' + this.$auth.accessToken + "/" + this.selected_dashboard.background_image 

      return url;
    },
    loadCustomDashboards: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("custom_dashboards", "", auth)
        .then((res) => {
          this.custom_dashboards = res.map((x) => {
            return {
              text: x.name,
              value: x,
            };
          });
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
          this.full_data = res.sort((a, b) => {
            if (a.subnet > b.subnet) {
              return 1;
            }
            if (a.subnet == b.subnet) {
              return 0;
            }
            return -1;
          });


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
.main{
  background-repeat: no-repeat;
}
</style>