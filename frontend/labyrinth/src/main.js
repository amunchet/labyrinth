import "@babel/polyfill";
import "mutationobserver-shim";
import Vue from "vue";
import "./plugins/fontawesome";
import "./plugins/bootstrap-vue";
import App from "./App.vue";
import "./registerServiceWorker";
import router from "./router";
import store from "./store";

Vue.config.productionTip = false;


//Auth
import AuthPlugin from './plugins/auth'
// Install the authentication plugin here
Vue.use(AuthPlugin)

new Vue({
  router,
  store,
  render: (h) => h(App),
}).$mount("#app");
