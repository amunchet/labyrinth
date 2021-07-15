import Vue from "vue";
import Vuex from "vuex";

Vue.use(Vuex);

export default new Vuex.Store({
  state: {
      logged_in: false
  },
  mutations: {
      setLogin(state){
          state.logged_in = true
      }
  },
  actions: {},
  modules: {},
});
