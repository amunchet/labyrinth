<template>
  <b-container>
    <b-row>
      <b-col>
        <b-row>
          <h4>Files</h4> </b-row
        ><b-row>
          <ul>
            <li>SSH Key</li>
            <li>TOTP Key</li>
            <li>Become Password</li>
            <li>Telegraf conf file</li>
          </ul>
        </b-row>
        <b-row>
          <b-button>Upload</b-button>
        </b-row>
              </b-col>
      <b-col>
        <h2>Deploy</h2>
        <b-row>
          Host: <b-select />
        </b-row>
        <b-row>
          <b-col>
          <h5>Ansible playbook</h5>
          Validating playbook...
          <textarea /><br />

<b-row>
          Password: 
            <b-input type="password" />
        </b-row>

          <b-button variant="success">Deploy</b-button>

          Test deployment in docker...
          </b-col>
        </b-row>
        </b-col>
    </b-row>
  </b-container>
</template>
<script>
export default {};
</script>
<style lang="scss" scoped>
textarea{
  width: 100%;
  min-height: 400px;
}
</style>