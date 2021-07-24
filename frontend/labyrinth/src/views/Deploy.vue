<template>
  <b-container>
    <b-row>
      <b-col>
        <h4>Deployment Files</h4>
        These must be encrypted vault files.  Select the ones you need (for example, you might be deploying without SSH keys)
        <hr />

        <b-row>
          <b-col > SSH Key </b-col>
        </b-row><b-row>
          <b-col>
            <b-select disabled v-if="files_list['ssh'] != undefined" :options="files_list['ssh']" />
          </b-col>
          <b-col>
            <b-form-file
              disabled
              class="float-left"
              v-model="ssh_key_file"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file> </b-col
          ><b-col cols="1">
            <b-button disabled variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row >
          <b-col> TOTP Key </b-col>
        </b-row><b-row>
          <b-col>
            <b-select  v-if="files_list['totp'] != undefined" :options="files_list['totp']" disabled />
          </b-col>
          <b-col>
            <b-form-file
              disabled
              v-model="file1"
              placeholder="..."
              drop-placeholder="Drop here..."
            ></b-form-file>
          </b-col>
          <b-col cols="1">
            <b-button disabled variant="link" class="m-0 mt-2 p-0 float-left">
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </b-col>
        </b-row>
        <b-row>
          <b-col> Become Password </b-col>
        </b-row><b-row>
          <b-col>
            <b-select  v-if="files_list['become'] != undefined" :options="files_list['become']" />
          </b-col>
          <b-col >
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
          <b-col>
          <hr />
          Become password needs to be in the following format: <br />
          <code class="text-left">
            ---<br />
            ansible_ssh_pass: "XXXXXXX"
          </code>
          </b-col>
        </b-row>
        <hr />
        <b-row>
          <b-col> Telegraf conf file </b-col>
        </b-row><b-row>
          <b-col>
            <b-select
              v-if="files_list['telegraf'] != undefined" :options="files_list['telegraf']"
            />
          </b-col>
          <b-col >
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
        </b-row><b-row>
          <b-col>
            <b-select 
            v-if="files_list['other'] != undefined" :options="files_list['other']"
            />
          </b-col>
          <b-col>
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
          <code>
          ansible-vault create [FILENAME]
          </code><br />
          <i>New Vault Password: XXXXXXX</i>
          
          [Edit file]
        </div>
      </b-col>
      <b-col>
        <div class="overflow-hidden">
        <h2 v-if="!isTesting" class="float-left">Deploy
        </h2>
        <h2 class="float-left text-success" v-else>TESTING</h2>
        <div class="float-right mt-1">
          <b-button variant="success" v-if="!isTesting" @click="isTesting = !isTesting">Enter Test Mode</b-button>
          <b-button variant="primary" v-else @click="isTesting = !isTesting">Enter Production Mode</b-button>
        </div>
        </div>
        <div class="mb-4 mt-2" v-if='!isTesting'>
        Host: <b-select :options="hosts" />
        </div>
        <div v-else class='mb-4 mt-2'>
          Host: <br /><b>sampleclient</b>
        </div>
        <h5 class="mt-2">Ansible playbook</h5>
        <b-select class="mt-2 mb-2" v-if="files_list['ansible'] != undefined" :options="files_list['ansible']" v-model="selected_playbook" />
        <textarea v-model="playbook_contents" v-if="loadings.playbook == undefined || loadings.playbook == 0"/>
        <div v-else class="text-center">
          <b-spinner class="ml-auto mr-auto mt-4" /></div>
        <div class="overflow-hidden">
        <b-button variant="success" class="mb-2 float-right" @click="savePlaybook()" v-if="loadings.save_playbook == undefined || loadings.save_playbook == 0">
          <font-awesome-icon icon="save" size="1x" />
        </b-button>
        <div class="mb-2 float-right" v-else>
          <b-spinner />
        </div>
        </div>
        <div>
        Password:
        <b-input type="password" />
        </div>
        <hr />

        <b-button v-if="isTesting" variant="success">Deploy to sampleclient</b-button>
        <b-button v-else variant="primary">Deploy to hosts</b-button>
        <br />
      </b-col>
    </b-row>
  </b-container>
</template>
<script>
import Helper from "@/helper";
import styles from "@/assets/variables.scss";
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

    //TODO: Finish other uploads
    selected_playbook: function(val){
      if(val != ""){
        this.loadPlaybook(val)
      }
    }


  },
  methods: {
    loadPlaybook: function(){
      var auth = this.$auth
      var loadings = this.loadings
      this.loadings["playbook"] = 1
      Helper.apiCall("get_ansible_file", this.selected_playbook, auth).then(res=>{
        this.playbook_contents = res
        delete loadings.playbook 
        this.$forceUpdate()
        console.log("loadged")
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    savePlaybook: /* istanbul ignore next */ function(){
      var auth = this.$auth
      var formData = new FormData()
      formData.append("data", this.playbook_contents)
      this.loadings["save_playbook"] = 1
      Helper.apiPost("save_ansible_file/", this.selected_playbook, "", auth, formData).then(res=>{
        this.$store.commit('updateError', res)
        this.loadings["save_playbook"] = 0
        this.loadPlaybook()
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    loadFilesList: /* istanbul ignore next */ async function (type) {
      var auth = this.$auth;
      Helper.apiCall("uploads", type, auth)
        .then((res) => {
          this.files_list[type]= res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadHosts: /* istanbul ignore next */ function(){
      var auth = this.$auth
      Helper.apiCall("hosts", "", auth).then(res=>{
        this.hosts = res
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    }
  },
  data() {
    return {
      file1: "",
      ssh_key_file: "",
      files_list: {},
      hosts: [],
      selected_playbook: "",
      playbook_contents: "",

      loadings: {},

      isTesting: false,
      options:[
        {
          text: "Test Mode",
          value: styles.green,
        }
      ]
    };
  },
  mounted: /* istanbul ignore next */ async function () {
    try {

      await this.loadFilesList("ansible");
      this.loadFilesList("ssh");
      this.loadFilesList("become");
      this.loadFilesList("other");
      this.loadFilesList("telegraf");
      this.loadFilesList("totp");
      
      
      this.loadHosts()
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
@import "@/assets/variables.scss";
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
.cursor{
  cursor: pointer;
}
.green{
  color: $green;
}

</style>
