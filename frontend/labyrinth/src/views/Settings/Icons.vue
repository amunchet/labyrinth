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
      TODO: Coming Soon
    </b-col>
  </b-row>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "SettingsIcons",
  data() {
    return {
      icons: [],
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
