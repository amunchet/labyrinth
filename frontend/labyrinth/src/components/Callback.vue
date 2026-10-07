<!-- src/components/Callback.vue -->

<template>
  <div></div>
</template>

<script>
export default {
  methods: {
    handleLoginEvent() /* istanbul ignore next */ {
      const target = sessionStorage.getItem("loginReturnTo") || "/";
      sessionStorage.removeItem("loginReturnTo");
      window.location.href =
        window.location.origin +
        target +
        (target.includes("?") ? "&" : "?") +
        "callback=1&date=" +
        Date.now();
    },
  },
  created: async function () {
    try {
      await this.$auth.handleAuthentication();
    } catch (e) {
      console.log(e);
    }
  },
  mounted() {},
};
</script>
