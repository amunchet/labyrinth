<template>
  <div class="aws-documentation">
    <b-card class="mb-4 text-left text-start">
      <b-card-title>What This Page Does</b-card-title>
      <b-card-body>
        <p>
          The AWS tab lists your EC2 instances (virtual machines running in
          Amazon Web Services) directly inside Labyrinth. To do that, Labyrinth
          needs a set of AWS "API keys" so it can ask AWS, on your behalf, "what
          servers do I have?"
        </p>
        <p class="mb-0">
          This guide walks through creating those keys and adding them to
          Labyrinth, one click at a time. No prior AWS experience is assumed.
        </p>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>1. Create an AWS User Just for Labyrinth</b-card-title>
      <b-card-body>
        <p>
          It's best to create a dedicated user for Labyrinth instead of using
          your own AWS login. That way you can control exactly what it's allowed
          to see, and you can turn off access later without affecting anyone
          else.
        </p>

        <h6>Steps:</h6>
        <ol>
          <li>
            Log in to the
            <a href="https://console.aws.amazon.com/" target="_blank"
              >AWS Console</a
            >
            with your normal AWS account.
          </li>
          <li>
            In the search bar at the top, type <strong>IAM</strong> and click on
            the <strong>IAM</strong> result.
          </li>
          <li>On the left-hand menu, click <strong>Users</strong>.</li>
          <li>Click the <strong>Create user</strong> button (top right).</li>
          <li>
            For the user name, type something easy to recognize later, such as
            <code>labyrinth-readonly</code>. Click <strong>Next</strong>.
          </li>
        </ol>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title
        >2. Give the User Permission to View EC2 Instances</b-card-title
      >
      <b-card-body>
        <p>
          Labyrinth only needs to <em>look at</em> your instances, never change
          them. Give it the smallest amount of access possible.
        </p>

        <h6>Steps:</h6>
        <ol>
          <li>
            On the <strong>Set permissions</strong> screen, choose
            <strong>Attach policies directly</strong>.
          </li>
          <li>In the search box, type <code>AmazonEC2ReadOnlyAccess</code>.</li>
          <li>
            Check the box next to <strong>AmazonEC2ReadOnlyAccess</strong> in
            the results.
          </li>
          <li>
            Click <strong>Next</strong>, review the summary, then click
            <strong>Create user</strong>.
          </li>
        </ol>

        <p>
          <strong>Prefer a more locked-down option?</strong> Instead of the AWS
          managed policy above, you can create a custom policy that only allows
          the single permission Labyrinth actually uses:
        </p>
        <b-card bg-variant="light" class="mt-2 mb-2">
          <pre class="mb-0"><code>{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
    }
  ]
}</code></pre>
        </b-card>
        <p class="mb-0">
          To use this instead, choose <strong>Create policy</strong> during the
          permissions step, paste this into the JSON editor, give it a name like
          <code>labyrinth-ec2-readonly</code>, and attach that policy to the
          user instead of <code>AmazonEC2ReadOnlyAccess</code>.
        </p>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>3. Create the Access Key</b-card-title>
      <b-card-body>
        <p>
          The access key is what Labyrinth actually uses to log in as this user.
          It's made of two parts: an <strong>Access Key ID</strong> (like a
          username) and a <strong>Secret Access Key</strong> (like a password).
        </p>

        <h6>Steps:</h6>
        <ol>
          <li>
            After the user is created, click on its name in the
            <strong>Users</strong>
            list to open it.
          </li>
          <li>Click the <strong>Security credentials</strong> tab.</li>
          <li>
            Scroll down to <strong>Access keys</strong> and click
            <strong>Create access key</strong>.
          </li>
          <li>
            When asked for a use case, choose
            <strong>Third-party service</strong> (this is exactly that:
            Labyrinth is a third-party service accessing AWS). Acknowledge the
            confirmation checkbox and click <strong>Next</strong>.
          </li>
          <li>
            (Optional) Add a description tag such as <code>labyrinth</code>,
            then click <strong>Create access key</strong>.
          </li>
          <li>
            <strong>Important:</strong> You'll now see the
            <strong>Access key</strong> and
            <strong>Secret access key</strong> values. Copy both somewhere safe
            right now &mdash; AWS will never show you the secret key again after
            you leave this page.
          </li>
        </ol>

        <b-alert show variant="warning">
          If you lose the secret key, you can't recover it. You'll need to
          delete the access key and create a new one, then update it in
          Labyrinth.
        </b-alert>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>4. Add the Account in Labyrinth</b-card-title>
      <b-card-body>
        <p>Now bring those two values into Labyrinth:</p>

        <h6>Steps:</h6>
        <ol>
          <li>
            Click the <strong>Settings</strong> tab at the top of this page.
          </li>
          <li>
            Fill in the <strong>Add AWS Account</strong> form on the left:
            <ul>
              <li>
                <strong>Account Name:</strong> any label to help you remember
                this account, e.g. <code>Production</code>.
              </li>
              <li>
                <strong>Region:</strong> the AWS region your instances run in,
                e.g. <code>us-east-1</code>. This is shown in the top-right
                corner of the AWS Console next to your account name.
              </li>
              <li>
                <strong>Access Key ID:</strong> paste the Access Key ID you
                copied in step 3.
              </li>
              <li>
                <strong>Secret Access Key:</strong> paste the Secret Access Key
                you copied in step 3.
              </li>
              <li>
                <strong>Session Token:</strong> leave this blank. It's only used
                for temporary credentials, which most setups don't need.
              </li>
            </ul>
          </li>
          <li>Click <strong>Add Account</strong>.</li>
          <li>
            Switch to the <strong>EC2 Instances</strong> tab &mdash; your
            instances should now appear within a few seconds.
          </li>
        </ol>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>Security Best Practices</b-card-title>
      <b-card-body>
        <ul class="mb-0">
          <li>
            Always create a separate, dedicated IAM user for Labyrinth &mdash;
            never reuse your personal login keys.
          </li>
          <li>Only grant read-only EC2 permissions (see step 2 above).</li>
          <li>Rotate (recreate) the access key every few months.</li>
          <li>
            If a key is ever exposed or you're unsure it's safe, delete it in
            IAM immediately and create a new one.
          </li>
          <li>
            Never paste access keys into chat messages, tickets, or public
            repositories.
          </li>
        </ul>
      </b-card-body>
    </b-card>

    <b-card class="text-left text-start">
      <b-card-title>Troubleshooting</b-card-title>
      <b-card-body>
        <h6>"Missing required fields" when adding an account:</h6>
        <ul>
          <li>
            Account Name, Region, Access Key ID, and Secret Access Key are all
            required.
          </li>
          <li>Session Token can be left empty.</li>
        </ul>

        <h6>No instances showing up:</h6>
        <ul>
          <li>
            Double-check the <strong>Region</strong> matches where your
            instances actually run.
          </li>
          <li>
            Confirm the IAM user has the
            <code>AmazonEC2ReadOnlyAccess</code> policy (or the custom policy
            from step 2) attached.
          </li>
          <li>
            Make sure the Access Key ID and Secret Access Key were copied
            without extra spaces.
          </li>
        </ul>

        <h6>Authentication / permission errors:</h6>
        <ul>
          <li>
            The access key may have been deleted or deactivated in AWS &mdash;
            create a new one and update the account in Labyrinth's Settings tab.
          </li>
          <li>
            Verify the policy was actually attached to the user (IAM &rarr;
            Users &rarr; select user &rarr; Permissions tab).
          </li>
        </ul>

        <h6>Need to rotate or replace a key:</h6>
        <ul class="mb-0">
          <li>
            In AWS IAM, create a new access key for the user, then in Labyrinth
            click <strong>Edit</strong> next to the account and paste in the new
            Access Key ID and Secret Access Key.
          </li>
          <li>
            Afterwards, delete the old access key in AWS IAM so it can no longer
            be used.
          </li>
        </ul>
      </b-card-body>
    </b-card>
  </div>
</template>

<script>
export default {
  name: "AwsDocumentation",
};
</script>

<style lang="scss" scoped>
.aws-documentation {
  code {
    background-color: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Courier New", monospace;
  }

  pre code {
    background-color: transparent;
    padding: 0;
  }

  h6 {
    margin-top: 1rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
  }
}
</style>
