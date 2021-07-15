<!-- src/components/Callback.vue -->

<template>
  <div>
    <p>Loading...</p>
  </div>
</template>

<script>
export default {
  methods: {
    handleLoginEvent() {
      //console.log(data);
      /* istanbul ignore next */
      this.$router.push("/");
    },
  },
  created() {
    try {
      this.$auth.handleAuthentication();
      this.$store.commit("setLogin")
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  mounted() {},
};
</script>
