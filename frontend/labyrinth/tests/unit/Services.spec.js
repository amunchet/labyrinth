// TEMPLATE FILE - Copy this file
import { config, shallowMount } from '@vue/test-utils'

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from '@/store'
import Instance from "@/views/Services.vue";

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

config.mocks['$sanitize'] = (x) => x

config.mocks['loaded'] = true

let state
let auth
let wrapper
let created


beforeEach(() => {
    wrapper = shallowMount(Instance, {
        propsData: {
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
            'b-form-file'
        ]
    })
})

afterEach(() => {
    wrapper.destroy()
})

describe('Services.vue', () => {
    test('is a Vue instance', () => {
        expect(wrapper.isVueInstance).toBeTruthy()
    })

    test("forceGlobalTag - ensures global settings present in all configuration files", ()=>{

    })
    test("add - transfers a template data structure over to output file", ()=>{
        
    })
})
