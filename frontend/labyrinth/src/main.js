import "@babel/polyfill";
import "mutationobserver-shim";
import Vue from "vue";
import "./plugins/fontawesome";
import App from "./App.vue";
import "./registerServiceWorker";
import router from "./router";
import store from "./store";

import vSelect from "vue-select";

Vue.config.productionTip = false;

//Sanitize

import sanitizeHTML from "sanitize-html";
Vue.prototype.$sanitize = sanitizeHTML;

//Bootstrap Vue
import { BootstrapVue, IconsPlugin } from "bootstrap-vue";

// Import Bootstrap an BootstrapVue CSS files (order is important)
import "bootstrap/dist/css/bootstrap.css";
import "bootstrap-vue/dist/bootstrap-vue.css";
// Make BootstrapVue available throughout your project
Vue.use(BootstrapVue);
// Optionally install the BootstrapVue icon components plugin
Vue.use(IconsPlugin);

//Auth
import AuthPlugin from "./plugins/auth";
// Install the authentication plugin here
Vue.use(AuthPlugin);

// Vuelidate
import Vuelidate from "vuelidate";
Vue.use(Vuelidate);

// Konva
import VueKonva from "vue-konva";
Vue.use(VueKonva);

import VueCodemirror from "vue-codemirror";

// require styles
import "codemirror/lib/codemirror.css";
import "codemirror/theme/base16-light.css";

// require more codemirror resource...

// you can set default global options and events when use
Vue.use(
  VueCodemirror /* { 
  options: { theme: 'base16-dark', ... },
  events: ['scroll', ...]
} */
);
import "vue-select/dist/vue-select.css";
Vue.component("v-select", vSelect);

new Vue({
  router,
  store,
  render: (h) => h(App),
}).$mount("#app");
