<template>
  <div class="home">
    <div v-if="$auth.profile == null || $auth.profile == undefined">
      <h4>Please login to continue.</h4>
      <b-button @click="$auth.login()" variant="success">Login</b-button>
    </div>
    <div v-else>
      <b-avatar class="mb-2" :src="$auth.profile.picture" size="5rem" />
      <h4>Welcome, {{ $auth.profile.name }}</h4>
    </div>
    <hr />
    <CustomDashboardsView />
    <br />
  </div>
</template>

<script>
// @ is an alias to /src
import CustomDashboardsView from '@/components/CustomDashboardsView'

export default {
  name: "Home",
  components: {
    CustomDashboardsView
  },
};
</script>
