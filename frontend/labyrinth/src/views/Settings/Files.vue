<template>
  <div class="text-left">
    <b-modal id="rename-file" title="Rename File" @ok="renameFile">
      <b-row>
        <b-col cols="4">Current name</b-col>
        <b-col>{{ rename_file_name }}</b-col>
      </b-row>
      <b-row class="mt-3">
        <b-col cols="4">New name</b-col>
        <b-col>
          <b-input v-model="rename_new_name" />
        </b-col>
      </b-row>
    </b-modal>

    <h3>Files</h3>
    <b-container class="mt-3">
      <b-row>
        <b-col cols="3">Folder</b-col>
        <b-col>
          <b-select v-model="selected_folder" :options="folders" />
        </b-col>
        <b-col cols="2">
          <b-button variant="primary" @click="loadFiles()">
            <font-awesome-icon icon="sync-alt" size="1x" />
          </b-button>
        </b-col>
      </b-row>

      <b-row class="mt-3">
        <b-col cols="3">Upload file</b-col>
        <b-col>
          <b-form-file
            v-model="upload_file"
            placeholder="Choose a file or drop it here..."
            drop-placeholder="Drop file here..."
          />
        </b-col>
      </b-row>

      <div v-if="loading" class="text-center mt-4">
        <b-spinner />
      </div>
      <div v-else class="mt-4">
        <b-row
          v-for="file in files"
          :key="`${selected_folder}-${file}`"
          class="file-row"
        >
          <b-col class="file-name">{{ file }}</b-col>
          <b-col cols="4" class="text-right">
            <b-button
              size="sm"
              variant="outline-primary"
              class="mr-2"
              @click="openRename(file)"
            >
              Rename
            </b-button>
            <b-button size="sm" variant="outline-danger" @click="deleteFile(file)">
              Delete
            </b-button>
          </b-col>
        </b-row>
        <div v-if="files.length === 0" class="text-muted">No files uploaded.</div>
      </div>
    </b-container>
  </div>
</template>
<script>
import Helper from "@/helper";

export default {
  name: "SettingsFiles",
  data() {
    return {
      folders: ["become", "ssh", "telegraf", "totp", "other", "ansible"],
      selected_folder: "become",
      files: [],
      loading: false,
      upload_file: null,
      rename_file_name: "",
      rename_new_name: "",
    };
  },
  watch: {
    selected_folder: /* istanbul ignore next */ function () {
      this.loadFiles();
    },
    upload_file: /* istanbul ignore next */ function (val) {
      if (val) {
        this.uploadFile(val);
      }
    },
  },
  methods: {
    loadFiles: /* istanbul ignore next */ function () {
      let auth = this.$auth;
      this.loading = true;
      Helper.apiCall("files", this.selected_folder, auth)
        .then((res) => {
          this.files = res;
          this.loading = false;
        })
        .catch((e) => {
          this.loading = false;
          this.$store.commit("updateError", e);
        });
    },
    uploadFile: /* istanbul ignore next */ function (val) {
      let auth = this.$auth;
      let formData = new FormData();
      formData.append("file", val);
      Helper.apiPost(
        "upload",
        "/" + this.selected_folder,
        auth.accessToken,
        auth,
        formData,
        true
      )
        .then(() => {
          this.upload_file = null;
          this.loadFiles();
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    openRename: /* istanbul ignore next */ function (name) {
      this.rename_file_name = name;
      this.rename_new_name = name;
      this.$bvModal.show("rename-file");
    },
    renameFile: /* istanbul ignore next */ function (e) {
      e.preventDefault();
      let auth = this.$auth;
      let formData = new FormData();
      formData.append("old_name", this.rename_file_name);
      formData.append("new_name", this.rename_new_name);
      Helper.apiPost(
        `files/${this.selected_folder}/rename`,
        "",
        "",
        auth,
        formData
      )
        .then(() => {
          this.$bvModal.hide("rename-file");
          this.loadFiles();
        })
        .catch((err) => {
          this.$store.commit("updateError", err);
        });
    },
    deleteFile: /* istanbul ignore next */ function (name) {
      let auth = this.$auth;
      this.$bvModal
        .msgBoxConfirm(`Delete ${name}?`)
        .then((res) => {
          if (!res) {
            return;
          }
          Helper.apiDelete(`files/${this.selected_folder}`, name, auth)
            .then(() => {
              this.loadFiles();
            })
            .catch((e) => {
              this.$store.commit("updateError", e);
            });
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: function () {
    this.loadFiles();
  },
};
</script>
<style lang="scss" scoped>
.file-row {
  border-bottom: 1px solid #efefef;
  padding: 0.75rem 0;
  align-items: center;
}

.file-name {
  word-break: break-word;
}
</style>
