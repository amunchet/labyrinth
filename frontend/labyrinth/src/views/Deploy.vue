<template>
  <b-container>
    <b-modal
      id="add_vault"
      title="Add Vault File"
      size="xl"
      @ok="saveAnsibleVault"
    >
      <b-row class="text-left">
        <b-col>
          To create ansible vault files, use the following command:
          <code> ansible-vault create [FILENAME] </code><br />
          <i>New Vault Password: XXXXXXX</i>
          <br />
          [Edit file]
        </b-col>
      </b-row>

      <hr />
      <b-row>
        <b-col class="border-right">
          <h4>Upload Ansible Vault File</h4>
          <b-row
            ><b-col>
              Become password needs to be in the following format: <br />
              <code class="text-left">
                ---<br />
                ansible_user: "XXXXXX" <br />
                ansible_ssh_pass: "XXXXXXX"<br />
                ansible_become_password: "XXXXXXX" </code
              ><br />
              <i># If SSH key is used - .yml is added automatically</i><br />
              <code class="text-left">
                ssh_key_file: /src/uploads/ssh/XXXXXX.yml<br />
                ssh_key_pass: XXXXXXX
              </code>
            </b-col>
          </b-row>
          <b-row>
            <b-col>
              Upload Become File:
              <b-form-file
                v-model="become_file"
                placeholder="..."
                drop-placeholder="Drop here..."
              ></b-form-file>
              <b-col cols="1">
                <b-button
                  variant="link"
                  class="m-0 mt-2 p-0 float-left"
                  @click="
                    () => {
                      files_list['become'] = '';
                      become_file = [];
                    }
                  "
                >
                  <font-awesome-icon icon="times" size="1x" />
                </b-button>
              </b-col>
            </b-col>
          </b-row>
          <hr />
          <h4>Upload SSH Key</h4>
          <b-row>
            <b-col>
              SSH Key - must have a passphrase
              <!--
          <b-col cols="3" class="text-center">
            <b-button
              class=""
              variant="warning"
              @click="
                () => {
                  generated_ansible = { type: 'SSH Key' };
                  generated_vault_file = '';
                  $bvModal.show('add_vault');
                }
              "
            >
              <font-awesome-icon icon="plus" size="1x" />
            </b-button>
          </b-col>
          -->
              <b-form-file
                class="float-left"
                v-model="ssh_key_file"
                placeholder="..."
                drop-placeholder="Drop here..."
              ></b-form-file>
              <br />
              <b-button
                variant="link"
                class="m-0 mt-2 p-0 float-left"
                @click="
                  () => {
                    files_list['ssh'] = '';
                    ssh_key_file = [];
                  }
                "
              >
                <font-awesome-icon icon="times" size="1x" />
              </b-button>
            </b-col>
          </b-row>
        </b-col>
        <b-col>
          <h4>Manual Entry of Ansible File Information</h4>
          <p>
            <span class="text-danger text-underline"
              >WARNING: This is not a good idea.</span
            >
            A better idea is to create a vault file offline and then upload it.
            It's not a great idea to trust a random NPM package to not steal
            your network secrets. Use this only in testing or a lab environment.
          </p>

          <b-row>
            <b-col> </b-col>
          </b-row>
          <b-row>
            <b-col cols="2"> Type: </b-col>
            <b-col
              ><b-select
                v-model="generated_ansible.type"
                :options="['Username and Password', 'SSH Key']"
            /></b-col>
          </b-row>
          <b-row>
            <b-col cols="4">
              Ansible&nbsp;Vault&nbsp;Password:&nbsp;&nbsp;</b-col
            >
            <b-col>
              <b-input
                type="password"
                v-model="generated_ansible.vault_password"
              />
            </b-col>
          </b-row>
          <b-row>
            <b-col cols="2"> Filename </b-col>
            <b-col>
              <b-input
                v-model="generated_ansible.filename"
                placeholder="Ansible Vault filename (e.g. password.yml)"
              />
            </b-col>
          </b-row>
          <hr />
          <b-row v-if="generated_ansible.type == 'Username and Password'">
            <b-col>
              Username:
              <b-input
                v-model="generated_ansible.ssh_username"
                placeholder="Ansible username (e.g. root)"
              />
            </b-col>
            <b-col>
              Password:
              <b-input
                type="password"
                v-model="generated_ansible.ssh_password"
              />
              <hr />
              SSH Key Passphrase:
              <b-input
                type="password"
                v-model="generated_ansible.ssh_passphrase"
              />

              SSH Key:
              <b-select
                v-if="files_list['ssh'] != undefined"
                v-model="generated_ansible.ssh_key_file"
                :options="files_list['ssh']"
              />
              <div v-else class="m-2">
                <b-spinner />
              </div>
            </b-col>
          </b-row>

          <b-row v-if="generated_ansible.type == 'SSH Key'">
            <b-col>
              SSH Key <br />
              <b-textarea
                style="height: 150px"
                v-model="generated_ansible.ssh_key"
              />
            </b-col>
          </b-row>
          <b-row>
            <b-col>
              <b-button
                class="float-right"
                variant="primary"
                style="width: 100%"
                @click="
                  () => {
                    loading_generated_vault_file = true;
                    $forceUpdate();
                    generateAnsibleVault();
                  }
                "
              >
                Generate Ansible File
              </b-button>
            </b-col>
          </b-row>
          <b-row>
            <b-col v-if="!loading_generated_vault_file">
              {{ generated_vault_file }}
            </b-col>
            <b-col v-else>
              <b-spinner class="m-2" />
            </b-col>
          </b-row>
        </b-col>
      </b-row>
    </b-modal>

    <b-modal
      id="new_playbook"
      title="Add New Ansible Playbook"
      @ok="createPlaybook"
    >
      <b-container>
        <b-row>
          <b-col cols="4"> Playbook name: </b-col>
          <b-col>
            <b-input
              placeholder="New Playbook name (e.g. test.yml)"
              v-model="new_ansible_file"
            />
          </b-col>
        </b-row>
      </b-container>
    </b-modal>

    <b-row>
      <b-col>
        <b-card no-body>
          <b-tabs pills card>
            <b-tab
              title="Deploy to Single Host"
              class="pl-5 pr-5"
              @click="
                () => {
                  isTesting = false;
                  ips = [];
                  selected_subnet = '';
                  selected_group = '';
                }
              "
              active
            >
              Single Host:
              <b-select
                :state="selected_host != ''"
                v-model="selected_host"
                :options="hosts"
                :enabled="isTesting"
              />
            </b-tab>

            <b-tab
              title="Deploy to Group"
              @click="
                () => {
                  isTesting = false;
                  selected_host = null;
                }
              "
            >
              <b-row>
                <b-col>
                  Subnet:
                  <b-select
                    :state="selected_subnet != ''"
                    v-model="selected_subnet"
                    :options="subnets"
                  />
                </b-col>
                <b-col>
                  Group:
                  <b-select
                    :state="selected_group != ''"
                    v-model="selected_group"
                    :options="groups"
                  />
                </b-col>
              </b-row>
            </b-tab>

            <b-tab
              title="Deployment Testing"
              class="bg-dark text-success"
              @click="
                () => {
                  isTesting = true;
                  selected_host = sample_ip;
                  ips = [];
                  selected_group = '';
                  selected_subnet = '';
                }
              "
            >
              <h4>TESTING MODE</h4>
              Host: <br /><b>sampleclient - ({{ sample_ip }})</b> <br />Backend
              ip is {{ ip }}
            </b-tab>
          </b-tabs>
        </b-card>
      </b-col>
    </b-row>
    <b-row v-if="selected_host || ips.length > 0">
      <b-col>
        <b-card class="text-left">
          <b-row>
            <b-col>
              <h4>Deployment Files</h4>
              <ul>
                <li>
                  These must be encrypted vault files (using
                  <code>ansible-vault</code>).
                </li>
                <li>
                  Please note that this file will be added to
                  <code>vars_files</code> sections in your ansible playbook
                  automatically.
                </li>
              </ul>
            </b-col>
          </b-row>
          <b-row>
            <b-col>
              Select uploaded Become Password file:
              <b-select
                v-if="files_list['become'] != undefined"
                :options="files_list['become']"
                v-model="selected['become']"
                :state="selected['become'] != ''"
              />
              <b-spinner v-else class="m-2" />
              <br />
              <b-button
                class="mt-3"
                variant="success"
                @click="
                  () => {
                    generated_ansible = { type: 'Username and Password' };
                    generated_vault_file = '';

                    $bvModal.show('add_vault');
                  }
                "
              >
                + Add Ansible Vault File
              </b-button>
            </b-col>
            <b-col>
              Vault Password:<br />
              <b-input
                :state="vault_password != ''"
                type="password"
                v-model="vault_password"
              />
            </b-col>
          </b-row>
        </b-card>
      </b-col>
    </b-row>
    <b-row
      v-if="
        (selected_host || ips.length > 0) &&
        selected['become'] &&
        vault_password
      "
      ><b-col>
        <b-card>
          <b-row>
            <b-col>
              <h4 class="">Ansible playbook</h4>
            </b-col>
          </b-row>
          <b-row>
            <b-col>
              Playbook: <br />
              <b-select
                class="mt-2 mb-2"
                v-if="files_list['ansible'] != undefined"
                :options="files_list['ansible']"
                :state="selected_playbook != ''"
                v-model="selected_playbook"
              />
            </b-col>
            <b-col cols="3" class="pt-2">
              <br />
              <b-button
                style="width: 100%"
                variant="success"
                @click="
                  () => {
                    new_ansible_file = '';
                    $bvModal.show('new_playbook');
                  }
                "
              >
                + Add New Playbook
              </b-button>
            </b-col>
          </b-row>

          <hr />
          <b-row>
            <b-col>
              <span class="text-left">Ansible Playbook Contents</span>

              <codemirror
                v-if="loadings.playbook == undefined || loadings.playbook == 0"
                bordered
                class="border"
                ref="code_mirror_playbook"
                v-model="playbook_contents"
                :options="{
                  tabSize: 4,
                  mode: 'text/x-yaml',
                  theme: 'default',
                  lineNumbers: true,
                  line: true,
                }"
                @ready="() => {}"
                @focus="() => {}"
                @input="() => {}"
              >
              </codemirror>

              <div v-else class="mt-2 text-center">
                <b-spinner class="ml-auto mr-auto mt-4" />
              </div>
              <div class="overflow-hidden mt-2">
                <b-button
                  variant="success"
                  class="mb-2 float-right"
                  @click="savePlaybook()"
                  v-if="
                    loadings.save_playbook == undefined ||
                    loadings.save_playbook == 0
                  "
                >
                  <font-awesome-icon icon="save" size="1x" />&nbsp; Save
                  Playbook
                </b-button>
                <div class="mb-2 mt-2 float-right" v-else>
                  <b-spinner />
                </div>
              </div>
            </b-col>
          </b-row>
        </b-card> </b-col
    ></b-row>
    <div
      v-if="
        (selected_host || ips.length > 0) &&
        selected['become'] &&
        vault_password &&
        selected_playbook
      "
    >
      <b-button
        size="lg"
        style="width: 100%"
        v-if="isTesting"
        variant="success"
        @click="runPlaybook()"
        >Deploy to sampleclient</b-button
      >
      <b-button
        size="lg"
        style="width: 100%"
        v-else
        variant="primary"
        @click="runPlaybook()"
        >Deploy to host<span v-if="ips.length != 0">s</span></b-button
      >
      <hr />
      <div
        class="playbook_result mb-4"
        v-html="$sanitize(playbook_result)"
        v-if="running && playbook_result && playbook_loaded && ips.length == 0"
      ></div>

      <div v-if="ips != [] && running">
        <div v-for="(item, idx) in ips" v-bind:key="idx">
          <h4 class="text-left">{{ item }} Results</h4>
          <div
            class="playbook_result"
            v-if="playbook_results[item] != undefined"
            v-html="$sanitize(playbook_results[item])"
          ></div>
          <div class="overflow-hidden" v-else>
            <b-spinner class="m-1 float-left" />
          </div>
          <hr />
        </div>
      </div>

      <b-spinner class="m-2" v-if="!playbook_loaded" />
    </div>
  </b-container>
