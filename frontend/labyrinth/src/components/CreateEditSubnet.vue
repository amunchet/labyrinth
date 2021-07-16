<template>
  <b-modal id="create_edit_subnet" title="Create/Edit Subnet">
    <b-row>
      <b-col>Subnet</b-col>
      <b-col>
        <b>{{subnet.subnet}}</b>
      </b-col>
    </b-row>
    <hr />
    <h6>Network Link</h6>
    <i>This is for additional subnets that are routed through a router on this subnet</i>
    <b-row>
      <b-col>
        Link IP
      </b-col>
      <b-col>

        <b-input v-model="subnet.links.ip"/>
      </b-col>
    </b-row>
    <b-row>
      <b-col>
        Link Icon
      </b-col>
      <b-col>
        <b-select :options="icons" v-model="subnet.links.icon" />
      </b-col>
    </b-row><b-row>
      <b-col>
        Ref
      </b-col>
      <b-col>
        <b-input v-model="subnet.links.ref"/>
      </b-col>
    </b-row>
    <b-row>
      <b-col>Color</b-col>
      <b-col><b-select :options="colors" v-model="subnet.links.color" /></b-col>
    </b-row>
    <hr />
    <h6>Origin</h6>
    <i>This is the router that allows entry into this subnet.  It may be the local machine itself (127.0.0.1)</i>

    <b-row>
      <b-col>
        Origin IP
      </b-col>
      <b-col>
        <b-input v-model="subnet.origin.ip" />
      </b-col>
    </b-row>
    <b-row>
      <b-col>Origin Icon</b-col>
      <b-col>
        <b-select :options="icons" v-model="subnet.origin.icon" />
      </b-col>
    </b-row>

      <template #modal-footer>
        <div style="width: 100%;">
          
        <b-button class="float-left" variant="danger">Delete</b-button>
        <b-button class="float-right ml-2" variant="primary">OK</b-button>
        <b-button class="float-right">Cancel</b-button>
        </div>
      </template>
  </b-modal>
</template>
<script>
import Helper from '@/helper'
export default {
  name: "CreateEditSubnet",
  data(){
    return{
      subnet: "",
      icons: [],
      colors: [],
    }
  },
  watch: {
    inp_subnet: function(val){
      if(val != ""){
      this.subnet = JSON.parse(JSON.stringify(this.inp_subnet))
      delete this.subnet["hosts"]
      delete this.subnet["groups"]
      }else{
        this.subnet = {
          subnet :"",
          origin: {
            ip: "",
            icon: ""
          },
          links: {
            ref: "",
            ip : "",
            icon: "",
            color: "",
          }
        }
      }
    }
  },
  props: ["inp_subnet"],
  mounted: function(){
    try{
      this.icons = Helper.listIcons()
      this.colors = Helper.listColors()
    }catch(e){
      this.$store.commit('updateError', e)
    }
  },
};
</script>
<style lang="scss" scoped>
.row{
  margin-top: 1rem;
  margin-bottom: 1rem;
}
</style>