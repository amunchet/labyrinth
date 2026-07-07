<template>
  <div class="proxmox-documentation">
    <b-card class="mb-4">
      <b-card-title>Proxmox Setup Guide</b-card-title>
      <b-card-body class="text-left text-start">
        <h5>1. Creating Proxmox API Token</h5>
        <p>
          To use Disk Space Check with Proxmox, you need to create an API token that
          allows querying host and storage information.
        </p>

        <h6>Steps:</h6>
        <ol>
          <li>
            Log in to your Proxmox VE cluster at
            <code>https://your-proxmox-host:8006</code>
          </li>
          <li>Navigate to <strong>Datacenter</strong> → <strong>API Tokens</strong></li>
          <li>
            Click <strong>"Add"</strong> to create a new token
          </li>
          <li>
            Fill in the form:
            <ul>
              <li><strong>User:</strong> Select or create a user (e.g., <code>labyrinth@pve</code>)</li>
              <li><strong>Token ID:</strong> Give it a descriptive name (e.g., <code>disk-space-check</code>)</li>
              <li><strong>Privilege Separation:</strong> Uncheck to inherit user permissions</li>
            </ul>
          </li>
          <li>Click <strong>"Add"</strong> to generate the token</li>
          <li>
            <strong>Important:</strong> Copy the full token value immediately
            (format: <code>user@realm!token_id=token_secret</code>)
          </li>
        </ol>

        <h6>Required Permissions:</h6>
        <p>The user account needs at least these permissions:</p>
        <ul>
          <li><code>Sys.Audit</code> - To read node and storage information</li>
          <li><code>VM.Audit</code> - To read VM and container information</li>
        </ul>

        <p>
          For security, consider creating a dedicated user with minimal permissions:
        </p>
        <b-card bg-variant="light" class="mt-3 mb-3">
          <code>
            pveum user add labyrinth@pve --password<br />
            pveum acl modify / --user labyrinth@pve --role PVEAuditor
          </code>
        </b-card>

        <h6>Testing the Token:</h6>
        <p>
          You can test the token by running this command on your Proxmox host:
        </p>
        <b-card bg-variant="light" class="mt-3 mb-3">
          <code>
            curl -k -H "Authorization: PVEAPIToken=user@pve!token_id=token_secret" \<br />
            &nbsp;&nbsp;https://localhost:8006/api2/json/nodes
          </code>
        </b-card>

        <p>
          If successful, you'll see a JSON response with your cluster nodes.
        </p>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>Tagging Proxmox Hosts</b-card-title>
      <b-card-body>
        <p>
          To enable disk space monitoring for a Proxmox host, you must tag it in the
          Labyrinth system:
        </p>

        <h6>Steps:</h6>
        <ol>
          <li>Go to <strong>Dashboard</strong> and find your Proxmox host</li>
          <li>Click on the host to view details</li>
          <li>Add the tag <strong>"Proxmox"</strong> (case-sensitive)</li>
          <li>Save the changes</li>
          <li>Return to Disk Space Check and click "Refresh"</li>
        </ol>

        <p>
          The system will automatically detect all hosts tagged with "Proxmox" and
          attempt to retrieve disk space information using the configured API keys.
        </p>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>API Key Management</b-card-title>
      <b-card-body>
        <h6>Global API Key vs Host-Specific Keys:</h6>

        <ul>
          <li>
            <strong>Global Key:</strong> Applied to all Proxmox hosts unless overridden
          </li>
          <li>
            <strong>Host-Specific Key:</strong> Overrides the global key for a particular
            host (useful for multi-cluster setups with different credentials)
          </li>
        </ul>

        <h6>Security Best Practices:</h6>
        <ul>
          <li>Use API tokens instead of plain username/password</li>
          <li>Create a dedicated, low-privilege user for Labyrinth</li>
          <li>Rotate tokens regularly</li>
          <li>Never share tokens in logs or documentation</li>
          <li>Restrict token usage to specific IPs if possible</li>
        </ul>

        <h6>Format Reminder:</h6>
        <p>
          API keys must be in this format:
          <code>user@realm!token_id=token_secret</code>
        </p>
        <p>
          Example:
          <code>labyrinth@pve!disk-space=c0ffee1234567890abcdef</code>
        </p>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>QEMU Guest Agent Setup</b-card-title>
      <b-card-body>
        <p>
          For more accurate disk space information, especially for VMs, consider
          installing the QEMU Guest Agent inside your VMs.
        </p>

        <h6>Installation Instructions:</h6>

        <h6 class="mt-4">Ubuntu/Debian:</h6>
        <b-card bg-variant="light" class="mt-2 mb-3">
          <code>
            sudo apt-get update<br />
            sudo apt-get install qemu-guest-agent<br />
            sudo systemctl start qemu-guest-agent<br />
            sudo systemctl enable qemu-guest-agent
          </code>
        </b-card>

        <h6>CentOS/RHEL:</h6>
        <b-card bg-variant="light" class="mt-2 mb-3">
          <code>
            sudo yum install qemu-guest-agent<br />
            sudo systemctl start qemu-guest-agent<br />
            sudo systemctl enable qemu-guest-agent
          </code>
        </b-card>

        <h6>Windows:</h6>
        <ol>
          <li>
            Download the installer from
            <a href="https://pve.proxmox.com/" target="_blank">Proxmox website</a>
          </li>
          <li>Run the installer and follow the prompts</li>
          <li>Restart the VM</li>
        </ol>

        <h6>Enabling in Proxmox:</h6>
        <ol>
          <li>
            In the Proxmox web UI, select your VM and go to
            <strong>Hardware</strong>
          </li>
          <li>Check if <strong>QEMU Agent</strong> is listed</li>
          <li>
            If not present, click <strong>"Add"</strong> and select
            <strong>"QEMU Agent"</strong>
          </li>
          <li>Click "Add" and restart the VM</li>
        </ol>

        <p>
          Once installed, the Proxmox API will provide more detailed VM metrics
          including accurate disk usage within the guest OS.
        </p>
      </b-card-body>
    </b-card>

    <b-card class="mb-4 text-left text-start">
      <b-card-title>Manual Hosts Setup</b-card-title>
      <b-card-body>
        <p>
          You can manually add AWS EC2, OPNsense, or other custom hosts for disk space
          monitoring. Currently, Labyrinth displays the host configuration but disk
          space retrieval requires additional agent software.
        </p>

        <h6 class="mt-4">AWS EC2 Instance:</h6>
        <ol>
          <li>
            Install the CloudWatch agent:
            <b-card bg-variant="light" class="mt-2 mb-2">
              <code>
                wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm<br />
                rpm -U ./amazon-cloudwatch-agent.rpm
              </code>
            </b-card>
          </li>
          <li>Configure the agent to collect disk metrics</li>
          <li>
            Add the EC2 instance in Disk Space Check Settings
          </li>
        </ol>

        <h6 class="mt-4">OPNsense Router:</h6>
        <ol>
          <li>Enable SSH on OPNsense for monitoring access</li>
          <li>Configure SNMP for remote metric collection (optional)</li>
          <li>
            Add the OPNsense host in Disk Space Check Settings
          </li>
        </ol>

        <h6 class="mt-4">Generic Linux/Unix:</h6>
        <p>
          For any Linux/Unix-like system, you can set up metrics collection via:
        </p>
        <ul>
          <li>Telegraf (recommended) - Configure to send disk metrics to Labyrinth</li>
          <li>SNMP - Enable SNMP daemon for metric collection</li>
          <li>Custom scripts - Write scripts to report disk usage</li>
        </ul>
      </b-card-body>
    </b-card>

    <b-card class="text-left text-start">
      <b-card-title>Troubleshooting</b-card-title>
      <b-card-body>
        <h6>No Proxmox hosts appearing:</h6>
        <ul>
          <li>Ensure hosts are tagged with "Proxmox" in Dashboard</li>
          <li>Check that Proxmox hosts are discovered (run a network scan)</li>
          <li>Verify API key is configured in Settings</li>
        </ul>

        <h6>Error: Invalid API Key:</h6>
        <ul>
          <li>Verify the token exists and hasn't expired</li>
          <li>Check the format: <code>user@pam!token_id=token_secret</code></li>
          <li>
            Ensure the token was generated from the correct Proxmox cluster
          </li>
          <li>Test the token manually using curl (see API Key Management section)</li>
        </ul>

        <h6>No data showing for VMs/Containers:</h6>
        <ul>
          <li>Ensure API token has sufficient permissions (Sys.Audit, VM.Audit)</li>
          <li>
            Install QEMU Guest Agent in VMs for better data accuracy
          </li>
          <li>Try refreshing the page</li>
        </ul>

        <h6>Connection timeout:</h6>
        <ul>
          <li>Verify Proxmox host IP is reachable from Labyrinth</li>
          <li>Check that port 8006 is open and accessible</li>
          <li>Verify firewall rules allow connections</li>
        </ul>
      </b-card-body>
    </b-card>
  </div>
</template>

<script>
export default {
  name: "ProxmoxDocumentation",
};
</script>

<style lang="scss" scoped>
.proxmox-documentation {
  code {
    background-color: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Courier New", monospace;
  }

  h5 {
    margin-top: 1.5rem;
    margin-bottom: 0.75rem;
  }

  h6 {
    margin-top: 1rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
  }

  ol,
  ul {
    margin-bottom: 1rem;
  }

  li {
    margin-bottom: 0.5rem;
  }

  b-card {
    margin-top: 1rem;
  }
}
</style>
