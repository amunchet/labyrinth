<template>
  <div class="text-left ml-4">
    <b-row>
      <b-col class="sub">
        <h3>Icons</h3>
        <div class="flex">
          <div v-for="(item, idx) in icons" v-bind:key="idx" class="box">
            <div class="overflow-hidden">
              <font-awesome-icon icon="times" size="1x" class="cursor float-right" 
              @click="deleteIcon()"
              />
            </div>
            <img :src="'/icons/' + item + '.svg'" :alt="item + ' icon'" />
            <div class="box_text">
              {{ item }}
            </div>
          </div>
          <div class="box pt-4 bg-success cursor text-white">
          <div class="mt-4 cursor" >
            + Upload New Icon (TODO)
            </div>
            </div>
        </div>
        <hr />

        <h3>Colors/Themes</h3>
        TODO: Coming Soon
      </b-col>

      <b-col class="sub">
        <h3>Telegraf</h3>
        <b-container class="mt-3">
          <b-row>
            <b-col>Default Template file: </b-col>
            <b-col><b-select /></b-col>
            <b-col cols="2">
              <b-button variant="primary">
                <font-awesome-icon icon="sync-alt" size="1x" />
              </b-button>
            </b-col>
          </b-row>
        </b-container>
      </b-col>
    </b-row>
  </div>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Settings",
  data() {
    return {
      icons: [],
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
    deleteIcon: /* istanbul ignore next */ function (){
      alert("TODO: Delete icon")
    },
  },
  mounted: function () {
    this.loadIcons();
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