</template>
<script>
import Helper from "@/helper";
import styles from "@/assets/variables.scss";
const { Vault } = require("ansible-vault");
export default {
  name: "Deploy",
  data() {
    return {
      ssh_key_file: [],
      become_file: [],
      other_file: [],
      selected: {
        ssh: "",
        become: "",
        other: "",
      },

      generated_ansible: {},
      generated_vault_file: "",
      loading_generated_vault_file: false,

      ip: "",
      sample_ip: "",
      sample_loading: false,

      new_ansible_file: "",

      files_list: {},

      hosts: [],
      subnets: [],
      groups: [],
      ips: [],

      selected_subnet: "",
      selected_group: "",
      selected_host: "",

      vault_password: "",
      ansible_user: "",

      selected_playbook: "",
      playbook_contents: "",
      playbook_loaded: true,

      playbook_result: "",
      playbook_results: {},

      loadings: {},

      running: false,

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
    ssh_key_file: /* istanbul ignore next */ function (val) {
      this.uploadHelper(val, "ssh");
    },

    become_file: /* istanbul ignore next */ function (val) {
      this.uploadHelper(val, "become");
    },
    other_file: /* istanbul ignore next */ function (val) {
      this.uploadHelper(val, "other");
    },

    //TODO: Finish other uploads
    selected_playbook: /* istanbul ignore next */ function (val) {
      if (val != "") {
        this.loadPlaybook(val);
      }
    },

    selected_subnet: /* istanbul ignore next */ function (val) {
      if (val != "") {
        this.loadGroups();
      }
    },
    selected_group: /* istanbul ignore next */ function (val) {
      if (val != "") {
        this.loadGroupMembers();
      }
    },
  },
  methods: {
    generateAnsibleVault: async function () {
      var a = new Vault({ password: this.generated_ansible.vault_password });
      this.loading_generated_vault_file = true;

      let item;
      if (this.generated_ansible.type == "SSH Key") {
        item = this.generated_ansible.ssh_key;
      } else {
        item = `ansible_user: ${this.generated_ansible.ssh_username}`;

        item += `\nansible_ssh_pass: ${this.generated_ansible.ssh_password}\n`;
        item += `\nansible_become_password: ${this.generated_ansible.ssh_password}\n`;

        if (this.generated_ansible.ssh_passphrase > "") {
          item += `\nssh_key_pass: ${this.generated_ansible.ssh_passphrase}`;
        }
        if (this.generated_ansible.ssh_key_file > "") {
          item += `\nssh_key_file: /src/uploads/ssh/${this.generated_ansible.ssh_key_file}`;
        }
      }

      await a
        .encrypt(item)
        .then(async (x) => {
          this.loading_generated_vault_file = false;
          this.generated_vault_file = x;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    saveAnsibleVault: /* istanbul ignore next */ function (e) {
      e.preventDefault();
      var auth = this.$auth;
      var type = "become";
      var formData = new FormData();
      formData.append("file", this.generated_vault_file);
      formData.append("filename", this.generated_ansible.filename);
      Helper.apiPost("upload", "/" + type, auth.accessToken, auth, formData)
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadFilesList(type);
          this.$bvModal.hide("add_vault");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },

    uploadHelper: /* istanbul ignore next */ function (val, type) {
      if (val) {
        var auth = this.$auth;
        var formData = new FormData();
        formData.append("file", val);
        Helper.apiPost(
          "upload",
          "/" + type,
          auth.accessToken,
          auth,
          formData,
          true
        )
          .then((res) => {
            //this.$store.commit("updateError", res);
            this.selected[type] = res;
            this.loadFilesList(type);
          })
          .catch((e) => {
            if (("" + e).indexOf("521") != -1) {
              this.$store.commit(
                "updateError",
                "Error: Invalid file type uploaded.  Make sure your file is the correct type (Encrypted Ansible, Telegraf Conf, etc.)"
              );
            } else {
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

    createPlaybook: /* istanbul ignore next */ function (e) {
      var auth = this.$auth;
      e.preventDefault();
      Helper.apiCall("new_ansible_file", this.new_ansible_file, auth)
        .then(async () => {
          await this.loadFilesList("ansible");
          this.selected_playbook =
            this.new_ansible_file.replace(".yml", "") + ".yml";
          this.$bvModal.hide("new_playbook");
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
        this.selected_playbook.replace(".yml", ""),
        "/" + this.selected["become"].replace(/.yml$/, ""),
        auth,
        formData
      )
        .then((res) => {
          this.$store.commit("updateError", res);
          this.loadings["save_playbook"] = 0;
          this.loadPlaybook();
        })
        .catch((e) => {
          this.loadings["save_playbook"] = 0;
          this.$forceUpdate();
          if (("" + e).indexOf("471") != -1) {
            this.$store.commit(
              "updateError",
              "Error: Invalid Ansible File.  Correct the file and save again." +
                e
            );
          } else {
            this.$store.commit("updateError", e);
          }
        });
    },

    runPlaybook: /* istanbul ignore next */ async function () {
      if (this.selected["become"] == "") {
        this.$store.commit(
          "updateError",
          "Error: No Become Password file selected"
        );
        return false;
      }

      var auth = this.$auth;
      this.running = true;
      if (this.ips.length > 0) {
        this.ips.forEach((host) => {
          var formData = new FormData();
          var data = {
            hosts: host,
            playbook: this.selected_playbook.replace(".yml", ""),
            vault_password: this.vault_password,
            become_file: this.selected["become"].replace(".yml", ""),
            ssh_key: this.selected["ssh"],
          };
          formData.append("data", JSON.stringify(data));
          this.$forceUpdate();
          Helper.apiPost("ansible_runner", "", "", auth, formData)
            .then((res) => {
              this.playbook_results[host] = res;
              this.$forceUpdate();
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        });
        return true;
      }

      var formData = new FormData();
      var host = this.selected_host;

      this.playbook_loaded = false;
      var data = {
        hosts: host,
        playbook: this.selected_playbook.replace(".yml", ""),
        vault_password: this.vault_password,
        become_file: this.selected["become"].replace(".yml", ""),
        ssh_key: this.selected["ssh"],
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

    loadIP: /* istanbul ignore next */ async function () {
      var auth = this.$auth;
      this.sample_loading = true;
      await Helper.apiCall("find_ip", "", auth)
        .then((res) => {
          this.ip = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
          this.sample_loading = false;
        });
      await Helper.apiCall("find_ip", "sampleclient", auth)
        .then((res) => {
          this.sample_ip = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
          this.sample_loading = false;
        });
      this.sample_loading = false;
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
    loadSubnets: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("subnets", "", auth)
        .then((res) => {
          this.subnets = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    loadGroups: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("group", this.selected_subnet, auth)
        .then((res) => {
          this.groups = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },

    loadGroupMembers: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall(
        "group",
        this.selected_subnet + "/" + this.selected_group,
        auth
      )
        .then((res) => {
          this.ips = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },

    loadHosts: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("hosts", "", auth)
        .then((res) => {
          this.hosts = res.map((x) => {
            return {
              text: x.ip,
              value: x.ip,
            };
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
      this.loadSubnets();

      this.loadHosts();
    } catch (e) {
      this.$store.commit("updateError", e);
    }
  },
};
</script>
<style lang="scss" scoped>
@import "@/assets/variables.scss";

*::-webkit-scrollbar {
  height: 8px;
  width: 8px;
}
*::-webkit-scrollbar-track-piece {
  background: lightgrey;
}
*::-webkit-scrollbar-thumb {
  background: darkgrey;
}

.playbook_result {
  height: 400px;
  width: 100%;
  text-align: left;
  overflow-y: scroll;
  margin-top: 2rem;
  background-color: lightgrey;
  padding: 1rem;
}

.text-underline {
  font-weight: bold;
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

::v-deep .CodeMirror {
  min-height: 400px;
  width: 100% !important;
}
@media screen and (max-width: 991px) {
  .row {
    display: block;
  }
  .col-1,
  .col-2,
  .col-3,
  .col-4,
  .col-5,
  .col-6,
  .col-7,
  .col-8,
  .col-9,
  .col-10,
  .col-11,
  .col-12,
  .col,
  .col-auto,
  .col-sm-1,
  .col-sm-2,
  .col-sm-3,
  .col-sm-4,
  .col-sm-5,
  .col-sm-6,
  .col-sm-7,
  .col-sm-8,
  .col-sm-9,
  .col-sm-10,
  .col-sm-11,
  .col-sm-12,
  .col-sm,
  .col-sm-auto,
  .col-md-1,
  .col-md-2,
  .col-md-3,
  .col-md-4,
  .col-md-5,
  .col-md-6,
  .col-md-7,
  .col-md-8,
  .col-md-9,
  .col-md-10,
  .col-md-11,
  .col-md-12,
  .col-md,
  .col-md-auto,
  .col-lg-1,
  .col-lg-2,
  .col-lg-3,
  .col-lg-4,
  .col-lg-5,
  .col-lg-6,
  .col-lg-7,
  .col-lg-8,
  .col-lg-9,
  .col-lg-10,
  .col-lg-11,
  .col-lg-12,
  .col-lg,
  .col-lg-auto,
  .col-xl-1,
  .col-xl-2,
  .col-xl-3,
  .col-xl-4,
  .col-xl-5,
  .col-xl-6,
  .col-xl-7,
  .col-xl-8,
  .col-xl-9,
  .col-xl-10,
  .col-xl-11,
  .col-xl-12,
  .col-xl,
  .col-xl-auto {
    max-width: 100% !important;
    width: 100% !important;
    overflow: hidden;
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
    text-align: center;
    margin-left: 0;
  }
  ::v-deep .CodeMirror {
    text-align: left;
  }
}
</style>
