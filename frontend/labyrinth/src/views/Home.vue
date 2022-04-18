<template>
  <div class="home">
    <div v-if="$auth.profile == null || $auth.profile == undefined">
      <h4>Please login to continue.</h4>
      <b-button @click="$auth.login()" variant="success">Login</b-button>
    </div>
    <div v-else>
      <b-avatar class="mb-2" :src="$auth.profile.picture" size="5rem" />
      <h4>Welcome, {{ $auth.profile.name }}</h4>
    </div>

    <hr />
    Scratch drag and drop
    {{ offsetX }}, {{ offsetY }}
    <div class="ml-4 mt-4" @dragover="(e)=>e.preventDefault()">
      <div class="outer" ref="outer_1">
        <div
          class="inner"
          draggable
          ref="inner_1"
          @dragstart="handleDragStart"
          @dragend="handleDrop"
          :style="
            'position:relative; left: ' +
            offsetX +
            'px; top: ' +
            offsetY +
            'px;'
          "
          :key="offsetX + offsetY"
        >
          &nbsp;
        </div>
      </div>
    </div>
      <b-col>
        1.  Allow upload of photos. (CRUD of them as well)<br />
        2.  Allow addition of hosts (and edit how they appear) - subnets, services too? <br />
        3.  Naming and Managing the dashboards
      </b-col>
  </div>
</template>

<script>
// @ is an alias to /src

export default {
  name: "Home",
  components: {},
  data() {
    return {
      offsetX: 0,
      offsetY: 0,

      where_in_box_clicked_x: 0,
      where_in_box_clicked_y: 0,
    };
  },
  methods: {
    handleDragStart: function (e) {

      this.where_in_box_clicked_x = e.offsetX;
      this.where_in_box_clicked_y =  e.offsetY
    },
    handleDrop: function (e) {

      var box_top = this.$refs.outer_1.offsetTop;
      var box_left = this.$refs.outer_1.offsetLeft;

      var box_height = this.$refs.outer_1.clientHeight;
      var box_width = this.$refs.outer_1.clientWidth;

      var dragging_box_width = this.$refs.inner_1.clientWidth;
      var dragging_box_height = this.$refs.inner_1.clientHeight;

      var structure = {
        box_top: box_top,
        box_left: box_left,
        box_height: box_height,
        box_width: box_width,
        dragging_box_height: dragging_box_height,
        dragging_box_width: dragging_box_width,
        x: e.pageX - this.where_in_box_clicked_x,
        y: e.pageY - this.where_in_box_clicked_y,
      };

      if (structure.x < box_left) {
        this.offsetX = box_left;
      } else if (structure.x > box_left + box_width) {
        this.offsetX = box_left + box_width - dragging_box_width;
      } else {
        this.offsetX = structure.x - box_left;
      }

      if (structure.y < box_top) {
        this.offsetY = 0;
      } else if (structure.y > box_height + box_top) {
        this.offsetY = box_height - dragging_box_height;
      } else {
        this.offsetY = structure.y - box_top;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.outer {
  width: 500px;
  height: 500px;
  margin-left: 10;
  border: 1px solid red;
}
.inner {
  height: 100px;
  background-color: black;
  width: 100px;
    cursor: move; /* fallback if grab cursor is unsupported */
    cursor: grab;
    cursor: -moz-grab;
    cursor: -webkit-grab;
}
.inner:active{
      cursor: grabbing;
    cursor: -moz-grabbing;
    cursor: -webkit-grabbing;
}
</style>