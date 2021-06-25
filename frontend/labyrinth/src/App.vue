<template>
  <div id="app">
    <div id="nav" v-if="false">
      <button @click="logOut">Log Out</button>
      <br /><br />
      <button @click="$auth.login()">Log In</button>
    </div>
    <span v-if="false">{{ $auth }}</span>
    <div id="nav" v-if="false">
      <router-link to="/">Home</router-link> |
      <router-link to="/about">About</router-link>
    </div>
    <router-view />
  </div>
</template>
<script>
export default {
  created() {
    try {
      this.$auth.handleAuthentication();
    } catch (e) {
      console.log("Authentication failed");
      console.log(e);
    }
  },
  methods: {
    logOut: function () {
      this.$auth.logOut();
      this.$router.push("/callback");
    },
  },
};
</script>
<style lang="scss">
@import '@/assets/variables.scss';

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
}

#nav {
  padding: 30px;
}

#nav a {
  font-weight: bold;
  color: #2c3e50;
}

#nav a.router-link-exact-active {
  color: #42b983;
}
</style>
