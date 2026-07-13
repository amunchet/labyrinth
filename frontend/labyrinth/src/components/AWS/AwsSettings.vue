<template>
  <div class="p-3">
    <b-row>
      <b-col cols="12" lg="5" class="mb-4 mb-lg-0">
        <b-card>
          <b-card-title>
            {{
              editingAccountId
                ? `Edit AWS Account: ${form.name}`
                : "Add AWS Account"
            }}
          </b-card-title>
          <p class="text-muted">
            Configure AWS credentials and region used to list EC2 instances.
          </p>

          <b-alert v-if="successMessage" show variant="success">
            {{ successMessage }}
          </b-alert>
          <b-alert v-if="errorMessage" show variant="danger">
            {{ errorMessage }}
          </b-alert>

          <b-form @submit.prevent="submitAccountForm">
            <b-form-group label="Account Name" label-for="aws-account-name">
              <b-form-input
                id="aws-account-name"
                v-model="form.name"
                required
                placeholder="Production"
              />
            </b-form-group>

            <b-form-group label="Region" label-for="aws-account-region">
              <b-form-input
                id="aws-account-region"
                v-model="form.region"
                required
                placeholder="us-east-1"
              />
            </b-form-group>

            <b-form-group label="Access Key ID" label-for="aws-access-key-id">
              <b-form-input
                id="aws-access-key-id"
                v-model="form.access_key_id"
                required
                placeholder="AKIA..."
              />
            </b-form-group>

            <b-form-group
              label="Secret Access Key"
              label-for="aws-secret-access-key"
              :description="
                editingAccountId
                  ? 'Leave blank to keep the current secret.'
                  : ''
              "
            >
              <b-form-input
                id="aws-secret-access-key"
                v-model="form.secret_access_key"
                type="password"
                :required="!editingAccountId"
                placeholder="AWS secret access key"
              />
            </b-form-group>

            <b-form-group
              label="Session Token"
              label-for="aws-session-token"
              description="Optional. Leave blank unless you are using temporary AWS credentials."
            >
              <b-form-textarea
                id="aws-session-token"
                v-model="form.session_token"
                rows="3"
                placeholder="Optional STS session token"
              />
            </b-form-group>

            <div class="d-flex justify-content-end">
              <b-button
                v-if="editingAccountId"
                variant="secondary"
                class="mr-2"
                @click="resetForm"
              >
                Cancel
              </b-button>
              <b-button variant="primary" type="submit" :disabled="saving">
                {{
                  saving
                    ? "Saving..."
                    : editingAccountId
                    ? "Save Changes"
                    : "Add Account"
                }}
              </b-button>
            </div>
          </b-form>
        </b-card>
      </b-col>

      <b-col cols="12" lg="7">
        <b-card>
          <b-card-title>Configured AWS Accounts</b-card-title>
          <p class="text-muted">
            Each account-region pair is queried when the EC2 inventory page
            refreshes.
          </p>

          <b-alert v-if="!accounts.length" show variant="info">
            No AWS accounts configured yet.
          </b-alert>

          <b-table
            v-else
            :items="accounts"
            :fields="fields"
            striped
            hover
            small
            responsive
          >
            <template #cell(account)="row">
              <div class="text-left">
                <div class="font-weight-bold">{{ row.item.name }}</div>
                <div class="small text-muted">{{ row.item.region }}</div>
              </div>
            </template>

            <template #cell(access_key_id)="row">
              <div class="text-left small">{{ row.item.access_key_id }}</div>
            </template>

            <template #cell(updated)="row">
              <div class="small text-left">
                {{ row.item.updated || row.item.created || "—" }}
              </div>
            </template>

            <template #cell(actions)="row">
              <div class="text-right">
                <b-button
                  variant="link"
                  class="p-0 mr-3"
                  @click="editAccount(row.item)"
                >
                  Edit
                </b-button>
                <b-button
                  variant="link"
                  class="p-0 text-danger"
                  @click="deleteAccount(row.item._id)"
                  :disabled="deletingAccountId === row.item._id"
                >
                  {{
                    deletingAccountId === row.item._id
                      ? "Deleting..."
                      : "Delete"
                  }}
                </b-button>
              </div>
            </template>
          </b-table>
        </b-card>
      </b-col>
    </b-row>
  </div>
