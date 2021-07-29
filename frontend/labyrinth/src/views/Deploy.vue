<template>
  <b-container>
    <b-row>
      <b-col>
        <h4>Deployment Files</h4>
        These must be encrypted vault files. Select the ones you need (for
        example, you might be deploying without SSH keys)
        <hr />

        <b-row>
          <b-col> SSH Key </b-col> </b-row
        ><b-row>
          <b-col>
            <b-select
              v-if="files_list['ssh'] != undefined"
              v-model="selected['ssh']"
              :options="files_list['ssh']"
            />
          </b-col>
          <b-col>
            <b-form-file
              class="float-left"
              v-model="ssh_key_file"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file> </b-col
          ><b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left" @click="()=>{
              files_list['ssh'] = ''
              ssh_key_file = []
              }">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>

        <b-row>
          <b-col> Become Password </b-col> </b-row
        ><b-row>
          <b-col>
            <b-select
              v-if="files_list['become'] != undefined"
              :options="files_list['become']"
              v-model="selected['become']"
            />
          </b-col>
          <b-col>
            <b-form-file
              v-model="become_file"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left" @click="()=>{
                files_list['become'] = ''
                become_file = []
              }">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row>
          <b-col>
            <hr />
            Become password needs to be in the following format: <br />
            <code class="text-left">
              ---<br />
              ansible_user: "XXXXXX" <br />
              ansible_ssh_pass: "XXXXXXX"<br />
            </code>
          </b-col>
        </b-row>
        <hr />

        <b-row>
          <b-col> Other Ansible Files (optional) </b-col> </b-row
        ><b-row>
          <b-col>
            <b-select
              disabled
              v-if="files_list['other'] != undefined"
              :options="files_list['other']"
              v-model="selected['other']"
            />
          </b-col>
          <b-col>
            <b-form-file
              disabled
              v-model="other_file"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button variant="link" class="m-0 mt-2 p-0 float-left" @click="()=>{
                files_list['other'] = ''
                other_file = []
              }"
              disabled
              >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <hr />
        <div class="text-left">
          To create ansible vault files, use the following command:
          <code> ansible-vault create [FILENAME] </code><br />
          <i>New Vault Password: XXXXXXX</i>

          [Edit file]
        </div>
      </b-col>
      <b-col>
        <div class="overflow-hidden">
          <h2 v-if="!isTesting" class="float-left">Deploy</h2>
          <h2 class="float-left text-success" v-else>TESTING</h2>
          <div class="float-right mt-1">
            <b-button
              variant="success"
              v-if="!isTesting"
              @click="()=>{
                
                isTesting = !isTesting
                selected_host = sample_ip
                }"
              >Enter Test Mode</b-button
            >
            <b-button variant="primary" v-else @click="isTesting = !isTesting"
              >Enter Production Mode</b-button
            >
          </div>
        </div>
        <div class="mb-4 mt-2" v-if="!isTesting">
          Host: <b-select v-model="selected_host" :options="hosts" :enabled="isTesting"/>
        </div>
        <div v-else class="mb-4 mt-2">
          Host: <br /><b>sampleclient - ({{sample_ip}})</b> <br />Backend ip is {{ ip }}
        </div>
        <h5 class="mt-2">Ansible playbook</h5>
        <b-select
          class="mt-2 mb-2"
          v-if="files_list['ansible'] != undefined"
          :options="files_list['ansible']"
          v-model="selected_playbook"
        />
        <b-textarea
          v-model="playbook_contents"
          v-if="loadings.playbook == undefined || loadings.playbook == 0"
        />
        <div v-else class="mt-2 text-center">
          <b-spinner class="ml-auto mr-auto mt-4" />
        </div>
        <div class="overflow-hidden mt-2">
          <b-button
            variant="success"
            class="mb-2 float-right"
            @click="savePlaybook()"
            v-if="
              loadings.save_playbook == undefined || loadings.save_playbook == 0
            "
          >
            <font-awesome-icon icon="save" size="1x" />
          </b-button>
          <div class="mb-2 mt-2 float-right" v-else>
            <b-spinner />
          </div>
        </div>

        <div>
          Vault Password:
          <b-input type="password" v-model="vault_password" />
        </div>
        <hr />

        <b-button v-if="isTesting" variant="success" @click="runPlaybook()"
          >Deploy to sampleclient</b-button
        >
        <b-button v-else variant="primary" @click="runPlaybook()"
          >Deploy to hosts</b-button
        >
        <br />
        <div
          class="playbook_result"
          v-html="$sanitize(playbook_result)"
          v-if="playbook_result && playbook_loaded"
        ></div>
        <b-spinner class="m-2" v-if="!playbook_loaded" />
      </b-col>
    </b-row>
  </b-container>
