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
      console.log(state)
      console.log(msg)
      state.full_error = msg;

      var temp = ""
      if (msg.response) {
        state.error_response = msg.response;
      }
      if (msg.error_description) {
        temp += msg.error_description + " ";
      } 
      if (msg.error) {
        temp += msg.error + " ";
      } 
      
      if(msg.status){
        if(msg.status != 200){
          temp = "Error " + temp
        }
        temp += msg.status + ": "
      }

      if (msg.data){
        temp += msg.data
      }
      console.log(temp)
      state.error = temp

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
