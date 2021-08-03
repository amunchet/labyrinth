<!-- src/components/Callback.vue -->

<template>
  <div>
    <p>Loading...</p>
  </div>
</template>

<script>
export default {
  methods: {
    handleLoginEvent() /* istanbul ignore next */ {
      //console.log(data);
      this.$router.push("/");
    },
  },
  created() /* istanbul ignore next */ {
    try {
      this.$auth.handleAuthentication();
      this.$store.commit("setLogin");
      this.$forceUpdate();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
  mounted() {},
};
</script>
