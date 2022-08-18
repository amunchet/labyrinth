<template>
  <div>
    <b-modal id="modal-1" size="xl" title="Custom Dashboard Drawing">
      <b-row>
        <b-col> Select Background image: </b-col>
        <b-col>
          <b-select
            :options="available_images"
            v-model="drawing.background_image"
          />
        </b-col>
      </b-row>
      <hr />
      <b-row>
        <b-col>
          Select Subnet <br />
          <b-select />
        </b-col>
        <b-col>
          Select Group <br />
          <b-select />
        </b-col>
        <b-col>
          Select Host <br />
          <b-select />
        </b-col>
      </b-row>
      <b-row>
        <b-col>
          <b-button> Add New Service </b-button>
        </b-col>
        <b-col> </b-col>
        <b-col>
          <b-button>Reset all Rotations</b-button>
          <b-button>Remove Host</b-button>
        </b-col>
      </b-row>
      <hr />

      <v-stage
        class="border-black"
        ref="stage"
        :config="stageSize"
        @mousedown="handleStageMouseDown"
        @touchstart="handleStageMouseDown"
      >
        <v-layer ref="background">
          <v-image
            :config="{
              image: computed_image,
            }"
            v-if="computed_image"
          />
        </v-layer>

        <v-layer ref="foreground">
          <v-image
            v-for="item in rectangles"
            :key="item.id"
            :config="item"
            @transformend="handleTransformEnd"
            @dragstart="handleDragStart"
            @dragend="handleDragEnd"
          >
          </v-image>
          <div v-for="item in rectangles" :key="item.id">
            <v-text
              v-if="!moving"
              :config="{
                text: item.name,
                fontSize: 30,
                fill: blue,
                x: item.x + 10,
                y: item.y + 10,
                rotation: item.rotation,
              }"
            />
          </div>
          <v-transformer ref="transformer" />
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
            /><br />
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
import Konva from "konva";

const width = window.innerWidth;
const height = window.innerHeight;

export default {
  data() {
    return {
      stageSize: {
        width: width,
        height: height,
      },

      rectangles: [
        {
          rotation: 0,
          x: 10,
          y: 10,
          scaleX: 1,
          scaleY: 1,
          name: "rect1",
          draggable: true,
        },
      ],
      selectedShapeName: "",
      moving: false,

      drawing: {
        background_image: "",
      },

      selected_image: "",
      available_images: [],
      new_image: "",
    };
  },
  computed: {
    computed_image: function () {
      var temp = this.drawing.background_image;
      if (this.drawing.background_image != "") {
        var image = new window.Image();
        var url =
          "/api/custom_dashboard_images/" + this.$auth.accessToken + "/";
        console.log(temp);

        image.src = url.concat(temp);
        return image;
      }
      return false;
    },
  },
  watch: {
    new_image: /* istanbul ignore next */ function (val) {
      this.uploadHelper(val);
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadImages();

      var image = new window.Image();
      image.src =
        "/api/custom_dashboard_images/" +
        this.$auth.accessToken +
        "/" +
        "sample.png";

      this.rectangles[0].image = image;
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  methods: {
    handleDragStart(e) {
      console.log(e);
      this.moving = true;
      this.$forceUpdate();
    },
    handleDragEnd(e) {
      console.log(e);
      this.moving = false;
      this.rectangles[e.target.index] = e.target.attrs;
      this.$forceUpdate();
    },
    handleTransformEnd(e) {
      // shape is transformed, let us save new attrs back to the node
      // find element in our state
      const rect = this.rectangles.find(
        (r) => r.name === this.selectedShapeName
      );
      // update the state
      rect.x = e.target.x();
      rect.y = e.target.y();
      rect.rotation = e.target.rotation();
      rect.scaleX = e.target.scaleX();
      rect.scaleY = e.target.scaleY();

      // change fill
      rect.fill = Konva.Util.getRandomColor();

      this.rectangles[e.target.index] = e.target.attrs;
      this.$forceUpdate();
    },
    handleStageMouseDown(e) {
      // clicked on stage - clear selection
      if (e.target === e.target.getStage()) {
        this.selectedShapeName = "";
        this.updateTransformer();

        return;
      }

      // clicked on transformer - do nothing
      const clickedOnTransformer =
        e.target.getParent().className === "Transformer";
      if (clickedOnTransformer) {
        return;
      }

      // find clicked rect by its name
      const name = e.target.name();
      const rect = this.rectangles.find((r) => r.name === name);
      if (rect) {
        this.selectedShapeName = name;
      } else {
        this.selectedShapeName = "";
      }
      this.updateTransformer();
    },
    updateTransformer() {
      // here we need to manually attach or detach Transformer node
      const transformerNode = this.$refs.transformer.getNode();
      const stage = transformerNode.getStage();
      const { selectedShapeName } = this;

      const selectedNode = stage.findOne("." + selectedShapeName);
      // do nothing if selected node is already attached
      if (selectedNode === transformerNode.node()) {
        return;
      }

      if (selectedNode) {
        // attach to another node
        transformerNode.nodes([selectedNode]);
      } else {
        // remove transformer
        transformerNode.nodes([]);
      }
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
  min-width: 25%;
  margin: 1rem;
  padding: 1rem;
  text-align: center;
  border-radius: 0.5rem;
}
.text-left {
  text-align: left !important;
}
</style>
