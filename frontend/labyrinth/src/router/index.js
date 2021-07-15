import Vue from "vue";
import VueRouter from "vue-router";
import Home from "../views/Home.vue";
import Callback from '@/components/Callback'

Vue.use(VueRouter);

const routes = [
  {
    path: "/",
    name: "Home",
    component: Home,
  },
{
    path: "/callback",
    name: "Callback",
    component: Callback,
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    // route level code-splitting
    // this generates a separate chunk (dashboard.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () =>
      import(/* webpackChunkName: "dashboard" */ "../views/Dashboard.vue"),
  },
{
    path: "/settings",
    name: "Settings",
    // route level code-splitting
    // this generates a separate chunk (settings.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () =>
      import(/* webpackChunkName: "settings" */ "../views/Settings.vue"),
  },
];

const router = new VueRouter({
  mode: "history",
  base: process.env.BASE_URL,
  routes,
});

export default router;
