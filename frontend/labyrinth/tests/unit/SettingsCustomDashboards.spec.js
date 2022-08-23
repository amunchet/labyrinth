// TEMPLATE FILE - Copy this file
import { config, shallowMount } from '@vue/test-utils'

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from '@/store'
import Instance from "@/views/Settings/CustomDashboards";

Vue.use(store)

config.mocks['$auth'] = {
    profile: {
        name: 'Test Name',
        picture: 'Test.jpg',
    },
    idToken: 1,
    login: function () { },
    getAccessToken: function () { },
}


config.mocks['loaded'] = true

let wrapper

beforeEach(() => {
    wrapper = shallowMount(Instance, {
        propsData: {
            options: [
                'All',
                'utopiany',
                'rousingr',
                'cunningh',
                'papayawi',
                'elegantc',
                'tidyseri',
                'quirkyco',
            ],
            onChange() {
                //console.log('select changed')
            },
        },
        store,
        methods: {},
        stubs: [
            'font-awesome-icon',
            'b-modal',
            'b-button',
            'b-select',
            'b-input',
            'b-row',
            'b-col',
            'b-table',
            'b-tab',
            'b-tabs',
            'b-spinner',
            'b-container',
            'b-textarea',
            'b-avatar',
            'b-form-file',
            'b-img',
            'b-modal',
            'v-layer',
            'v-stage',
            'b-form-checkbox',
            'v-transformer',
            'v-image',
            'v-text'
        ]
    })
})

afterEach(() => {
    wrapper.destroy()
})

describe('CustomDashboards', () => {
    test('is a Vue instance', () => {
        expect(wrapper.isVueInstance).toBeTruthy()
    })
    test("handleTransformEnd", ()=>{
        wrapper.vm.$data.selectedShapeName = "TESTNAME"

    })
    test("handleStageMouseDown", ()=>{
        wrapper.vm.handleStageMouseDown({
            target: {
                getStage: ()=>{},
                getParent: ()=>{
                    return{
                        className: "Transformer"
                    }
            }
        }
        })
    })

    test("updateTransformer", ()=>{
        wrapper.vm.$refs.transformer = {
            getNode: function(){
                return {
                    getStage: function(){
                        return {
                            findOne: function(item){
                                return item
                            }
                        }
                    },
                    node: ()=>{ return "Something else" },
                    nodes: function(){

                    }
                }
            }
        }
        wrapper.vm.updateTransformer()
    })
    test("addHost", ()=>{
        wrapper.vm.addHost()
        wrapper.vm.addHost(0,0,0,0,0,"test", "test_subnet", "test_group")
    })
})
