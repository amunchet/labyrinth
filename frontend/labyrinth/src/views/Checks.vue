<template>
  <b-container class="text-left">
    <h2>Create/Edit a Service</h2>
    
    <b-modal id="add_service" title="Add/Edit Service" @ok="saveCheck">
        <b-row>
          <b-col><b>Name</b><br />
          <span class="helptext">Name of the service</span>
          </b-col>
          <b-col>
            <b-input v-model="selected_service.name" placeholder="E.g. check_hd" /></b-col>
        </b-row>
        <b-row>
          <b-col><b>Type</b><br />
          <span class="helptext">Service type</span>
          </b-col>
          <b-col>
            <b-input disabled v-model="selected_service.type" placeholder="E.g. check" /></b-col>
        </b-row>
        <b-row>
          <b-col><b>Metric</b><br />
          <span class="helptext">Specific service metric</span>
          </b-col>
          <b-col>
            <b-input v-model="selected_service.metric" placeholder="E.g. diskio" /></b-col>
        </b-row>
        <b-row>
          <b-col><b>Field</b><br />
          <span class="helptext">Service metric field</span>
          </b-col>
          <b-col>
            <b-input v-model="selected_service.field" placeholder="E.g. read_time" /></b-col>
        </b-row>
        <b-row>
          <b-col><b>Comparison</b><br />
          <span class="helptext">Comparison operator on the service</span>
          </b-col>
          <b-col>
            <b-select :options="comparison_types" v-model="selected_service.comparison" />
            </b-col>
        </b-row>
        <b-row>
          <b-col><b>Value</b><br />
          <span class="helptext">Target value of the service</span>
          </b-col>
          <b-col>
            <b-input v-model="selected_service.value" placeholder="E.g. 100" /></b-col>
        </b-row>

    </b-modal>

    <b-button @click="()=>{
        selected_service = {
          type: 'check'
        }
        $bvModal.show('add_service')
      }"
      variant="success"
      class="m-2 float-right"
      >+ Add Service</b-button>

    <b-table :fields="service_fields" :items="services" striped>
      <template v-slot:cell(name)="row">
        <b-button variant="link" class="shadow-none"
          @click="()=>{
            selected_service = row.item
            $bvModal.show('add_service')
            }"
        >
          <font-awesome-icon icon="edit" size="1x" />
        </b-button>
        {{row.item.name}}
      </template>
    </b-table>
    <hr />
    <h2 class='mt-2 mb-2'>Latest Metrics</h2>
    <div class="metrics-table mb-2">
    <b-table  :items="metrics" striped :fields="['name', 'tags', 'fields', 'timestamp']">
      <template v-slot:cell(fields)="row">
        <div v-for="(item, idx) in row.item.fields" v-bind:key="idx">
          {{idx}} : {{item}} <br />
        </div>
      </template>
      <template v-slot:cell(tags)="row">
        <div v-for="(item, idx) in row.item.tags" v-bind:key="idx">
          {{item}} <br />
        </div>
      </template>
    </b-table>
    </div>
    <hr />
    <h3>Settings</h3>
    Frequency of scans

  </b-container>
</template>
<script>
import Helper from '@/helper'
export default {
  data(){
    return{
      selected_service: {
        type: "check"
      },
      services: [],
      comparison_types: ["greater", "less", "equal"],
      service_fields: ["name", "type", "field", "metric", "comparison", "value"],
      metrics: [],
    }
  },
  methods: {
    loadServices: /* istanbul ignore next */ function(){
      var auth = this.$auth
      Helper.apiCall("services", "all", auth).then(res=>{
        this.services = res
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    loadMetrics: /* istanbul ignore next */ function(){
      var auth = this.$auth
      Helper.apiCall("metrics", "25", auth).then(res=>{
        this.metrics = res
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    saveCheck: /* istanbul ignore next */ function(e){
      e.preventDefault()
      var auth = this.$auth
      var formData = new FormData()
      formData.append("data", JSON.stringify(this.selected_service))
      Helper.apiPost("service", "", "", auth, formData).then(res=>{
        this.loadServices()
        this.$store.commit('updateError', res)
        this.$bvModal.hide("add_service")
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    }
  },
  mounted: /* istanbul ignore next */ function(){
    try{
      this.loadServices()
      this.loadMetrics()
    }catch(e){
      this.$store.commit('updateError', e)
    }
  },
}
</script>
<style lang="scss" scoped>
.row{
  margin: 1rem;
}
.helptext{
  font-size: 8pt;
  color: grey;
  font-family: Arial, sans-serif;
}
.metrics-table{
  height: 400px;
  overflow-y: scroll;
  overflow-x: hidden;
}
</style>