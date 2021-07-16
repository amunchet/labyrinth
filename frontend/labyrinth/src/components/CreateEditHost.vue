<template>
  <b-modal id="create_edit_host" title="Create/Edit Host" size="lg">
    <b-container>
      <b-row>
        <b-col>
          IP
        </b-col>
        <b-col>
          <b-input v-model="host.ip" />
        </b-col>
      </b-row>

    <b-row><b-col>MAC </b-col><b-col><b-input v-model="host.mac" /></b-col></b-row>
    <b-row><b-col>Group </b-col><b-col><b-input v-model="host.group" /></b-col></b-row>
    <b-row><b-col>Subnet</b-col><b-col><b-input v-model="host.subnet" /></b-col></b-row>
    <b-row><b-col>Icon</b-col><b-col><b-input v-model="host.icon" /></b-col></b-row>
    <b-row><b-col>Class</b-col><b-col><b-input v-model="host.class" /></b-col></b-row>

      </b-container>
    Is this a host with standard health metrics? 
    
    Services list - this is going to be the painful one. Want to be able to create
    service [FUTURE] - push the new metrics out I want to see the latest metrics
    for this host.
    <b-row>
      <b-col>
    <h4>Expected Open Ports</h4>
    <b-table v-if="host.open_ports" :items="host.open_ports.map(x=>{
      return {'port': x}
    })" striped />
      </b-col>
      <b-col>
    <h4>Services</h4>
    <b-table :items="host.services" striped />
      </b-col>
    </b-row>
    <b-row class="overflow-scroll">
    <h4>Latest Host Metrics</h4>
    <b-table :items="metrics" striped />
    </b-row>


    <template #modal-footer="{ cancel }">
      <div style="width: 100%">
        <b-button class="float-left" variant="danger" @click="deleteHost()"
          >Delete</b-button
        >
        <b-button
          class="float-right ml-2"
          variant="primary"
          @click="saveHost()"
          >OK</b-button
        >
        <b-button class="float-right" @click="cancel()">Cancel</b-button>
      </div>
    </template>
  </b-modal>
</template>
<script>
import Helper from '@/helper'
export default {
  name: "CreateEditHost",
  props: ["inp_host"],
  data(){
    return {
      isNew: true,
      host: "",
      metrics: [],
    }
  },
  watch: {
    inp_host: function(val){
      if(val == ""){
        this.isNew = true
      }else{
        this.isNew = false
        this.host = val
        this.loadMetrics()
      }
    }
  },
  methods: {
    loadMetrics: /* istanbul ignore next */ function(){
      var auth = this.$auth
      Helper.apiCall("metrics", this.host.mac, auth).then(res=>{
        this.metrics = res
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    saveHost: /* istanbul ignore next  */ function(){
      var auth = this.$auth
      var formData = new FormData()

      var host = JSON.parse(JSON.stringify(this.host))
      host["services"] = host["services"].map(x=>x["name"])
      formData.append("data", JSON.stringify(host))
      Helper.apiPost("host", "", "", auth, formData).then(res=>{
        this.$emit("update")
        this.$store.commit('updateError', res)
        this.$bvModal.hide("create_edit_host")
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
  },
}
</script>
<style lang="scss" scoped>
.row{
  margin: 1rem;
}
h4{
  text-align: center;
}
.overflow-scroll{
  overflow-x: scroll;
}
</style>