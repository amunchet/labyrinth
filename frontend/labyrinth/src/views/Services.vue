<template>
  <b-container>
      <h4>Services</h4>
      <b-button variant="primary">Load Services Template</b-button>

      <ServiceComponent v-for="(section, idx) in data" v-bind:key="idx" :name="idx" :data="section" :start_minimized="true" :isParent="true"/>

  
    <hr />
</b-container>
</template>

<script>
import Helper from '@/helper'
import ServiceComponent from '@/components/Service'
export default {
  name: "Services",
  components: {
    ServiceComponent
  },
  data() {
    return {
      data: [
        {
          name: "global_tags",
        },
        {
          name: "inputs",

        },
        {
          name: "agent",
        },
      ],

      // List children for a specific element
      list_children: ['cpu', 'disk', 'diskio', 'kernel', 'mem'],
      
      // Details - this will look for parent of whatever
      details: {
        name: "cpu",
        comment: "",
        fields: {
          "percpu" : {
            "raw" : "percpu = true",
            "comments" : [
              "Read metrics about cpu usage"
            ]
          },
          "totalcpu" : "",
          "collect_cpu_time": "",
          "report_active": "",
        }
      },
    };
  },
  methods: {
    loadStructure: /* istanbul ignore next */ function(){
      var auth = this.$auth
      Helper.apiCall("redis", "get_structure", auth).then(res=>{
        this.data = res
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    }
  },
  mounted: /* istanbul ignore next */ function(){
    try{
      this.loadStructure()
    }catch(e){
      this.$store.commit('updateError', e)
    }
  }
};
</script>

<style scoped></style>
