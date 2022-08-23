<template>
  <div>
    <b-modal
      id="modal-1"
      size="fullscreen"
      title="Custom Dashboard"
      @ok="saveCustomDashboard"
    >
      <b-row class="mb-2">
        <b-col>Custom Dashboard Name</b-col>
        <b-col
          ><b-input
            lazy
            v-model="drawing.name"
            placeholder="Enter Custom Dashboard Name"
          />
        </b-col>
      </b-row>
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
          <b-select v-model="selected_subnet" :options="subnets" />
        </b-col>
        <b-col>
          Select Group <br />
          <b-select v-model="selected_group" :options="groups" />
        </b-col>
        <b-col>
          Select Host <br />
          <b-select v-model="selected_host" :options="hosts" />
        </b-col>
      </b-row>
      <b-row>
        <b-col>
          <b-button @click="addHost()"> Add New Service </b-button>
        </b-col>
        <b-col> </b-col>
        <b-col>
          <b-button
            @click="
              () => {
                var found = drawing.components.find(
                  (x) => x.name == selectedShapeName
                );
                if (found) {
                  found.rotation = 0;
                }
                $forceUpdate();
              }
            "
            >Reset all Rotations</b-button
          >
          <b-button
            @click="
              () => {
                drawing.components = drawing.components.filter(
                  (x) => x.name != selectedShapeName
                );
                selectedShapeName = '';
                $forceUpdate();
              }
            "
            >Remove Host</b-button
          >
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
            v-for="item in drawing.components"
            :key="item.id"
            :config="item"
            @transformend="handleTransformEnd"
            @dragstart="handleDragStart"
            @dragend="handleDragEnd"
          >
          </v-image>
          <div v-for="item in drawing.components" :key="item.id">
            <v-text
              v-if="!moving"
              :config="{
                text: item.name,
                fontSize: 23,
                fill: blue,
                x: item.x + 10,
                y: item.y + 20,
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

        <b-button v-b-modal.modal-1 class="float-right mb-2" variant="success"  >+ Add Dashboard</b-button>

        <b-table
          :items="custom_dashboards"
          bordered
          striped
          :fields="['name', 'components', 'background_image', '_']"
        >
          <template v-slot:cell(components)="row">
            <b-table
              :items="
                row.item.components.map((x) => {
                  return {
                    name: x.name,
                    subnet: x.subnet,
                  };
                })
              "
              striped
            />
          </template>
          <template v-slot:cell(background_image)="row">
            <b-img
            width="100px"
              :src="
                '/api/custom_dashboard_images/' +
                $auth.accessToken +
                '/' +
                row.item.background_image
              "
            />
          </template>
          <template v-slot:cell(_)="row">
            <b-button
            @click="()=>{
                drawing.background_image = row.item.background_image
                drawing.name = row.item.name
                drawing.components = []
                row.item.components.forEach(item=>{
                  addHost(item.x, item.y, item.scaleX, item.scaleY, item.rotation, item.name, item.subnet, item.group)
                })
                $forceUpdate();
                $bvModal.show('modal-1')
              }"
            >
              Edit
              </b-button>
            </template>
        </b-table>
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
          <font-awesome-icon icon="times" size="1x" /> Clear Upload 
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

      selectedShapeName: "",
      moving: false,

      drawing: {
        background_image: "",
        components: [],
      },

      selected_image: "",
      available_images: [],
      new_image: "",

      subnets: [],
      selected_subnet: "",

      groups: [],
      selected_group: "",

      hosts: [],
      selected_host: "",

      custom_dashboards: [],
    };
  },
  computed: {
    computed_image: function () {
      var temp = this.drawing.background_image;
      if (this.drawing.background_image != "") {
        var image = new window.Image();
        var url =
          "/api/custom_dashboard_images/" + this.$auth.accessToken + "/";

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

    selected_subnet: /* istanbul ignore next */ function (val) {
      if (val != "") {
        this.loadGroups(val);
      } else {
        this.groups = [];
      }
      this.hosts = [];
    },
    selected_group: /* istanbul ignore next */ function (val) {
      this.hosts = [];
      if (val != "") {
        this.loadHosts(val);
      }
    },
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.loadSubnets();
      this.loadImages();
      this.loadCustomDashboards();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  methods: {
    handleDragStart(e) {
      console.log("Drag start");
      console.log(e);
      this.moving = true;
      this.$forceUpdate();
    },
    handleDragEnd(e) {
      console.log("Drag end");
      console.log(e);
      this.moving = false;
      this.drawing.components[e.target.index] = e.target.attrs;
      this.$forceUpdate();
    },
    handleTransformEnd(e) {
      console.log("Transform end");
      // shape is transformed, let us save new attrs back to the node
      // find element in our state
      const rect = this.drawing.components.find(
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

      this.drawing.components[e.target.index] = e.target.attrs;
      this.$forceUpdate();
    },
    handleStageMouseDown(e) {
      console.log("Handle Stage Mouse DOwn");
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
      const rect = this.drawing.components.find((r) => r.name === name);
      console.log(name)
      if (rect) {
        this.selectedShapeName = name;
      } else {
        this.selectedShapeName = "";
      }
      this.updateTransformer();
    },
    updateTransformer() {
      console.log("Update Tranform");
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

    addHost: function (x, y, scaleX, scaleY, rotation, name, subnet, group){
      var image = new window.Image();
      image.src = "img/dashboards/" + "host.png";

      if(x == undefined){
        x = 10
      }
      if(y == undefined){
        y = 10
      }
      if(scaleX == undefined){
        scaleX = 1
      }
      if(scaleY == undefined){
        scaleY = 1
      }
      if(rotation == undefined){
        rotation = 0
      }

      if(name == undefined) {
        name = this.selected_host
      }

      if(subnet == undefined){
        subnet = this.selected_subnet
      }
      if(group == undefined){ 
        group = this.selected_group
      }

      var new_rect = {
        rotation: rotation,
        x: x,
        y: y,
        scaleX: scaleX,
        scaleY: scaleY,
        name: name,
        subnet: subnet,
        group: group,
        type: "host",
        draggable: true,
        image: image,
      };

      this.drawing.components.push(new_rect);
      this.$forceUpdate();
    },

    loadSubnets: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("subnets", "", auth)
        .then((res) => {
          this.subnets = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadGroups: /* istanbul ignore next */ function (selected_subnet) {
      var auth = this.$auth;
      Helper.apiCall("group", selected_subnet, auth)
        .then((res) => {
          this.groups = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadHosts: /* istanbul ignore next */ function (selected_group) {
      var auth = this.$auth;
      Helper.apiCall("group", this.selected_subnet + "/" + selected_group, auth)
        .then((res) => {
          this.hosts = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
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
    loadCustomDashboards: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("custom_dashboards", "", auth)
        .then((res) => {
          this.custom_dashboards = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    saveCustomDashboard: /* istanbul ignore next */ function (e) {
      e.preventDefault();

      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(this.drawing));

      Helper.apiPost("custom_dashboard", "", this.drawing.name, auth, formData)
        .then(() => {
          this.loadCustomDashboards();
          this.$bvModal.hide("modal-1");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
};
</script>
<style scoped>
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
/deep/ .modal-fullscreen {
  max-width: 90% !important;
}
</style>
