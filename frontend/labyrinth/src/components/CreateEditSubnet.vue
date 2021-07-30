<template>
  <b-modal id="create_edit_subnet" title="Create/Edit Subnet">
    <b-row>
      <b-col>Subnet</b-col>
      <b-col>
        <b v-if="!isNew">{{ subnet.subnet }}</b>
        <b-input v-else v-model="subnet.subnet" />
      </b-col>
    </b-row>
    <b-row>
      <b-col>Color</b-col>
      <b-col><b-select :options="colors" v-model="subnet.color" /></b-col>
    </b-row>
    <hr />
    <h6>Network Link</h6>
    <i
      >This is for additional subnets that are routed through a router on this
      subnet</i
    >
    <b-row>
      <b-col> Link IP </b-col>
      <b-col v-if="subnet.links">
        <b-input v-model="subnet.links.ip" />
      </b-col>
    </b-row>
    <b-row>
      <b-col> Link Icon </b-col>
      <b-col v-if="subnet.links">
        <b-select :options="icons" v-model="subnet.links.icon" />
      </b-col> </b-row
    ><b-row>
      <b-col> Ref </b-col>
      <b-col v-if="subnet.links">
        <b-input v-model="subnet.links.ref" />
      </b-col>
    </b-row>
    <b-row>
      <b-col>Color</b-col>
      <b-col v-if="subnet.links"
        ><b-select :options="colors" v-model="subnet.links.color"
      /></b-col>
    </b-row>
    <hr />
    <h6>Origin</h6>
    <i
      >This is the router that allows entry into this subnet. It may be the
      local machine itself (127.0.0.1)</i
    >

    <b-row>
      <b-col> Origin IP </b-col>
      <b-col v-if="subnet.origin">
        <b-input v-model="subnet.origin.ip" />
      </b-col>
    </b-row>
    <b-row>
      <b-col>Origin Icon</b-col>
      <b-col v-if="subnet.origin">
        <b-select :options="icons" v-model="subnet.origin.icon" />
      </b-col>
    </b-row>

    <template #modal-footer="{ cancel }">
      <div style="width: 100%">
        <b-button class="float-left" variant="danger" @click="deleteSubnet()"
          >Delete</b-button
        >
        <b-button
          class="float-right ml-2"
          variant="primary"
          @click="saveSubnet()"
          >OK</b-button
        >
        <b-button class="float-right" @click="cancel()">Cancel</b-button>
      </div>
    </template>
  </b-modal>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "CreateEditSubnet",
  props: ["inp_subnet"],
  data() {
    return {
      subnet: {
        subnet: "",
        origin: {
          ip: "",
          icon: "",
        },
        links: {
          ref: "",
          ip: "",
          icon: "",
          color: "",
        },
      },
      icons: [],
      colors: [],
      isNew: true,
    };
  },
  methods: {
    saveSubnet: /* istanbul ignore next */ function () {
      if (this.subnet.subnet == "") {
        this.$store.commit("updateError", "Error: Please enter subnet name");
        return -1;
      }
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.subnet));
      Helper.apiPost("subnet", "", "", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.$emit("update");
          this.$bvModal.hide("create_edit_subnet");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    deleteSubnet: /* istnabul ignore next */ function () {
      var auth = this.$auth;
      this.$bvModal
        .msgBoxConfirm("Are you sure you want to delete this subnet?")
        .then((res) => {
          if (!res) {
            return;
          }
          Helper.apiDelete("subnet", this.subnet.subnet, auth)
            .then((res) => {
              this.$store.commit("updateError", res);

              this.$emit("update");
              this.$bvModal.hide("create_edit_subnet");
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        });
    },
  },
  watch: {
    inp_subnet: function (val) {
      if (val != "") {
        this.subnet = JSON.parse(JSON.stringify(this.inp_subnet));
        delete this.subnet["hosts"];
        delete this.subnet["groups"];
        this.isNew = false;
      } else {
        this.isNew = true;
        this.subnet = {
          subnet: "",
          origin: {
            ip: "",
            icon: "",
          },
          links: {
            ref: "",
            ip: "",
            icon: "",
            color: "",
          },
        };
      }
    },
  },
  mounted: function () {
    try {
      this.icons = Helper.listIcons();
      this.colors = Helper.listColors();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
.row {
  margin-top: 1rem;
  margin-bottom: 1rem;
}
</style>
