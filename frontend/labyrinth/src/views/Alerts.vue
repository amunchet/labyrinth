<template>
  <b-container>
    <b-tabs content-class="mt-3" lazy>
      <b-tab title="Settings" active class="text-left">
        <h4>Settings</h4>
        <ul>
          <li>Frequency of scans</li>
          <li>Grouping by hosts, services, summary, etc?</li>
          <li>Time until Metric is considered stale</li>
        </ul>
      </b-tab>
      <b-tab title="Alert Manager">
        <b-row class="m-2">
          <b-col>
            <div class="float-left">
              Default Username is <b>admin</b>.
            </div></b-col
          >
          <b-col>
            <b-button
              class="float-right"
              variant="success"
              @click="loadIframe()"
            >
              <font-awesome-icon icon="clipboard" size="1x" />&nbsp; Click to
              Copy Generated Password</b-button
            >
          </b-col>
        </b-row>
        <iframe :src="frame_url" />
      </b-tab>
      <b-tab title="AlertManager Configuration File" class="text-left">
        <i>alertmanager.yml</i>
        <b-button @click="load()" class="mb-2 float-right" variant="warning">
          Load File
        </b-button>
        <b-textarea v-if="file" class="shadow-none" v-model="file" />
        <b-spinner class="m-2 float-right" v-if="loading" />
        <b-button v-else-if="file" @click="save()" variant="success" class="mt-2 float-right">
          <font-awesome-icon icon="save" size="1x" />
        </b-button>
      </b-tab>
    </b-tabs>
  </b-container>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Alerts",
  data() {
    return {
      frame_url: "",
      navigator: "",
      file: "",
      loading: false,
    };
  },
  methods: {
    load: /* istanbul ignore next */ function(){
      var auth = this.$auth
      this.loading = true
      Helper.apiCall("alertmanager", "", auth).then(res=>{
        this.file = res
        this.loading = false
      }).catch(e=>{
        this.loading = false
        this.$store.commit('updateError', e)
      })
    },
    save: /* istanbul ignore next */ function(){
      var auth = this.$auth
      var formData = new FormData()
      formData.append("data", this.file)
      this.loading = true
      Helper.apiPost("alertmanager", "", "", auth, formData).then(res=>{
        this.load()
        this.$store.commit('updateError', res)
      }).catch(e=>{
        this.loading = false
        this.$store.commit('updateError', e)
      })
    },

    copyToClipboard: function (textToCopy) {
      // navigator clipboard api needs a secure context (https)
      if (navigator.clipboard && window.isSecureContext) {
        // navigator clipboard api method'
        return navigator.clipboard.writeText(textToCopy);
      } else {
        // text area method
        let textArea = document.createElement("textarea");
        textArea.value = textToCopy;
        // make the textarea out of viewport
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        return new Promise((res, rej) => {
          // here the magic happens
          document.execCommand("copy") ? res() : rej();
          textArea.remove();
        });
      }
    },
    loadIframe: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("alertmanager", "pass", auth)
        .then((res) => {
              this.copyToClipboard(res)
              this.$store.commit("updateError", "Password copied to clipboard");
              this.frame_url = Helper.getURL().replace("api", "alertmanager");
              this.$forceUpdate();
            })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: function () {
    this.navigator = navigator;
    console.log(this.navigator);
  },
};
</script>
<style lang="scss" scoped>
iframe {
  width: 100%;
  min-height: 500px;
  overflow-y: scroll;
}
textarea{
  height: 400px;
  overflow-y: scroll;
}
</style>
