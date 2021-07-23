<template>
  <b-container>
    <b-row>
      <b-col>
        <h4>Deployment Files</h4>
        All of these must be encrypted vault files.
        <hr />

        <b-row>
          <b-col> SSH Key </b-col>
          <b-col>
            <b-select :options="ssh_key_files" />
          </b-col>
          <b-col cols="4">
            <b-form-file
              class="float-left"
              v-model="ssh_key_file"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file> </b-col
          ><b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row>
          <b-col> TOTP Key </b-col>
          <b-col>
            <b-select />
          </b-col>
          <b-col cols="4">
            <b-form-file
              v-model="file1"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row>
          <b-col> Become Password </b-col>
          <b-col>
            <b-select />
          </b-col>
          <b-col cols="4">
            <b-form-file
              v-model="file1"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row>
          <b-col> Telegraf conf file </b-col>
          <b-col>
            <b-select />
          </b-col>
          <b-col cols="4">
            <b-form-file
              v-model="file1"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row>
          <b-col> Ansible Files (optional) </b-col>
          <b-col>
            <b-select />
          </b-col>
          <b-col cols="4">
            <b-form-file
              v-model="file1"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row>
          <b-col> Other Ansible Files (optional) </b-col>
          <b-col>
            <b-select />
          </b-col>
          <b-col cols="4">
            <b-form-file
              v-model="file1"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <hr />
        <div class="text-left">
          Telegraf deployment is interesting, because there are some non x64
          machines here. FreeBSD, old arm processors, etc.
        </div>
        <hr />
        <div class="text-left">
          To create ansible vault files, use the following command: 
          ```
          ansible-vault create [FILENAME]
          ```
          New Vault Password: XXXXXXX
          
          [Edit file]
        </div>
      </b-col>
      <b-col>
        <h2>Deploy</h2>
        Host: <b-select />
        <h5 class="mt-2 mb-2">Ansible playbook</h5>
        Validating playbook...
        <textarea /><br />

        Password:
        <b-input type="password" />
        <hr />
        <b-button variant="success">Deploy</b-button>
        <br />
        Test deployment in docker...
      </b-col>
    </b-row>
  </b-container>
</template>
<script>
import Helper from "@/helper";
export default {
  name: "Deploy",
  watch: {
    ssh_key_file: function (val) {
      if (val != "") {
        var auth = this.$auth;
        var formData = new FormData();
        formData.append("file", this.ssh_key_file);
        Helper.apiPost("upload", "/ssh", auth.accessToken, auth, formData, true)
          .then((res) => {
            this.$store.commit("updateError", res);
          })
          .catch((e) => {
            this.$store.commit("updateError", e);
          });
      }
    },
  },
  methods: {
    load_ssh_keys: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("uploads", "ssh", auth)
        .then((res) => {
          this.ssh_key_files = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  data() {
    return {
      ssh_key_file: "",
      ssh_key_files: [],
    };
  },
  mounted: /* istanbul ignore next */ function () {
    try {
      this.load_ssh_keys();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
textarea {
  width: 100%;
  min-height: 400px;
}
.row {
  margin-top: 1rem;
  margin-bottom: 1rem;
}
.col {
  text-align: left;
  margin-left: 2rem;
}
</style>
