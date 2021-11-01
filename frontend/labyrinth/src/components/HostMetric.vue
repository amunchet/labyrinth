<template>
  <b-modal id="service_detail" title="Service Detail" size="xl">
    <b-table :items="result" v-if="!loading"/>
    <b-spinner v-else  />
  </b-modal>
</template>
<script>
import Helper from '@/helper'
export default {
  name: "HostMetric",
  props: ["data"],
  data(){
    return{
      result: [],
      loading: false,
    }
  },
  watch: {
    data: /* istanbul ignore next */ function(inp){
      if(inp != "" && inp != undefined && inp){
        var auth = this.$auth
        this.loading = true
        Helper.apiCall("metrics", this.data.ip + "/" + this.data.name, auth).then(res=>{
          this.result = res
          this.loading = false
        }).catch(e=>{
          this.$store.commit('updateError', e)
          this.loading = false
        })
      }
    }
  },
};
</script>
