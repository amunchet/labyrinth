<template>
  <div id="app">
    <div>
      <b-navbar toggleable="lg" type="light" class="pb-0 pt-0">
        <b-navbar-brand href="#" class="top_logo">
          <img src="/logo.png" alt="Labyrinth logo" />
        </b-navbar-brand>

        <b-navbar-toggle target="nav-collapse"></b-navbar-toggle>

        <b-collapse id="nav-collapse" class="pt-2" is-nav>
          <b-navbar-nav>
            <b-nav-item href="#">
              <router-link to="/">
                <font-awesome-icon icon="home" size="1x" />
              </router-link>
            </b-nav-item>
            <b-nav-item href="/dashboard">
              <router-link to="/dashboard">Dashboard</router-link>
            </b-nav-item>
            
            <b-nav-item href="/dashboard">
              <router-link to="/dashboard">Checks</router-link>
            </b-nav-item>
          </b-navbar-nav>

          <!-- Right aligned nav items -->
          <b-navbar-nav class="ml-auto">
            <b-navbar-nav>

              <b-nav-item href="/settings">
                <router-link to="/settings">Scan</router-link>
              </b-nav-item>
              <b-nav-item href="/services">
                <router-link to="/services">Metrics</router-link>
              </b-nav-item>
              <b-nav-item href="/deploy">
                <router-link to="/deploy">Deploy</router-link>
              </b-nav-item>
                <b-nav-item href="/deploy">
                <router-link to="/deploy">Alerts</router-link>
              </b-nav-item>
            </b-navbar-nav>

            <b-nav-item-dropdown right class="ml-3">
              <!-- Using 'button-content' slot -->
              <template #button-content>
                <b-avatar
                  v-if="$auth.profile"
                  variant="info"
                  size="2rem"
                  :src="$auth.profile.picture"
                >
                </b-avatar>
                <b-avatar size="2rem" v-else></b-avatar>
              </template>
              <b-dropdown-item
                href="#"
                @click="$auth.login()"
                v-if="$auth.profile == null"
                >Sign In</b-dropdown-item
              >
              <b-dropdown-item v-else href="#" @click="$auth.logOut()"
                >Sign Out</b-dropdown-item
              >
            </b-nav-item-dropdown>
          </b-navbar-nav>
        </b-collapse>
      </b-navbar>
    </div>
    <hr class="m-2" />
    <br />
    <router-view />
  </div>
</template>
<script>
import Helper from "@/helper";
export default {
  data() {
    return {};
  },
  methods: {
    checkErrorMessage: function () {
      var msg = "";
      try {
        msg = JSON.stringify(this.$store.state.error);
      } catch (e) {
        /* istanbul ignore next */
        msg = this.$store.state.error;
      }
      if (msg.indexOf("rror") != -1) {
        return "danger";
      } else {
        /*istanbul ignore next */
        return "success";
      }
    },
  },
  watch: {
    "$store.state.error": function (val, prev) {
      //window.scrollTo(0, 0)
      if (val != undefined) {
        var parsed_val = ("" + val).replace(/\[.*\]/, "");
        if (parsed_val != undefined && parsed_val != "" && parsed_val != " ") {
          if (parsed_val.indexOf("401") != -1) {
            parsed_val = "Error: Logged out.  Please login again.";
          }

          if (this.$bvToast != undefined && prev.indexOf(val) == -1) {
            this.$bvToast.toast(
              parsed_val.charAt(0).toUpperCase() + parsed_val.slice(1),
              {
                title: `Notice`,
                variant: this.checkErrorMessage(),
                solid: true,
                toaster: "b-toaster-bottom-right",
              }
            );
          }
          this.$store.state.error = parsed_val;
          this.countDown = 10;
        }
      }
    },
  },
  created: function () {
    var auth = this.$auth;

    var current_page = this.$route.query.page;
    auth.handleAuthentication();
    if (current_page == undefined || current_page.indexOf("callback") == -1) {
      try {
        Helper.apiCall("secure", "", auth)
          .then((res) => {
            this.sandbox = ("" + res).toLowerCase() == "true";
          })
          .catch((e) => {
            var output = "" + e;
            var page = this.$route.query.page;

            if (
              output.indexOf("401") != -1 &&
              (page == undefined || page.indexOf("callback") == -1)
            ) {
              //this.$auth.login();
            } else {
              this.$store.commit("updateError", e);
            }
          });
      } catch (e) {
        console.log(this.$auth);
        console.log(e);
        //this.$auth.login();
        this.$auth.handleAuthentication();
      }
    }
  },
};
</script>

<style lang="scss">
@import "@/assets/variables.scss";

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
}

#nav {
  padding: 30px;

  a {
    font-weight: bold;
    color: #2c3e50;

    &.router-link-exact-active {
      color: #42b983;
    }
  }
}

.router-link-active{
    color: $darkblue;
    font-weight: bold;
}

.top_logo {
  position: absolute;
  left: 20px;
  top: 1px;
}
.top_logo img {
  height: 50px;
}
#nav-collapse {
  margin-left: 75px;
}
</style>
