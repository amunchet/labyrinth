<template>
  <b-modal id="group_edit" :title="'Group Options for ' + selected_group">
    <template #modal-footer="{ok}">
      <div>
        <b-button @click="ok()">Cancel</b-button>
      </div>
    </template>
    <div class="mr-3">
      <b-row>
        <b-col cols="5"> Monitor All </b-col>
        <b-col cols="6">
          <b-form-checkbox
            size="lg"
            name="check-button"
            switch
            v-model="status"
          >
          </b-form-checkbox>
        </b-col>
      </b-row>
      <b-row>
        <b-col cols="5"> Rename Group</b-col>
        <b-col cols="6">
          <b-input size="sm" />
        </b-col>
        <b-col cols="1">
          <b-button variant="success" size="sm">
            <font-awesome-icon icon="check" size="1x" />
          </b-button>
        </b-col>
      </b-row>
      <b-row>
        <b-col cols="5"> Change Icons </b-col>
        <b-col cols="6">
          <b-select size="sm"/>
        </b-col>
        <b-col cols="1">
          <b-button size="sm" variant="warning">
            <font-awesome-icon icon="save" />
          </b-button>
        </b-col>
      </b-row>
      <b-row>
        <b-col cols="5"> Add Service to All</b-col>
        <b-col cols="6">
          <b-select size="sm"/>
        </b-col>
        <b-col cols="1">
          <b-button size="sm" variant="primary">
            <font-awesome-icon icon="plus" />
          </b-button>
        </b-col>
      </b-row>
    </div>
  </b-modal>
</template>
<script>
import Helper from '@/helper'
export default {
  name: "GroupModal",
  props: ["selected_group", "selected_subnet"],
  data(){
    return{
      status: false 
    }
  },
  watch: {
    status: function(val){
        this.changeMonitor(val)
    }
  },
  methods: {
    changeMonitor: function(status){
      var auth = this.$auth
      var url = "monitor/" + this.selected_subnet.subnet + "/" + this.selected_group + "/" + status

      Helper.apiCall("group", url, auth).then((res)=>{
        this.$emit("updated")
        this.$store.commit('updateError', "Monitor update: " + res)
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    changeGroupName: function(){

    },
    changeIcons: function(){

    },
    addService: function(){

    },

    listIcons: function(){

    },
    listServices: function(){

    }

  },
};
</script>
<style lang="scss" scoped>
.row {
  margin: 1rem 0 1rem 0;
}
.col-5{
  user-select: none;
}
</style>