<template>
  <b-modal id="create_edit_subnet" title="Create/Edit Subnet">
    <b-row>
      <b-col>Subnet</b-col>
      <b-col>
        <b v-if="!isNew">{{ subnet.subnet }}</b>
        <b-input
          v-else
          v-model="subnet.subnet"
          placeholder="E.g. 192.168.0"
          :state="!$v.subnet.subnet.$invalid"
        />
      </b-col>
    </b-row>
    <b-row>
      <b-col>Theme</b-col>
      <b-col
        ><b-select
          :options="[
            { text: 'None', value: '' },
            ...themes.map((x) => {
              return { text: x.name, value: x.name };
            }),
          ]"
          v-model="subnet.color"
      /></b-col>
    </b-row>
    <b-row>
      <b-col>Show Only Monitored?</b-col>
      <b-col>
        <b-form-checkbox
          size="lg"
          name="show-monitored"
          switch
          v-model="subnet.monitored"
        />
      </b-col>
    </b-row>
    <b-row>
      <b-col>Minimize Subnet?</b-col>
      <b-col>
        <b-form-checkbox
          size="lg"
          name="minimized"
          switch
          v-model="subnet.minimized"
        />
      </b-col>
    </b-row>
    <b-row>
      <b-col> Display Mode </b-col>
      <b-col>
        <b-select v-model="subnet.display">
          <option value="">All Hosts (default)</option>
          <option value="summary">Summary View</option>
        </b-select>
      </b-col>
    </b-row>
    <hr />

    <h6>Origin</h6>
    <i>
      These settings control the origin host, which sits at the top left of the
      subnet and can show visual connection to other subnets. Leave Origin IP
      blank to hide.
    </i>
    <hr />
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

    <hr />

    <h6>Network Link</h6>
    <i>
      This connects one subnets origin host to another. This is purely cosmetic.
      Leave Link IP blank to disable.
    </i>
    <hr />
    <b-row>
      <b-col> Link IP </b-col>
      <b-col v-if="subnet.links">
        <b-input v-model="subnet.links.ip" />
      </b-col>
    </b-row>
    <b-row>
      <b-col>Theme</b-col>
      <b-col v-if="subnet.links"
        ><b-select
          :options="themes.map((x) => x.name)"
          v-model="subnet.links.color"
      /></b-col>
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
import { required } from "vuelidate/lib/validators";
export default {
  name: "CreateEditSubnet",
  props: ["inp_subnet"],
  data() {
    return {
      themes: [],
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
      isNew: true,
    };
  },
  validations: {
    subnet: {
      subnet: {
        required,
        ipValidation: (val) => Helper.validateIP(val, 3),
      },
    },
  },
  methods: {
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

    listIcons: /* istanbul ignore next */ function () {
     let auth = this.$auth;
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
    saveSubnet: /* istanbul ignore next */ function () {
      if (this.subnet.subnet == "" || this.$v.subnet.$invalid) {
        this.$store.commit(
          "updateError",
          "Error: Please enter a correct subnet name"
        );
        return -1;
      }
     let auth = this.$auth;
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
    deleteSubnet: /* istanbul ignore next */ function () {
     let auth = this.$auth;
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
      this.listIcons();
      this.loadThemes();
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
