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

    <b-row class="mt-4">
      <b-col cols="12">
        <b-card class="text-left text-start">
          <b-card-title>EC2 Unmatched Instance Alerts</b-card-title>
          <b-card-sub-title>
            Email notifications when an EC2 instance can't be matched to an
            existing Labyrinth host
          </b-card-sub-title>

          <b-form @submit.prevent="saveAlertSettings">
            <b-form-group
              label="Recipient email(s):"
              label-for="ec2-alert-recipients"
              description="Comma-separated list of email addresses to notify"
            >
              <b-form-textarea
                id="ec2-alert-recipients"
                v-model="alertRecipientsText"
                rows="2"
                placeholder="admin@example.com, ops@example.com"
              />
            </b-form-group>

            <b-button
              variant="primary"
              type="submit"
              :disabled="savingAlertSettings"
            >
              <b-spinner
                small
                v-if="savingAlertSettings"
                class="mr-2"
              ></b-spinner>
              Save Alert Settings
            </b-button>
          </b-form>

          <hr />

          <p class="text-muted small mb-2">
            Send a test email to the recipient(s) above without waiting for
            the next scheduled check.
          </p>
          <b-button
            variant="outline-secondary"
            class="mr-2"
            :disabled="sendingSimpleTest || sendingFullTest"
            @click="sendTestEmail('simple')"
          >
            <b-spinner small v-if="sendingSimpleTest" class="mr-2"></b-spinner>
            Send Test Email
          </b-button>
          <b-button
            variant="outline-secondary"
            :disabled="sendingSimpleTest || sendingFullTest"
            @click="sendTestEmail('full')"
          >
            <b-spinner small v-if="sendingFullTest" class="mr-2"></b-spinner>
            Send Full Test Email (Live Data)
          </b-button>
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
      alertRecipientsText: "",
      savingAlertSettings: false,
      sendingSimpleTest: false,
      sendingFullTest: false,
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
        this.alertRecipientsText = Array.isArray(payload.ec2_alert_recipients)
          ? payload.ec2_alert_recipients.join(", ")
          : "";
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      }
    },
    async saveAlertSettings() {
      this.savingAlertSettings = true;
      this.clearMessages();
      try {
        const auth = this.$auth;
        const recipientsData = new FormData();
        recipientsData.append("name", "ec2_alert_recipients");
        recipientsData.append("value", this.alertRecipientsText);
        await Helper.apiPost("settings", "", "", auth, recipientsData);
        this.successMessage = "EC2 unmatched instance alert settings saved successfully!";
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      } finally {
        this.savingAlertSettings = false;
      }
    },
    async sendTestEmail(mode) {
      const recipients = this.alertRecipientsText
        .split(",")
        .map((r) => r.trim())
        .filter((r) => r.length > 0);

      if (recipients.length === 0) {
        this.errorMessage =
          "Enter at least one recipient email above before sending a test.";
        return;
      }

      const isFull = mode === "full";
      if (isFull) {
        this.sendingFullTest = true;
      } else {
        this.sendingSimpleTest = true;
      }
      this.clearMessages();

      try {
        const auth = this.$auth;
        const payload = JSON.stringify({ mode: mode, recipients: recipients });
        const response = await Helper.apiPost(
          "aws/test-email",
          "",
          "",
          auth,
          payload
        );
        const data = this.parseMaybeJSON(response);

        if (isFull) {
          const errorCount =
            data && Array.isArray(data.account_errors)
              ? data.account_errors.length
              : 0;
          let msg =
            "Full test email sent! Found " +
            data.unmatched_found +
            " unmatched instance(s).";
          if (errorCount > 0) {
            msg +=
              " (" +
              errorCount +
              " account" +
              (errorCount === 1 ? "" : "s") +
              " could not be reached)";
          }
          this.successMessage = msg;
        } else {
          this.successMessage = "Test email sent successfully! Check your inbox.";
        }
      } catch (err) {
        this.errorMessage = err.message || `${err}`;
      } finally {
        this.sendingSimpleTest = false;
        this.sendingFullTest = false;
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
