<template>
  <div
    :class="determineClass()"
    :id="name"
    v-if="
      (isParent ||
        service_filter == '' ||
        (parent + name).indexOf(service_filter) != -1) &&
      ((name != '' && typeof parsed_data == 'object') || !minimized)
    "
  >
    <h2 v-if="name != '' && typeof parsed_data == 'object'">
      <b-button
        variant="link"
        class="mt-0 pt-0 pb-0 mb-0 pr-1 shadow-none"
        @click="minimized = !minimized"
      >
        <font-awesome-icon
          class="pt-1"
          v-if="minimized"
          icon="caret-right"
          size="2x"
        />
        <font-awesome-icon
          class="pt-1"
          v-if="!minimized"
          icon="caret-down"
          size="2x"
        />
      </b-button>
      {{ format(name) }}
      <b-button
        v-if="!isWrite && depth * 1 < 2"
        class="mb-0 mt-1 p-0 pl-1 pr-1 mr-1 float-right"
        variant="success"
        @click="add(parsed_data, name, parent)"
      >
        <font-awesome-icon class="pt-1" icon="plus" size="1x" />
      </b-button>

      <b-button
        v-if="isWrite"
        class="mb-0 mt-1 p-0 pl-1 pr-1 mr-1 float-right"
        variant="danger"
        @click="
          () => {
            $emit('child_delete', name);
          }
        "
      >
        <font-awesome-icon class="pt-1" icon="times" size="1x" />
      </b-button>

      <b-button
        class="float-right shadow-none"
        variant="link"
        @click="loadComment()"
      >
        <font-awesome-icon icon="info-circle" size="1x" />
      </b-button>
    </h2>
    <div>
      <div class="text-left comment" v-if="comment.comments != undefined">
        <span v-for="(comment, i) in comment.comments" v-bind:key="i">
          {{ comment.replace(/#/g, "").replace("/", " / ") }}&nbsp;
        </span>
      </div>

      <div v-if="typeof parsed_data == 'object' && Array.isArray(parsed_data)">
        <div class="overflow-hidden">
          <b-button
            class="float-left m-0 p-0"
            variant="link"
            v-if="!minimized && isWrite"
            @click="
              () => {
                parsed_data.push(JSON.parse(JSON.stringify(parsed_data[0])));
                $forceUpdate();
              }
            "
            >+ {{ name }}</b-button
          >
        </div>
        <ServiceComponent
          v-for="(item, idx) in parsed_data"
          v-bind:key="idx"
          :name="idx"
          :inp_data="item"
          :arrayChild="true"
          :parent="parent + '.' + name"
          :start_minimized="minimized"
          service_filter=""
          :depth="depth * 1 + 1"
          @add="parsed"
          @update="
            (update_name, val) => {
              parsed_data[update_name] = val;
              $emit('update', name, parsed_data);
            }
          "
          @child_delete="handle_child_delete"
          :isWrite="isWrite"
        />
      </div>
      <div v-else-if="typeof parsed_data == 'object'">
        <ServiceComponent
          v-for="(item, idx) in parsed_data"
          v-bind:key="idx"
          :name="idx"
          :inp_data="item"
          :parent="parent + '.' + name"
          :start_minimized="minimized"
          :service_filter="service_filter"
          :depth="depth * 1 + 1"
          @add="parsed"
          @update="
            (update_name, val) => {
              parsed_data[update_name] = val;
              $emit('update', name, parsed_data);
            }
          "
          @child_delete="handle_child_delete"
          :isWrite="isWrite"
        />
        <b-row v-if="isWrite && depth > 0">
          <b-col>
            <b-input placeholder="Name" v-model="new_field_name" size="sm" />
          </b-col>
          <b-col>
            <b-input placeholder="Value" v-model="new_field_value" size="sm" />
          </b-col>
          <b-col cols="2">
            <b-button
              class="float-left"
              variant="success"
              size="sm"
              @click="
                () => {
                  if (new_field_name != '' && new_field_value != '') {
                    parsed_data[new_field_name] = new_field_value;
                    $emit('update', name, parsed_data);
                    $forceUpdate();
                  }
                }
              "
            >
              <font-awesome-icon icon="plus" size="1x" />
            </b-button>
          </b-col>
        </b-row>
      </div>
      <div v-else-if="typeof parsed_data == 'number'">
        <b-row>
          <b-col>
            <div v-if="!arrayChild" class="float-left mt-1 text-capitalize">
              {{ format(name) }}
            </div>

            <b-button
              class="float-left shadow-none"
              variant="link"
              @click="loadComment()"
            >
              <font-awesome-icon icon="info-circle" size="1x" />
            </b-button>
          </b-col>
          <b-col :cols="col_size">
            <b-input v-model="parsed_data" />
          </b-col>
          <b-col cols="0" v-if="isWrite">
            <b-button
              @click="
                () => {
                  $emit('child_delete', name);
                }
              "
              variant="link"
              class="text-danger"
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
      </div>
      <div v-else-if="typeof parsed_data == 'boolean'">
        <b-row>
          <b-col>
            <div v-if="!arrayChild" class="float-left mt-1 text-capitalize">
              {{ format(name) }}
            </div>
            <b-button
              class="float-left shadow-none"
              variant="link"
              @click="loadComment()"
            >
              <font-awesome-icon icon="info-circle" size="1x" />
            </b-button>
          </b-col>
          <b-col :cols="col_size">
            <b-form-checkbox v-model="parsed_data" switch />
          </b-col>
          <b-col cols="0" v-if="isWrite">
            <b-button
              @click="
                () => {
                  $emit('child_delete', name);
                }
              "
              variant="link"
              class="text-danger"
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
      </div>
      <div v-else>
        <b-row>
          <b-col>
            <div v-if="!arrayChild" class="float-left mt-1 text-capitalize">
              {{ format(name) }}
            </div>
            <b-button
              class="float-left shadow-none"
              variant="link"
              @click="loadComment()"
            >
              <font-awesome-icon icon="info-circle" size="1x" />
            </b-button>
          </b-col>
          <b-col :cols="col_size">
            <b-input v-model="parsed_data" />
          </b-col>
          <b-col cols="0" v-if="isWrite">
            <b-button
              @click="
                () => {
                  $emit('child_delete', name);
                }
              "
              variant="link"
              class="text-danger"
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
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
    "inp_data",
    "arrayChild",
    "parent",
    "start_minimized",
    "isParent",
    "service_filter",
    "depth",
    "isWrite", //This describes if we can delete items
  ],
  data() {
    return {
      comment_name: "",
      comment: " ",
      col_size: 5,
      minimized: true,
      parsed_data: {},

      new_field_name: "",
      new_field_value: "",
    };
  },
  methods: {
    add: function (item, name, parent) {
      let structure = {
        item: item,
        name: name,
        parent: parent || "",
      };

      this.$emit("add", JSON.stringify(structure));
      this.$forceUpdate();
    },
    handle_child_delete: function (val) {
      if (Array.isArray(this.parsed_data)) {
        this.parsed_data.splice(val, 1);
      } else {
        delete this.parsed_data[val];
      }
      this.$emit(
        "update",
        this.name,
        JSON.parse(JSON.stringify(this.parsed_data))
      );
      this.$forceUpdate();
    },
    parsed: function (item) {
      let structure = JSON.parse(item);
      this.add(structure.item, structure.name, structure.parent);
    },
    loadComment: /* istanbul ignore next */ function () {
      if (this.comment != "") {
        this.comment = "";
        return;
      }
      let auth = this.$auth;
      Helper.apiCall("redis", "get_comments/" + this.comment_name, auth)
        .then((res) => {
          this.comment = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    determineClass: function () {
      if (
        typeof this.parsed_data == "object" &&
        Array.isArray(this.parsed_data)
      ) {
        return "main array child";
      } else if (typeof this.parsed_data != "object") {
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
    inp_data: function (val) {
      if (val != "") {
        this.parsed_data = val;
      }
    },
    parsed_data: function (val) {
      this.$emit("update", this.name, val);
    },
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
    try {
      this.parsed_data = this.inp_data;
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
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
// Specific styles
#outputs {
  max-height: 400px;
  overflow-y: scroll;
  overflow-x: hidden;
}

#processors {
  max-height: 400px;
  overflow-y: scroll;
  overflow-x: hidden;
}

#inputs {
  max-height: 400px;
  overflow-y: scroll;
  overflow-x: hidden;
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
  border-bottom: 1px dotted #efefed;
}
.row {
  margin-top: 0.25rem;
  padding-left: 1rem;
  padding-right: 0.5rem;
}
input {
  margin-bottom: 0.5rem;
}
</style>
