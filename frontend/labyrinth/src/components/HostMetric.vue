<template>
  <b-modal id="service_detail" title="Service Detail" size="xl">
    <line-chart height="100px" :chart-data="datacollection"></line-chart>
    <button @click="fillData()">Randomize</button>

    <b-table :items="result" v-if="!loading"/>
    <b-spinner v-else  />
  </b-modal>
</template>

<script>
  import LineChart from './charts/BarChart'

import Helper from '@/helper'

  export default {

  name: "HostMetric",
  props: ["data"],
    components: {
      LineChart
    },
    data () {
      return {
        datacollection: null,

      result: [],
      loading: false,
      }
    },
    mounted () {
      this.fillData()
    },
    methods: {
      fillData () {
        this.datacollection = {
          labels: [this.getRandomInt(), this.getRandomInt()],
          datasets: [
            {
              label: 'Data One',
              backgroundColor: '#f87979',
              data: [this.getRandomInt(), this.getRandomInt()]
            }, {
              label: 'Data One',
              backgroundColor: '#f87979',
              data: [this.getRandomInt(), this.getRandomInt()]
            }
          ]
        }
      },
      getRandomInt () {
        return Math.floor(Math.random() * (50 - 5 + 1)) + 5
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

  }
</script>

<style>
  .small {
    max-width: 600px;
    margin:  150px auto;
  }
</style>
