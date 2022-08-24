<template>
  <b-row>
    <b-col>
      <h3>Icons</h3>
      <div class="flex">
        <div v-for="(item, idx) in icons" v-bind:key="idx" class="box">
          <div class="overflow-hidden">
            <font-awesome-icon
              icon="times"
              size="1x"
              class="cursor float-right"
              @click="deleteIcon()"
            />
          </div>
          <img :src="'/icons/' + item + '.svg'" :alt="item + ' icon'" />
          <div class="box_text">
            {{ item }}
          </div>
        </div>
        <div class="box pt-4 bg-success cursor text-white">
          <div class="mt-4 cursor">+ Upload New Icon (TODO)</div>
        </div>
      </div>
    </b-col>
    <b-col>
      <h3>Colors/Themes</h3>
      <b-row class="text-left">
        <b-col>Color Theme Name: </b-col><b-col><b-select /></b-col>
      </b-row>
      <b-row>
        <b-col></b-col>
        <b-col class="text-right mt-2">
          <b-button variant="primary">+Add New Theme</b-button>
        </b-col>
      </b-row>
      <hr />
      <b-row class="text-left mb-2">
        <b-col>Background Color</b-col>
        <b-col><b-input /></b-col>
      </b-row>
      <b-row class="text-left mb-2">
        <b-col>Border Color</b-col>
        <b-col
          ><b-input v-model="color.hex" />
          <color-picker v-model="color" />
        </b-col>
      </b-row>
      <b-row class="text-left mb-2">
        <b-col>Connection Color</b-col>
        <b-col><b-input /></b-col>
      </b-row>
      <hr />
      <b-row class="text-left">
        <b-col>Preview: <br /> </b-col>
      </b-row>
      <hr />
      <b-row>
        <b-col class="text-left">
          <b-button class="text-danger" variant="link">
            <font-awesome-icon icon="times" size="1x" />&nbsp;Delete
            Theme</b-button
          >
        </b-col>
        <b-col class="text-right">
          <b-button variant="success">
            <font-awesome-icon icon="save" size="1x" />&nbsp; Save
            Theme</b-button
          >
        </b-col>
      </b-row>
    </b-col>
  </b-row>
</template>
<script>
import Helper from "@/helper";
import { Chrome } from "vue-color";
export default {
  name: "SettingsIcons",
  components: {
    "color-picker": Chrome,
  },
  data() {
    return {
      icons: [],
      color: "#ababad",
      default_backend: "",
    };
  },

  methods: {
    loadIcons: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("icons", "", auth)
        .then((res) => {
          this.icons = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    deleteIcon: /* istanbul ignore next */ function () {
      alert("TODO: Delete icon");
    },
  },
  mounted: function () {
    try {
      this.loadIcons();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
.sub {
  border-right: 1px solid lightgrey;
  min-height: 400px;
  text-align: center;
  padding-top: 1rem;
}
.flex {
  display: flex;
  flex-wrap: wrap;
}
.box {
  border: 1px solid lightgrey;
  width: 25%;
  margin: 1rem;
  padding: 1rem;
  text-align: center;
  border-radius: 0.5rem;
}
.box_text {
  margin-top: 0.5rem;
}
.cursor {
  cursor: pointer;
}
</style>
