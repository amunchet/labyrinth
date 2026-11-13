<template>
  <b-row class="text-left">
    <b-col lg="5" class="mb-3">
      <b-card>
        <b-card-title>{{
          form._id ? "Edit " + form.name : "Add a UniFi controller"
        }}</b-card-title>
        <b-form @submit.prevent="save()">
          <b-form-group label="Name">
            <b-input v-model="form.name" placeholder="HQ console" />
          </b-form-group>
          <b-form-group
            label="URL"
            description="The console's address, e.g. https://192.168.1.1, or https://unifi.example.com:8443 for a self-hosted Network application"
          >
            <b-input v-model="form.url" placeholder="https://192.168.1.1" />
          </b-form-group>
          <b-form-group label="Sign in with">
            <b-form-radio-group v-model="form.auth" :options="auth_options" />
          </b-form-group>
          <b-form-group
            v-if="form.auth == 'api_key'"
            label="API key"
            :description="
              form.has_api_key ? 'Leave blank to keep the saved key.' : ''
            "
          >
            <b-input
              v-model="form.api_key"
              type="password"
              autocomplete="off"
            />
          </b-form-group>
          <template v-else>
            <b-form-group label="Username">
              <b-input v-model="form.username" autocomplete="off" />
            </b-form-group>
            <b-form-group
              label="Password"
              :description="
                form.has_password
                  ? 'Leave blank to keep the saved password.'
                  : ''
              "
            >
              <b-input
                v-model="form.password"
                type="password"
                autocomplete="new-password"
              />
            </b-form-group>
          </template>
          <b-form-checkbox v-model="form.protect"
            >Watch its Protect cameras</b-form-checkbox
          >
          <b-form-checkbox v-model="form.add_devices"
            >Add its devices and cameras to the inventory</b-form-checkbox
          >
          <b-form-checkbox v-model="form.verify_ssl"
            >Verify its TLS certificate</b-form-checkbox
          >
          <div v-if="form_problem" class="text-danger mt-2">
            {{ form_problem }}
          </div>
          <div class="mt-3">
            <b-button
              variant="primary"
              type="submit"
              :disabled="!!form_problem || saving"
              >{{ form._id ? "Save" : "Add" }}</b-button
            >
            <b-button v-if="form._id" class="ml-2" @click="resetForm()"
              >Cancel</b-button
            >
          </div>
        </b-form>
      </b-card>

      <b-card class="mt-3 help" title="Setting up">
        <p>
          <strong>API key</strong> (UniFi OS consoles: Dream Machine, Cloud
          Gateway, Dream Router, Cloud Key Gen2+, NVR): in UniFi Network, go to
          Settings → Control Plane → Integrations and create a key. It has the
          rights of the admin who creates it.
        </p>
        <p>
          <strong>Local account</strong> (also the self-hosted Network
          application): add a local admin with the View Only role under Admins
          &amp; Users. Use one if the device list answers "HTTP 401" to an API
          key: switch ports come from the Network application's own API, which
          not every version opens to keys.
        </p>
        <p class="mb-0">
          Map each UniFi site to a location: its devices and the clients seen
          there take that location unless they have their own, and switch ports
          suggest which rack a device is in. Offline devices and cameras are
          alerted through Alertmanager, with the usual notification backoff.
        </p>
      </b-card>
    </b-col>

    <b-col lg="7">
      <b-card title="Controllers">
        <b-alert v-if="!controllers.length" show variant="info"
          >No controllers yet.</b-alert
        >
        <div
          v-for="controller in controllers"
          :key="controller._id"
          class="controller mb-3"
        >
          <div class="d-flex flex-wrap align-items-center">
            <strong class="mr-2">{{ controller.name }}</strong>
            <small class="text-muted mr-auto"
              >{{ controller.url }} ·
              {{ controller.auth == "api_key" ? "API key" : "local account" }}
              <span v-if="controller.protect"> · Protect</span></small
            >
            <b-button size="sm" variant="link" @click="edit(controller)"
              >Edit</b-button
            >
            <b-button
              size="sm"
              variant="link"
              class="text-danger"
              @click="remove(controller)"
              >Delete</b-button
            >
          </div>
          <div
            v-if="!(sites[controller._id] || []).length"
            class="text-muted small"
          >
            Its sites appear here once it has been checked.
          </div>
          <table v-else class="table table-sm mb-1">
            <thead>
              <tr>
                <th>UniFi site</th>
                <th>Location</th>
                <th>Monitor</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="site in sites[controller._id]" :key="site.site">
                <td>{{ site.name }}</td>
                <td>
                  <b-select
                    v-model="site.location"
                    size="sm"
                    :options="location_options"
                  />
                </td>
                <td><b-form-checkbox v-model="site.monitor" /></td>
              </tr>
            </tbody>
          </table>
          <b-button
            v-if="(sites[controller._id] || []).length"
            size="sm"
            variant="outline-primary"
            @click="saveSites(controller)"
            >Save sites</b-button
          >
        </div>
      </b-card>
    </b-col>
  </b-row>
