<template>
    <b-container>
        <h2>Settings</h2>
        <hr />
        <b-row>
            <b-col>
                Enter Subnet to scan: <br />
                (i.e. 192.168.0.0/24)
            </b-col>
            <b-col>
                <b-input v-model="subnet" />
            </b-col>
            <b-col class="text-left">
                <b-button variant="primary" @click="startScan()">Start</b-button>
            </b-col>
        </b-row>
        <hr />
        <b-textarea disabled v-model="data" />
    </b-container>
    
</template>
<script>
import Helper from '@/helper'
export default {
    name: "Settings",
    data(){
        return{
        data: "",
        subnet: "",
        }
    },
    methods: {
        loadData: /* istanbul ignore next */ function(){
            var auth = this.$auth
            Helper.apiCall("redis", "", auth).then(res=>{
                this.data = res
            }).catch(e=>{
                this.$store.commit('updateError', e)
            })
        },
        startScan: /* istanbul ignore next */ function(){
            var auth = this.$auth
            var formData = new FormData()
            formData.append("data", this.subnet)
            Helper.apiPost("scan", "", "", auth, formData).then(res=>{
                this.$store.commit('updateError', res)
            }).catch(e=>{
                this.$store.commit('updateError', e)
            })
        },
    },
    mounted: function(){
        try{
            setInterval(this.loadData, 2000)
        }catch(e){
            this.$store.commit('updateError', e)
        }
    }
}
</script>
<style scoped>
    textarea{
        min-height: 400px;
    }
</style>
