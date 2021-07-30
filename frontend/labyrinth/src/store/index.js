import Vue from "vue";
import Vuex from "vuex";

Vue.use(Vuex);

export default new Vuex.Store({
  state: {
    error: "",
    error_response: "",
    full_error: "",

    logged_in: false,
  },
  mutations: {
    setLogin(state) {
      state.logged_in = true;
    },
    updateError(state, msg) {
      // General Application: Displays the error message
      state.full_error = msg;

      if (msg.response) {
        state.error_response = msg.response;
      }
      if (msg.error_description) {
        state.error = msg.error_description;
      } else if (msg.status) {
        state.error = msg.status;
      } else if (msg.error) {
        state.error = msg.error;
      } else {
        state.error = msg;
      }

      state.error = "[" + new Date().getTime() + "] " + state.error;

      if (
        (state.error.indexOf("401") != -1 &&
          state.error.indexOf("ogin") == -1) ||
        (state.error_response + "" == "401" &&
          state.error.indexOf("ogin") == -1)
      ) {
        state.error = state.error + ".  Please login again.";
      }
    },
  },
  actions: {},
  modules: {},
});
