<template>
  <b-modal id="group_edit" :title="'Group Options for ' + selected_group">
    <template #modal-footer="{ ok }">
      <div>
        <b-button @click="ok()">Cancel</b-button>
      </div>
    </template>
    <div class="mr-3">
      <b-row>
        <b-col cols="5"> Monitor All </b-col>
        <b-col cols="6">
          <b-form-checkbox
            size="lg"
            name="check-button"
            switch
            v-model="status"
          >
          </b-form-checkbox>
        </b-col>
      </b-row>
      <b-row>
        <b-col cols="5"> Rename Group</b-col>
        <b-col cols="6">
          <b-input size="sm" v-model="new_name" />
        </b-col>
        <b-col cols="1">
          <b-button variant="success" size="sm" @click="changeGroupName()">
            <font-awesome-icon icon="check" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row>
        <b-col cols="5"> Change Icons </b-col>
        <b-col cols="6">
          <b-select size="sm" :options="icons" v-model="selected_icon" />
        </b-col>
        <b-col cols="1">
          <b-button size="sm" variant="warning" @click="changeIcons()">
            <font-awesome-icon icon="save" />
          </b-button>
        </b-col>
      </b-row>
      <b-row>
        <b-col cols="5"> Add Service to All</b-col>
        <b-col cols="6">
          <b-select size="sm" :options="services" v-model="selected_service" />
        </b-col>
        <b-col cols="1">
          <b-button size="sm" variant="primary" @click="addService()">
            <font-awesome-icon icon="plus" />
          </b-button>
        </b-col>
      </b-row>

      <b-row>
        <b-col cols="5"> Delete a Service from All</b-col>
        <b-col cols="6">
          <b-select size="sm" :options="services" v-model="selected_delete_service" />
        </b-col>
        <b-col cols="1">
          <b-button size="sm" variant="danger" @click="deleteService()">
            <font-awesome-icon icon="times" />
          </b-button>
        </b-col>
      </b-row>

    </div>
  </b-modal>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "GroupModal",
  props: ["selected_group", "selected_subnet"],
  data() {
    return {
      status: false,
      new_name: "",

      icons: [],
      selected_icon: "",

      services: [],
      selected_service: "",
      selected_delete_service: "",
    };
  },
  watch: {
    status: function (val) {
      this.changeMonitor(val);
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.listIcons();
      this.listServices()
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  methods: {
    changeMonitor: function (status) {
      var auth = this.$auth;
      var url =
        "monitor/" +
        this.selected_subnet.subnet +
        "/" +
        this.selected_group +
        "/" +
        status;

      Helper.apiCall("group", url, auth)
        .then((res) => {
          this.$emit("updated");
          this.$store.commit("updateError", "Monitor update: " + res);
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    changeGroupName: function () {
      var auth = this.$auth;
      var url =
        "name/" +
        this.selected_subnet.subnet +
        "/" +
        this.selected_group +
        "/" +
        this.new_name;
      Helper.apiCall("group", url, auth)
        .then(() => {
          this.$emit("updated");
          this.$bvModal.hide("group_edit");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    changeIcons: function () {
      var auth = this.$auth;
      var url =
        "icons/" +
        this.selected_subnet.subnet +
        "/" +
        this.selected_group +
        "/" +
        this.selected_icon;
      Helper.apiCall("group", url, auth)
        .then((res) => {
          this.$emit("updated");
          this.$store.commit("updateError", res);
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    addService: function () {
      var auth = this.$auth
      var url = "add_service/" + this.selected_subnet.subnet + "/" + this.selected_group + "/" + this.selected_service
      Helper.apiCall("group", url, auth).then(res=>{
        this.$emit("updated")
        this.$store.commit("updateError", res)
      }).catch(e=>{
        this.$store.commit("updateError", e)
      })
    },
    deleteService: function () {
      var auth = this.$auth
      var url = "delete_service/" + this.selected_subnet.subnet + "/" + this.selected_group + "/" + this.selected_delete_service
      Helper.apiCall("group", url, auth).then(res=>{
        this.$emit("updated")
        this.$store.commit("updateError", res)
      }).catch(e=>{
        this.$store.commit("updateError", e)
      })
    },

    listIcons: function () {
      var auth = this.$auth;
      Helper.apiCall("icons", "", auth)
        .then((res) => {
          this.icons = res.map((x) => {
            return {
              text: x,
              value: x,
            };
          });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    listServices: function () {
      var auth = this.$auth;
      Helper.apiCall("services", "all", auth)
        .then((res) => {
          this.services = res.map((x) => {
            return {
              text: x.name,
              value: x.name,
            };
          });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
};
</script>
<style lang="scss" scoped>
.row {
  margin: 1rem 0 1rem 0;
}
.col-5 {
  user-select: none;
}
</style>