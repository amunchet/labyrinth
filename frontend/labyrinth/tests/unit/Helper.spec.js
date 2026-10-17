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

    expect(Helper.formatDate("2020-01-01 00:00:00", true)).toBe("0:0:0");
  });
  test("formatUTC reads metric timestamps as UTC", () => {
    // 2026-10-15 16:44:03 UTC, rendered in whatever zone the test runs in
    const epoch = Date.UTC(2026, 9, 15, 16, 44, 3) / 1000;
    const when = new Date(epoch * 1000);
    const expected =
      Helper.formatDate(when) + " " + Helper.formatDate(when, true);

    expect(Helper.formatUTC("2026-10-15 16:44:03")).toBe(expected);
    expect(Helper.formatUTC("2026-10-15 16:44:03.123456")).toBe(expected);
    expect(Helper.formatUTC("2026-10-15T16:44:03+00:00")).toBe(expected);
    expect(Helper.formatUTC(epoch)).toBe(expected);
    expect(Helper.formatUTC(null)).toBe("");
    expect(Helper.formatUTC("")).toBe("");
  });
  test("getUrl", () => {
    expect(Helper.getURL()).toBe("/api/");
  });

  test("validateIP", () => {
    expect(Helper.validateIP("192.168.0.1")).toBeTruthy();
    expect(Helper.validateIP("254.254.254.254")).toBeTruthy();

    expect(Helper.validateIP("255.254.254.254")).not.toBeTruthy();
    expect(Helper.validateIP("192.0.1")).not.toBeTruthy();
    expect(Helper.validateIP("asdfasdfsa")).not.toBeTruthy();
    expect(Helper.validateIP("192.168.0.123asdfasdf")).not.toBeTruthy();
  });
  test("capitalize", () => {
    expect(Helper.capitalize("addd")).toBe("Addd");
  });
  test("listColors", () => {
    const colors = Helper.listColors();
    expect(Array.isArray(colors)).toBe(true);
    expect(colors.length).toBeGreaterThan(0);
    expect(colors).toContain("darkblue");
    expect(colors).toContain("red");
  });
});
