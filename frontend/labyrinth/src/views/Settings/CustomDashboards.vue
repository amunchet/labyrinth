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
      </b-col>
    </b-row>
  </div>
</template>

<script>
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
    };
  },
  methods: {
    handleDragStart() {
      this.isDragging = true;
    },
    handleDragEnd() {
      this.isDragging = false;
    },
  },
};
</script>
<style scoped>
.border-black {
  border: 1px solid black;
}
</style>
