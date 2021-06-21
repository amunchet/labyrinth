import Vue from 'vue'
import App from './App.vue'
import './registerServiceWorker'

Vue.config.productionTip = false


//Auth
import AuthPlugin from './plugins/auth'

import router from './router'

// Install the authentication plugin here
Vue.use(AuthPlugin)

new Vue({
  router,
  render: h => h(App)
}).$mount('#app')
