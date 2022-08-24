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
      <h3>Color Themes</h3>
      <b-row class="text-left">
        <b-col>Color Theme Name: </b-col>
        <b-col>
          <b-select
            :options="
              themes.map((x) => {
                return {
                  text: x.name,
                  value: x,
                };
              })
            "
            v-if="!new_theme"
            v-model="selected_theme"
          />
          <b-input v-else v-model="theme.name" />
        </b-col>
      </b-row>
      <b-row>
        <b-col></b-col>
        <b-col class="text-right mt-2">
          <b-button
            variant="primary"
            v-if="!new_theme"
            @click="() => (new_theme = true)"
            >+Add New Theme</b-button
          >
          <b-button
            v-else
            variant="link"
            @click="
              () => {
                new_theme = false;
                selected_theme = '';
                loadThemes();
              }
            "
            >Cancel</b-button
          >
        </b-col>
      </b-row>
      <hr />
      <div> 
      <b-row class="text-left mb-2">
        <b-col cols="4">Background Color</b-col>
        <b-col
          ><b-input v-if="theme && theme.background" v-model="theme.background.hex" />
          <color-picker
            v-if="theme && theme.show && theme.show.background"
            class="mt-2 mb-2"
            v-model="theme.background"
          />
        </b-col>

        <b-col cols="2">
          <b-button
            variant="warning"
            @click="theme.show.background = !theme.show.background"
          >
            <font-awesome-icon icon="palette" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row class="text-left mb-2">
        <b-col cols="4">Border Color</b-col>
        <b-col
          ><b-input v-if="theme && theme.border" v-model="theme.border.hex" />
          <color-picker
            v-if="theme && theme.show && theme.show.border"
            class="mt-2 mb-2"
            v-model="theme.border"
          />
        </b-col>
        <b-col cols="2">
          <b-button
            variant="warning"
            @click="theme.show.border = !theme.show.border"
          >
            <font-awesome-icon icon="palette" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row class="text-left mb-2">
        <b-col cols="4">Text Color</b-col>
        <b-col
          ><b-input v-if="theme && theme.text" v-model="theme.text.hex" />
          <color-picker
            v-if="theme && theme.show && theme.show.text"
            class="mt-2 mb-2"
            v-model="theme.text"
          />
        </b-col>

        <b-col cols="2">
          <b-button
            variant="warning"
            @click="theme.show.text = !theme.show.text"
          >
            <font-awesome-icon icon="palette" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row class="text-left mb-2">
        <b-col cols="4">Connection Color</b-col>
        <b-col
          ><b-input v-if="theme && theme.connection" v-model="theme.connection.hex" />
          <color-picker
            v-if="theme && theme.show && theme.show.connection"
            class="mt-2 mb-2"
            v-model="theme.connection"
          />
        </b-col>

        <b-col cols="2">
          <b-button
            variant="warning"
            @click="theme.show.connection = !theme.show.connection"
          >
            <font-awesome-icon icon="palette" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <hr />
      <b-row class="text-left">
        <b-col
          >Preview: <br />
          <div
            class="preview"
            v-if="theme && theme.background && theme.border"
            :style="
              'background-color: ' +
              theme.background.hex +
              '; border: 5px solid ' +
              theme.border.hex +
              ';'
            "
          >
            <div
              class="preview-connection"
              v-if="theme && theme.connection"
              :style="'background-color: ' + theme.connection.hex + ';'"
            ></div>
            <div 
            v-if="theme && theme.text"
            class='text-center'
            :style="'color: ' + theme.text.hex + ';'">Sample Text</div>
          </div>
        </b-col>
      </b-row>
      <hr />
      <b-row>
        <b-col class="text-left">
          <b-button
            class="text-danger ml-0 mr-0 pl-0 pr-0"
            @click="deleteTheme()"
            variant="link"
          >
            <font-awesome-icon class="mr-2" icon="times" size="1x" />Delete
            Theme</b-button
          >
        </b-col>
        <b-col class="text-right">
          <b-button variant="success" @click="saveTheme()">
            <font-awesome-icon icon="save" size="1x" />&nbsp; Save
            Theme</b-button
          >
        </b-col>
      </b-row>
      </div>
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
  props: ["time"],
  data() {
    return {
      icons: [],

      themes: [],
      selected_theme: "",

      color: "#ababad",
      default_backend: "",

      new_theme: false,
      theme: {
        name: "",
        show: {
          border: false,
          background: false,
          connection: false,
          text: false,
        },
        border: {
          hex: "",
        },
        background: {
          hex: "",
        },
        connection: {
          hex: "",
        },
        text: {
          hex: "",
        },
      },
    };
  },
  watch: {
    selected_theme: /* istanbul ignore next */ function (val) {
      if (val != ""){ 
        this.theme = val
      }
      this.$forceUpdate();
    },
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

    loadThemes: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("themes", "", auth)
        .then((res) => {
          this.themes = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    saveTheme: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      Object.keys(this.theme.show).forEach((x) => {
        this.theme.show[x] = false;
      });
      if(this.theme["_id"] != undefined){
        delete this.theme["_id"]
      }

      this.$forceUpdate();
      formData.append("data", JSON.stringify(this.theme));
      Helper.apiPost("themes", "", "", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res)
          this.new_theme = false
          this.loadThemes()
          this.$emit("reload")
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    deleteTheme: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      this.$bvModal
        .msgBoxConfirm("Are you sure you want to delete this host?")
        .then((res) => {
          if (!res) {
            return;
          }
          Helper.apiDelete("themes", this.selected_theme.name, auth)
            .then((res) => {
              this.$store.commit("updateError", res);
              this.loadThemes();
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: function () {
    try {
      this.loadIcons();
      this.loadThemes();
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
.preview {
  min-height: 150px;
  min-width: 150px;
  border-radius: 1rem;
}
.preview-connection {
  margin-top: 30px;
  margin-bottom: 30px;
  height: 10px;
  width: 50%;
}
</style>
