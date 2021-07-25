<template>
  <div
    :class="determineClass()"
    :id="name"
    v-if="
      (isParent ||
        service_filter == '' ||
        (parent + name).indexOf(service_filter) != -1) &&
      ((name != '' && typeof data == 'object') || !minimized)
    "
  >
    <h2 v-if="name != '' && typeof data == 'object'">
      <b-button
        variant="link"
        class="mt-0 pt-0 pb-0 mb-0 pr-1 shadow-none"
        @click="minimized = !minimized"
      >
        <font-awesome-icon class="pt-1" v-if="minimized" icon="caret-right" size="2x" />
        <font-awesome-icon class="pt-1"  v-if="!minimized" icon="caret-down" size="2x" />
      </b-button>
      {{ format(name) }}
      <b-button v-if="depth *1 < 2" class="mb-0 mt-1 p-0 pl-1 pr-1 mr-1 float-right" variant="success" @click="add(data, name, parent)">
        <font-awesome-icon class="pt-1" icon="plus" size="1x" />
      </b-button>

      <b-button class="float-right shadow-none" variant="link" @click="loadComment()">
        <font-awesome-icon icon="info-circle" size="1x" />
      </b-button>
    </h2>
    <div>
      <div class="text-left comment" v-if="comment.comments != undefined">
        <span v-for="(comment, i) in comment.comments" v-bind:key="i">
          {{ comment.replace(/#/g, "") }}&nbsp;
        </span>
      </div>

      <div v-if="typeof data == 'object' && Array.isArray(data)">
        <div class="overflow-hidden">
          <b-button class="float-left m-0 p-0" variant="link" v-if="!minimized"
            >+ {{ name }}</b-button
          >
        </div>
        <ServiceComponent
          v-for="(item, idx) in data"
          v-bind:key="idx"
          :name="idx"
          :data="item"
          :arrayChild="true"
          :parent="parent + '.' + name"
          :start_minimized="minimized"
          service_filter=""
          :depth="depth * 1 + 1"
          @add="parsed"
        />
      </div>
      <div v-else-if="typeof data == 'object'">
        <ServiceComponent
          v-for="(item, idx) in data"
          v-bind:key="idx"
          :name="idx"
          :data="item"
          :parent="parent + '.' + name"
          :start_minimized="minimized"
          :service_filter="service_filter"
          :depth="depth * 1 + 1"
          @add="parsed"
        />
      </div>
      <div v-else-if="typeof data == 'number'">
        <b-row>
          <b-col>
            <div v-if="!arrayChild" class="float-left mt-1 text-capitalize">
              {{ format(name) }}
            </div>

            <b-button class="float-left" variant="link" @click="loadComment()">
              <font-awesome-icon icon="info-circle" size="1x" />
            </b-button>
          </b-col>
          <b-col :cols="col_size">
            <b-input v-model="data" />
          </b-col>
        </b-row>
      </div>
      <div v-else-if="typeof data == 'boolean'">
        <b-row>
          <b-col>
            <div v-if="!arrayChild" class="float-left mt-1 text-capitalize">
              {{ format(name) }}
            </div>
            <b-button class="float-left" variant="link" @click="loadComment()">
              <font-awesome-icon icon="info-circle" size="1x" />
            </b-button>
          </b-col>
          <b-col :cols="col_size">
            <b-form-checkbox v-model="data" switch />
          </b-col>
        </b-row>
      </div>
      <div v-else>
        <b-row>
          <b-col>
            <div v-if="!arrayChild" class="float-left mt-1 text-capitalize">
              {{ format(name) }}
            </div>
            <b-button class="float-left" variant="link" @click="loadComment()">
              <font-awesome-icon icon="info-circle" size="1x" />
            </b-button>
          </b-col>
          <b-col :cols="col_size">
            <b-input v-model="data" />
          </b-col>
        </b-row>
      </div>
    </div>
  </div>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "ServiceComponent",
  props: [
    "name",
    "data",
    "arrayChild",
    "parent",
    "start_minimized",
    "isParent",
    "service_filter",
    "depth"
  ],
  data() {
    return {
      comment_name: "",
      comment: " ",
      col_size: 5,
      minimized: true,
    };
  },
  methods: {
    add: function(item, name, parent){

      var structure = {
        "item" : item,
        "name" : name,
        "parent" : parent || ""
      }

      this.$emit("add", JSON.stringify(structure))
      this.$forceUpdate()
    },
    parsed: function(item){
      var structure = JSON.parse(item)
      this.add(structure.item, structure.name, structure.parent)
    },
    loadComment: /* istanbul ignore next */ function () {
      if (this.comment != "") {
        this.comment = "";
        return;
      }
      var auth = this.$auth;
      Helper.apiCall("redis", "get_comments/" + this.comment_name, auth)
        .then((res) => {
          this.comment = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    determineClass: function () {
      if (typeof this.data == "object" && Array.isArray(this.data)) {
        return "main array child";
      } else if (typeof this.data != "object") {
        return "child";
      } else {
        return "main border";
      }
    },
    format(item) {
      try {
        return item.replace(/_/g, " ");
      } catch (e) {
        return item;
      }
    },
  },
  watch: {
    start_minimized: function (val) {
      this.minimized = val;
    },
    service_filter: function (val) {
      if (val != "") {
        this.minimized = false;
      } else {
        this.minimized = true;
      }
    },
  },
  mounted: function () {
    if (this.parent != undefined) {
      this.comment_name = (this.parent + "." + this.name)
        .replace(".0", "")
        .replace("undefined.", "");
    } else {
      this.comment_name = this.name;
    }

    if (this.start_minimized != undefined) {
      this.minimized = this.start_minimized;
    }
  },
};
</script>
<style lang="scss" scoped>
// Specific styles
#outputs {
  max-height: 400px;
  overflow-y: scroll;
}

#processors {
  max-height: 400px;
  overflow-y: scroll;
}

#inputs {
  max-height: 400px;
  overflow-y: scroll;
}

.comment:first-letter {
  text-transform: capitalize;
}
.comment {
  padding: 1rem;
  margin: 1rem;
  background-color: #efefed;
  border-radius: 0.5rem;
}
h2 {
  text-align: left;
  text-transform: capitalize;
  font-size: 1.5rem;
  line-height: 1;
  margin: 0.25rem;
}
.child h2 {
  font-size: 12pt;
}
.border {
  border: 1px solid grey;
  border-radius: 0.5rem;
}
.main {
  margin: 0.5rem;
}
.array {
  margin-bottom: 1rem;
}
.child {
  margin: 0.5rem;
  border-bottom: 1px solid #efefed;
}
.row {
  margin-top: 0.25rem;
  padding-left: 1rem;
  padding-right: 0.5rem;
}
</style>
