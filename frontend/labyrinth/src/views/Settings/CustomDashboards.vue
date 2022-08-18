<template>
  <div>
    <b-modal id="modal-1" size="xl">
      <v-stage ref="stage" :config="stageSize" class="border-black">
        <v-layer ref="layer">
          <v-text
            @dragstart="handleDragStart"
            @dragend="handleDragEnd"
            :config="{
              text: 'Draggable Text',
              x: 50,
              y: 50,
              draggable: true,
              fill: isDragging ? 'green' : 'black',
            }"
          />
        </v-layer>
      </v-stage>
    </b-modal>

    <b-modal
      id="image-popup"
      size="xl"
      :title="selected_image"
      class="overflow-hidden"
    >
      <b-img
        :src="
          '/api/custom_dashboard_images/' +
          $auth.accessToken +
          '/' +
          selected_image
        "
      />
    </b-modal>
    <b-row>
      <b-col>
        <h4>Dashboards</h4>

        <b-button v-b-modal.modal-1>Open</b-button>
      </b-col>
      <b-col>
        <h4>Dashboard Images</h4>

        <div v-if="available_images" class="overflow-hidden">
          <div
            v-for="(item, idx) in available_images"
            v-bind:key="idx"
            class="box float-left"
          >
            <img
              @click="
                () => {
                  selected_image = item;
                  $bvModal.show('image-popup');
                }
              "
              role="button"
              :src="
                '/api/custom_dashboard_images/' + $auth.accessToken + '/' + item
              "
              width="100px"
            />
            <b-button
              variant="link"
              class="text-danger m-0 p-0 mt-2"
              @click="deleteImage(item)"
            >
              <font-awesome-icon
                icon="times"
                size="1x"
                class="float-left m-0 p-0 mt-1"
              />
              &nbsp; Delete
            </b-button>
          </div>
        </div>

        <hr />
        <div class="text-left">Upload New Image</div>
        <b-form-file
          class="float-left"
          v-model="new_image"
          placeholder="..."
          drop-placeholder="Drop here..."
        ></b-form-file>
        <br />
        <b-button
          variant="link"
          class="m-0 mt-2 p-0 float-left"
          @click="
            () => {
              new_image = '';
            }
          "
        >
          <font-awesome-icon icon="times" size="1x" />
        </b-button>
      </b-col>
    </b-row>
  </div>
</template>

<script>
import Helper from "@/helper";

const width = window.innerWidth;
const height = window.innerHeight;

export default {
  data() {
    return {
      stageSize: {
        width: width,
        height: height,
      },
      isDragging: false,

      selected_image: "",
      available_images: [],
      new_image: "",
    };
  },
  watch: {
    new_image: /* istanbul ignore next */ function (val) {
      this.uploadHelper(val);
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadImages();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  methods: {
    handleDragStart() {
      this.isDragging = true;
    },
    handleDragEnd() {
      this.isDragging = false;
    },

    loadImages: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("custom_dashboard_images", "", auth)
        .then((res) => {
          this.available_images = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    uploadHelper: /* istanbul ignore next */ function (val) {
      if (val) {
        var auth = this.$auth;
        var formData = new FormData();
        formData.append("file", val);
        console.log(val);
        Helper.apiPost("custom_dashboard_images", "", "", auth, formData, true)
          .then(() => {
            this.loadImages();
            this.new_image = "";
          })
          .catch((e) => {
            if (("" + e).indexOf("521") != -1) {
              this.$store.commit(
                "updateError",
                "Error: Invalid file type uploaded.  Make sure your file is the correct type (Encrypted Ansible, Telegraf Conf, etc.)"
              );
            } else {
              this.$store.commit("updateError", e);
            }
          });
      }
    },
    deleteImage: /* istanbul ignore next */ function (val) {
      var auth = this.$auth;
      this.$bvModal
        .msgBoxConfirm("Are you sure you want to delete this image?")
        .then((res) => {
          if (!res) {
            return;
          }

          Helper.apiDelete("custom_dashboard_images", val, auth)
            .then(() => {
              this.loadImages();
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
};
</script>
<style scoped>
.border-black {
  border: 1px solid black;
}
.box {
  border: 1px solid lightgrey;
  width: 25%;
  margin: 1rem;
  padding: 1rem;
  text-align: center;
  border-radius: 0.5rem;
}
.text-left {
  text-align: left !important;
}
</style>