</template>
<script>
import Helper from "@/helper";

const emptyForm = () => ({
  _id: "",
  name: "",
  url: "",
  auth: "api_key",
  api_key: "",
  username: "",
  password: "",
  has_api_key: false,
  has_password: false,
  protect: false,
  add_devices: true,
  verify_ssl: false,
});

// UniFi controllers: their address and sign-in, and which Labyrinth location
// each of their sites is.  `status` (/unifi/) lists the sites each one has.
export default {
  name: "UnifiSettings",
  props: {
    status: { type: Object, required: true },
  },
  data() {
    return {
      controllers: [],
      locations: [],
      sites: {},
      form: emptyForm(),
      saving: false,
      auth_options: [
        { value: "api_key", text: "API key" },
        { value: "login", text: "Local account" },
      ],
    };
  },
  computed: {
    location_options() {
      return [{ value: "", text: "No location" }].concat(
        this.locations.map((x) => x.name)
      );
    },
    form_problem() {
      let form = this.form;
      if (!form.name.trim()) {
        return "Give it a name.";
      }
      if (!/^https?:\/\/[^/\s]+\/?$/.test(form.url.trim())) {
        return "The URL is just the address, like https://192.168.1.1";
      }
      if (form.auth == "api_key" && !form.api_key && !form.has_api_key) {
        return "Enter the API key.";
      }
      if (
        form.auth == "login" &&
        !(form.username && (form.password || form.has_password))
      ) {
        return "Enter the local account's username and password.";
      }
      return "";
    },
  },
  watch: {
    status() {
      this.buildSites();
    },
  },
  methods: {
    buildSites() {
      // The sites each controller reported, with their saved location and
      // whether they are monitored (new sites are)
      let sites = {};
      this.controllers.forEach((controller) => {
        let saved = {};
        (controller.sites || []).forEach((x) => (saved[x.site] = x));
        let found = this.status.controllers.find(
          (x) => x._id == controller._id
        );
        sites[controller._id] = ((found && found.sites) || []).map((x) => ({
          site: x.site,
          name: x.name,
          location: (saved[x.site] || {}).location || "",
          monitor: (saved[x.site] || {}).monitor !== false,
        }));
      });
      this.sites = sites;
    },
    resetForm() {
      this.form = emptyForm();
    },
    edit(controller) {
      this.form = {
        ...emptyForm(),
        ...controller,
        api_key: "",
        password: "",
      };
    },
    post: /* istanbul ignore next */ async function (data) {
      let formData = new FormData();
      formData.append("data", JSON.stringify(data));
      return Helper.apiPost("unifi/controller", "", "", this.$auth, formData);
    },
    save: /* istanbul ignore next */ async function () {
      this.saving = true;
      let data = { ...this.form };
      ["has_api_key", "has_password", "created", "updated", "name_key"].forEach(
        (x) => delete data[x]
      );
      if (!data._id) {
        delete data._id;
      }
      try {
        await this.post(data);
        this.resetForm();
        await this.load();
        this.$emit("changed");
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      this.saving = false;
    },
    saveSites: /* istanbul ignore next */ async function (controller) {
      try {
        await this.post({
          _id: controller._id,
          sites: this.sites[controller._id].map((x) => ({
            site: x.site,
            location: x.location,
            monitor: x.monitor,
          })),
        });
        await this.load();
        this.$emit("changed");
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    remove: /* istanbul ignore next */ async function (controller) {
      let ok = await this.$bvModal.msgBoxConfirm(
        "Delete " +
          controller.name +
          "? The hosts it added stay in the inventory."
      );
      if (!ok) {
        return;
      }
      try {
        await Helper.apiDelete("unifi/controller", controller._id, this.$auth);
        await this.load();
        this.$emit("changed");
      } catch (e) {
        this.$store.commit("updateError", e);
      }
    },
    load: /* istanbul ignore next */ async function () {
      try {
        this.controllers = await Helper.apiCall(
          "unifi/controllers",
          "",
          this.$auth
        );
        this.locations = await Helper.apiCall("locations", "", this.$auth);
      } catch (e) {
        this.$store.commit("updateError", e);
      }
      this.buildSites();
    },
  },
  mounted: /* istanbul ignore next */ function () {
    this.load();
  },
};
</script>
<style scoped>
.help {
  font-size: 0.85rem;
}
</style>
