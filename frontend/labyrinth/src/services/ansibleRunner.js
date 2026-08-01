// Shared Ansible save/run/poll logic used by both Deploy.vue and AiChat.vue.
// Extracted out of Deploy.vue so the two pages don't maintain separate
// copies of the same save -> run -> poll sequence.
import Helper from "@/helper";

export async function loadFilesList(auth, type) /* istanbul ignore next */ {
  return Helper.apiCall("uploads", type, auth);
}

export async function savePlaybookContents(
  auth,
  playbookName,
  becomeFile,
  contents
) /* istanbul ignore next */ {
  let formData = new FormData();
  formData.append("data", contents);

  return Helper.apiPost(
    "save_ansible_file/",
    playbookName.replace(".yml", ""),
    (becomeFile || "").replace(/.yml$/, ""),
    auth,
    formData
  );
}

// params: { hosts, playbook, vaultPassword, becomeFile, sshKey, totpFile }
// onLog(logs) is called with the accumulated log lines each time a poll comes back.
export async function runPlaybookAndPoll(
  auth,
  params,
  onLog
) /* istanbul ignore next */ {
  let data = {
    hosts: params.hosts,
    playbook: params.playbook.replace(".yml", ""),
    vault_password: params.vaultPassword,
    become_file: params.becomeFile.replace(".yml", ""),
    ssh_key: params.sshKey || "",
    totp_file: params.totpFile || "",
  };

  let formData = new FormData();
  formData.append("data", JSON.stringify(data));

  let response = await Helper.apiPost(
    "ansible_runner",
    "",
    "",
    auth,
    formData,
    false,
    1
  );

  const resp = await response.json();
  const job_id = resp.job_id;
  if (!job_id || resp.status !== "started") {
    throw new Error("Failed to start the playbook execution.");
  }

  let polling = true;
  let results = "";
  let logs = [];

  while (polling) {
    await new Promise((resolve) => setTimeout(resolve, 2000));

    let statusResponse = await Helper.apiCall(
      `ansible_status/${job_id}`,
      "",
      auth
    );

    const {
      status,
      logs: newLogs,
      results: newResults,
      error,
    } = statusResponse;
    logs = newLogs || [];

    if (status === "completed") {
      results = newResults || "";
      polling = false;
    } else if (status === "error") {
      throw new Error(error || "An error occurred during execution.");
    }

    if (onLog) {
      onLog(logs);
    }
  }

  return { job_id, results, logs };
}