</template>

<script>
import Helper from "@/helper";

export default {
  name: "AwsSettings",
  data() {
    return {
      saving: false,
      deletingAccountId: null,
      editingAccountId: null,
      successMessage: "",
      errorMessage: "",
      accounts: [],
      fields: [
        { key: "account", label: "Account" },
        { key: "access_key_id", label: "Access Key ID" },
        { key: "updated", label: "Updated" },
        { key: "actions", label: "" },
      ],
      form: this.emptyForm(),
    };
  },
  mounted() {
    this.loadAccounts();
  },
  methods: {
    emptyForm() {
      return {
        name: "",
        region: "us-east-1",
        access_key_id: "",
        secret_access_key: "",
        session_token: "",
      };
    },
    parseMaybeJSON(payload) {
      return typeof payload === "string" ? JSON.parse(payload) : payload;
    },
    clearMessages() {
      this.successMessage = "";
      this.errorMessage = "";
    },
    async loadAccounts() {
      this.clearMessages();
      try {
        const auth = this.$auth;
        const response = await Helper.apiCall("aws", "settings", auth);
        const payload = this.parseMaybeJSON(response);
        this.accounts = payload.accounts || [];
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      }
    },
    resetForm() {
      this.editingAccountId = null;
      this.form = this.emptyForm();
      this.clearMessages();
    },
    editAccount(account) {
      this.clearMessages();
      this.editingAccountId = account._id;
      this.form = {
        name: account.name,
        region: account.region,
        access_key_id: account.access_key_id,
        secret_access_key: "",
        session_token: "",
      };
      this.$nextTick(() => {
        const el = document.getElementById("aws-account-name");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    },
    async submitAccountForm() {
      if (this.editingAccountId) {
        await this.saveAccountEdit();
      } else {
        await this.addAccount();
      }
    },
    async addAccount() {
      if (
        !this.form.name ||
        !this.form.region ||
        !this.form.access_key_id ||
        !this.form.secret_access_key
      ) {
        this.errorMessage = "Please fill in all required fields";
        return;
      }

      this.saving = true;
      this.clearMessages();
      try {
        const auth = this.$auth;
        const body = JSON.stringify(this.form);
        await Helper.apiPost("aws/accounts", "", "", auth, body);
        this.form = this.emptyForm();
        await this.loadAccounts();
        this.successMessage = "AWS account added successfully!";
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      } finally {
        this.saving = false;
      }
    },
    async saveAccountEdit() {
      this.saving = true;
      this.clearMessages();
      try {
        const auth = this.$auth;
        const payload = {
          name: this.form.name,
          region: this.form.region,
          access_key_id: this.form.access_key_id,
        };
        if (this.form.secret_access_key) {
          payload.secret_access_key = this.form.secret_access_key;
        }
        if (this.form.session_token) {
          payload.session_token = this.form.session_token;
        }

        await Helper.apiPut(
          "aws/accounts",
          this.editingAccountId,
          auth,
          payload
        );
        this.resetForm();
        await this.loadAccounts();
        this.successMessage = "AWS account updated successfully!";
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      } finally {
        this.saving = false;
      }
    },
    async deleteAccount(accountId) {
      if (!confirm("Delete this AWS account configuration?")) return;

      this.clearMessages();
      this.deletingAccountId = accountId;
      try {
        const auth = this.$auth;
        await Helper.apiDelete("aws/accounts", accountId, auth);
        if (this.editingAccountId === accountId) {
          this.resetForm();
        }
        await this.loadAccounts();
        this.successMessage = "AWS account deleted successfully!";
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      } finally {
        this.deletingAccountId = null;
      }
    },
  },
};
</script>
