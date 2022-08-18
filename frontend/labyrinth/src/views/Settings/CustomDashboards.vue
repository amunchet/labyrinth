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

    <b-row>
      <b-col>
        <h4>Dashboards</h4>

        <b-button v-b-modal.modal-1>Open</b-button>
      </b-col>
      <b-col>
        <h4>Dashboard Images</h4>
        {{ available_images }}

        {{new_image.name}}


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

      available_images: [],
      new_image: "",
    };
  },
  watch: {
    new_image: /* istanbul ignore next */ function(val){
      this.uploadHelper(val)
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
        console.log(val)
        Helper.apiPost(
          "custom_dashboard_images",
          "",
          "",
          auth,
          formData,
          true
        )
          .then(() => {
            this.loadImages()
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
    }
  },
};
</script>
<style scoped>
.border-black {
  border: 1px solid black;
}
</style>