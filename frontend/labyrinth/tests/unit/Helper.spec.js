// TEMPLATE FILE - Copy this file
import { config, shallowMount } from "@vue/test-utils";

//import { render } from '@vue/server-test-utils'

import Vue from "vue";
import store from "@/store";
import Helper from "@/helper";

Vue.use(store);

config.mocks["$auth"] = {
  profile: {
    name: "Test Name",
    picture: "Test.jpg",
  },
  idToken: 1,
  login: function () {},
  getAccessToken: function () {},
};

config.mocks["loaded"] = true;

let state;
let auth;
let wrapper;
let created;

describe("Helper", () => {
  test("formatDate", () => {
    expect(Helper.formatDate("2020-01-01")).toBe("2020-01-01");
  });
  test("getUrl", () => {
    expect(Helper.getURL()).toBe("/api/");
  });
});