</template>
<script>
import Helper from "@/helper";
import styles from "@/assets/variables.scss";
export default {
  name: "Deploy",
  data() {
    return {
      ssh_key_file: [],
      become_file: [],
      other_file: [],
      selected: {
        "ssh" : "",
        "become" : "",
        "other" : "",
      },

      ip: "",
      sample_ip: "",

      files_list: {},

      hosts: [],
      selected_host: "",

      vault_password: "",
      ansible_user: "",

      selected_playbook: "",
      playbook_contents: "",
      playbook_loaded: true,

      playbook_result: "",

      loadings: {},

      isTesting: false,
      options: [
        {
          text: "Test Mode",
          value: styles.green,
        },
      ],
    };
  },
  watch: {
    ssh_key_file: function (val) {
      this.uploadHelper(val, "ssh")
    },

    become_file: function(val){
      this.uploadHelper(val, "become")
    },
    other_file: function(val){
      this.uploadHelper(val, "other")
    },

    //TODO: Finish other uploads
    selected_playbook: function (val) {
      if (val != "") {
        this.loadPlaybook(val);
      }
    },
  },
  methods: {
    uploadHelper: /* istanbul ignore next */ function(val, type){
      if (val) {
        var auth = this.$auth;
        var formData = new FormData();
        formData.append("file", val)
        Helper.apiPost("upload", "/" + type, auth.accessToken, auth, formData, true)
          .then((res) => {
            //this.$store.commit("updateError", res);
            this.selected[type] = res
            this.loadFilesList(type)
          })
          .catch((e) => {
            if(("" + e).indexOf("521") != -1){
              this.$store.commit('updateError', "Error: Invalid file type uploaded.  Make sure your file is the correct type (Encrypted Ansible, Telegraf Conf, etc.)")
            }else{
              this.$store.commit("updateError", e);
            }
          });
      }
    },
    loadPlaybook: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      var loadings = this.loadings;
      this.loadings["playbook"] = 1;
      Helper.apiCall("get_ansible_file", this.selected_playbook, auth)
        .then((res) => {
          this.playbook_contents = res;
          delete loadings.playbook;
          this.$forceUpdate();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },

    savePlaybook: /* istanbul ignore next */ function () {
      this.loadings["save_playbook"] = 1;
      this.$forceUpdate();
      var auth = this.$auth;
      var formData = new FormData();
      formData.append("data", this.playbook_contents);
      Helper.apiPost(
        "save_ansible_file/",
        this.selected_playbook,
        "",
        auth,
        formData
      )
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadings["save_playbook"] = 0;
          this.loadPlaybook();
        })
        .catch((e) => {
          this.loadings["save_playbook"] = 0
          this.$forceUpdate()
          if (("" + e).indexOf("471") != -1){
            this.$store.commit("updateError", "Error: Invalid Ansible File.  Correct the file and save again." + e);
          }else{
            this.$store.commit("updateError", e);
          }
        });
    },

    /* istanbul ignore next */
    runPlaybook: function () {
      var auth = this.$auth;
      var formData = new FormData();
      var host = this.selected_host;

      this.playbook_loaded = false;
      var data = {
        hosts: host,
        playbook: this.selected_playbook.replace(".yml", ""),
        vault_password: this.vault_password,
        become_file: this.selected['become'].replace(".yml", ""),
        ssh_key: this.selected["ssh"]
      };
      formData.append("data", JSON.stringify(data));

      Helper.apiPost("ansible_runner", "", "", auth, formData)
        .then((res) => {
          this.playbook_result = res;
          this.playbook_loaded = true;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
          this.playbook_loaded = true;
        });
    },

    loadIP: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("find_ip", "", auth)
        .then((res) => {
          this.ip = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
      Helper.apiCall("find_ip", "sampleclient", auth)
        .then((res) => {
          this.sample_ip = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },

    loadFilesList: /* istanbul ignore next */ async function (type) {
      var auth = this.$auth;
      Helper.apiCall("uploads", type, auth)
        .then((res) => {
          this.files_list[type] = res;
          this.$forceUpdate();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadHosts: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("hosts", "", auth)
        .then((res) => {
          this.hosts = res.map(x=>{
            return{
              text: x.ip,
              value: x.ip
            }
          });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },

  mounted: /* istanbul ignore next */ async function () {
    try {
      await this.loadFilesList("ansible");
      this.loadFilesList("ssh");
      this.loadFilesList("become");
      this.loadFilesList("other");
      this.loadFilesList("telegraf");
      this.loadFilesList("totp");

      this.loadIP();

      this.loadHosts();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
@import "@/assets/variables.scss";

*::-webkit-scrollbar{
  height: 8px;
  width: 8px;
}
*::-webkit-scrollbar-track-piece{
  background: lightgrey;
}
*::-webkit-scrollbar-thumb{
  background: darkgrey;
}





.playbook_result {
  height: 400px;
  max-width: 500px;
  overflow-y: scroll;
  margin-top: 2rem;
  background-color: lightgrey;
  padding: 1rem;
}

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
.cursor {
  cursor: pointer;
}
.green {
  color: $green;
}
</style>
