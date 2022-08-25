<template>
  <b-container class="mt-3">
    <b-tabs content-class="mt-3" lazy>
      <b-tab title="Active Alerts" active class="text-left">
        <p>List of active alerts.</p>
        <div v-if="active_alerts_loading">
          <b-spinner class="m-2" />
        </div>
        <b-table
          striped
          style="max-width: 100%"
          :items="active_alerts"
          v-else
          :fields="['resolve', 'labels', 'annotations', 'receivers', 'time']"
        >
          <template v-slot:cell(resolve)="item">
            <b-button variant="primary" @click="resolveAlert(item.item)">
              <font-awesome-icon icon="check" size="1x" />
            </b-button>
          </template>
          <template v-slot:cell(labels)="item">
            <b-row v-for="(j, idx) in item.item.labels" v-bind:key="idx">
              <b-col class="text-left border">
                {{ idx }}
              </b-col>
              <b-col class="text-left border">
                {{ j }}
              </b-col>
            </b-row>
          </template>
          <template v-slot:cell(time)="item">
            Started: {{ item.item.startsAt }} <br />
            Ends at: {{ item.item.endsAt }} <br />
            Updated: {{ item.item.updatedAt }}
          </template>
        </b-table>
      </b-tab>
      <b-tab title="Settings" class="text-left">
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
        <b-button @click="load()" class="mb-2 float-right" variant="primary">
          Load AlertManager Configuration
        </b-button>
        <b-textarea v-if="file" class="shadow-none" v-model="file" />
        <b-spinner class="m-2 float-right" v-if="loading" />
        <div v-else-if="file">
          <b-button @click="save()" variant="success" class="mt-2 float-right">
            <font-awesome-icon icon="save" size="1x" />
          </b-button>
        </div>
        <br /><br />
        <hr />
        <h5>Example alertmanager.yml file</h5>
        <b-textarea v-model="sample_alertmanager" disabled />
        <codemirror
          ref="code_mirror"
          style="background-color: #e9ecef;"
          disabled
          :value="sample_alertmanager"
          :options="{
            'tabSize' : 4,
            'mode' : 'text/x-yaml',
            'theme' : 'base16-dark',
            'lineNumbers' : true,
            'line' : true,
            'readOnly' : true
          }"
          @ready="() => {}"
          @focus="() => {}"
          @input="() => {}"
        >
        </codemirror>
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
      active_alerts: [],
      active_alerts_loading: false,

      sample_loading: false,
      sample_alertmanager: "",
    };
  },
  methods: {
    resolveAlert: /* istanbul ignore next */ function (val) {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", JSON.stringify(val));
      Helper.apiPost("alertmanager", "", "alert", auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadAlerts();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadAlerts: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      this.active_alerts_loading = true;
      Helper.apiCall("alertmanager", "alerts", auth)
        .then((res) => {
          this.active_alerts = res;
          this.active_alerts_loading = false;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    restartAlertManager: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("alertmanager", "restart", auth)
        .then((res) => {
          this.$store.commit("updateError", res);
        })
        .catch((e) => {
          this.$store.commit("updateError", "Error: " + e.data);
        });
    },
    load: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      this.loading = true;
      Helper.apiCall("alertmanager", "", auth)
        .then((res) => {
          this.file = res;
          this.loading = false;
        })
        .catch((e) => {
          this.loading = false;
          this.$store.commit("updateError", e);
        });
    },
    loadSample: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      this.sample_loading = true;
      Helper.apiCall("alertmanager", "alertmanager.sample", auth)
        .then((res) => {
          this.sample_alertmanager = res;
          this.sample_loading = false;
        })
        .catch((e) => {
          this.sample_loading = false;
          this.$store.commit("updateError", e);
        });
    },

    save: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", this.file);
      this.loading = true;
      Helper.apiPost("alertmanager", "", "", auth, formData)
        .then((res) => {
          this.load();
          this.restartAlertManager();
          this.$store.commit("updateError", res);
        })
        .catch((e) => {
          this.loading = false;
          this.$store.commit("updateError", e);
        });
    },

    copyToClipboard: /* istanbul ignore next */ function (textToCopy) {
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
          this.copyToClipboard(res);
          this.$store.commit("updateError", "Password copied to clipboard");
          this.frame_url = Helper.getURL().replace("api", "alertmanager");
          this.$forceUpdate();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.navigator = navigator;
    try {
      this.loadAlerts();
      this.loadSample();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
iframe {
  width: 100%;
  min-height: 500px;
  overflow-y: scroll;
}
textarea {
  height: 400px;
  overflow-y: scroll;
}
.col.border {
  width: 50%;
  overflow: hidden;
  text-transform: capitalize;
}
</style>
