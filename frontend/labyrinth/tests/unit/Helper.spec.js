// TEMPLATE FILE - Copy this file
import { config } from "@vue/test-utils";

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

describe("Helper", () => {
  test("formatDate", () => {
    expect(Helper.formatDate("2020-01-01")).toBe("2020-01-01");

    expect(Helper.formatDate("2020-01-01 00:00:00", true)).toBe("0:0:0")
  });
  test("getUrl", () => {
    expect(Helper.getURL()).toBe("/api/");
  });
});
