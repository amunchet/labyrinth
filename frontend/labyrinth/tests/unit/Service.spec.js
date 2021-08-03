// TEMPLATE FILE - Copy this file
import { config, shallowMount } from '@vue/test-utils'

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from '@/store'
import Instance from "@/components/Service.vue";

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

let state
let auth
let wrapper
let created


beforeEach(() => {
    wrapper = shallowMount(Instance, {
        propsData: {
            "name": "test",
            "inp_data": "test",
            "arrayChild": "test",
            "parent": "test",
            "start_minimized": "test",
            "isParent": "test",
            "service_filter": "test",
            "depth": 1,
            "isWrite": true, //This describes if we can delete items


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
            'b-form-file'
        ]
    })
})

afterEach(() => {
    wrapper.destroy()
})

describe('Service.vue', () => {
    test('is a Vue instance', () => {
        expect(wrapper.isVueInstance).toBeTruthy()
    })

    test('Dummy test for add and parsed', ()=>{
        expect(wrapper.vm.add("item", "name", "parent")).toBe(undefined)
        expect(wrapper.vm.parsed('{"item": 1, "name": 2, "parent" : 3}')).toBe(undefined)
    })
    test("handle_child_delete", async ()=>{
        wrapper.vm.$data.parsed_data = ["a", "b", "c"]
        wrapper.vm.handle_child_delete(1)
        await wrapper.vm.$forceUpdate()
        expect(wrapper.vm.$data.parsed_data).toStrictEqual(["a", "c"])

        wrapper.vm.$data.parsed_data = {"a" : 1, "b" : 2, "c" : 3}
        await wrapper.vm.$forceUpdate()
        wrapper.vm.handle_child_delete("b")
        await wrapper.vm.$forceUpdate()

        expect(wrapper.vm.$data.parsed_data).toStrictEqual({"a": 1, "c" : 3})

    })
    test("determineClass", async ()=>{
        wrapper.vm.$data.parsed_data = [1,2,3]
        await wrapper.vm.$forceUpdate()
        expect(wrapper.vm.determineClass()).toBe("main array child")


        wrapper.vm.$data.parsed_data = {"test" : 1}
        await wrapper.vm.$forceUpdate()
        expect(wrapper.vm.determineClass()).toBe("main border")

        wrapper.vm.$data.parsed_data = "bc"
        expect(wrapper.vm.determineClass()).toBe("child")
    })
    test("watched variables", async () =>{
        wrapper.setProps({
            inp_data: "",
            start_minimized: true,
            service_filter: true 
        })
        await wrapper.vm.$forceUpdate()
        wrapper.setProps({
            inp_data: "TEST",
            start_minimized: false,
            service_filter: false
        })


        expect(wrapper.vm.$data.parsed_data).toBe("test")
        expect(wrapper.vm.$data.minimized).toBe(false)

        wrapper.setProps({
            start_minimized: true,
        })
        await wrapper.vm.$forceUpdate()
        expect(wrapper.vm.$data.minimized).toBe(true)

        wrapper.setProps({
            service_filter: "" 
        })
        await wrapper.vm.$forceUpdate()
        expect(wrapper.vm.$data.minimized).toBe(true)

        wrapper.setProps({
            service_filter: "ABC" 
        })
        await wrapper.vm.$forceUpdate()
        expect(wrapper.vm.$data.minimized).toBe(false)

    })

})
