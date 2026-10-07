import axios from "axios";

const local_backend =
  "https://" + window.location.host.split(":")[0] + ":7210/api/";
const devel_port = "8101";

/*
const local_backend = "https://network.north.altamontco.com/api/"
const devel_port = ""
*/

// Inventory device types (keys match the backend's DEVICE_TYPES)
const deviceTypes = {
  server: { label: "Server", icon: "server" },
  vm: { label: "Virtual machine", icon: "cloud" },
  lxc: { label: "LXC container", icon: "cube" },
  pc: { label: "PC", icon: "desktop" },
  laptop: { label: "Laptop", icon: "laptop" },
  switch: { label: "Switch", icon: "network-wired" },
  router: { label: "Router", icon: "route" },
  firewall: { label: "Firewall", icon: "shield-alt" },
  ap: { label: "Access point", icon: "wifi" },
  bridge: { label: "Wireless bridge", icon: "broadcast-tower" },
  plc: { label: "PLC / controller", icon: "microchip" },
  iot: { label: "IoT device", icon: "plug" },
  camera: { label: "Camera", icon: "video" },
  printer: { label: "Printer", icon: "print" },
  phone: { label: "Phone", icon: "phone" },
  ups: { label: "UPS", icon: "car-battery" },
  storage: { label: "Storage / NAS", icon: "hdd" },
  "patch-panel": { label: "Patch panel", icon: "grip-lines" },
  other: { label: "Other", icon: "question-circle" },
};

export default {
  name: "Helper",
  capitalize: function (string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
  },
  validateIP(ip, count = 4) {
    try {
      var nonnumber = ip.replace(/\./g, "").replace(/[0-9]/g, "");
      if (nonnumber.length > 0) {
        return false;
      }

      var splits = ip.split(".");
      if (splits.length != count) {
        return false;
      }

      for (var i = 0; i < count; i++) {
        var temp = parseInt(splits[i]);
        if (isNaN(temp)) {
          /* istanbul ignore next */
          return false;
        }
        if (temp < 0 || temp > 254) {
          return false;
        }
      }
    } catch (e) {
      /* istanbul ignore next */
      return false;
    }
    return true;
  },
  formatDate(date, isTime = false) {
    var d = new Date(date),
      month = "" + (d.getMonth() + 1),
      day = "" + d.getDate(),
      year = d.getFullYear();

    if (month.length < 2) month = "0" + month;
    if (day.length < 2) day = "0" + day;

    if (isTime) {
      var hours = d.getHours();
      var minutes = d.getMinutes();
      var seconds = d.getSeconds();

      return hours + ":" + minutes + ":" + seconds;
    }
    return [year, month, day].join("-");
  },

  deviceTypes,
  linkTypes: ["ethernet", "fiber", "wireless", "vpn"],
  // Rolled-up device status from /inventory/ (`_live.status`)
  deviceStatuses: {
    up: { label: "Up", variant: "success" },
    down: { label: "Unreachable", variant: "danger" },
    error: { label: "Failing services", variant: "danger" },
    warning: { label: "Warning", variant: "warning" },
    unknown: { label: "Not checked yet", variant: "secondary" },
    none: { label: "No IP (not monitored)", variant: "light" },
  },
  deviceIcon(device) {
    let type = deviceTypes[device._live ? device._live.type : ""];
    return type ? type.icon : "circle";
  },
  deviceName(device) {
    return device.host || device.ip || device.mac;
  },

  listColors: function () {
    var retval = [
      "darkblue",
      "lightblue",
      "blue",
      "yellow",
      "orange",
      "red",
      "darkerblue",
    ];
    return retval;
  },
  getURL() {
    var full_url = "";
    if (window.location.host.indexOf(devel_port) != -1) {
      /* istanbul ignore next */
      full_url = local_backend;
    } else {
      full_url = "/api/";
    }
    return full_url;
  },
  apiCall(url, command, auth) /* istanbul ignore next */ {
    var profile = auth["profile"]["email"];
    var full_url = "";
    if (window.location.host.indexOf(devel_port) != -1) {
      full_url = local_backend + url;
    } else {
      full_url = "/api/" + url;
    }

    return auth
      .getAccessToken()
      .then((accessToken) => {
        return axios
          .get(full_url + "/" + encodeURIComponent(command), {
            headers: {
              Authorization: `Bearer ${accessToken}`,
              Email: profile,
            },
          })
          .then((response) => {
            return response.data;
          })
          .catch((e) => {
            throw "Error " + e.response.status + ": " + e.response.data;
          });
      })
      .catch((e) => {
        throw e;
      });
  },
  apiDelete(url, command, auth) /* istanbul ignore next */ {
    var profile = auth["profile"]["email"];
    var full_url = "";
    if (window.location.host.indexOf(devel_port) != -1) {
      full_url = local_backend + url;
    } else {
      full_url = "/api/" + url;
    }

    return auth
      .getAccessToken()
      .then((accessToken) => {
        return axios
          .delete(full_url + "/" + encodeURIComponent(command), {
            headers: {
              Authorization: `Bearer ${accessToken}`,
              Email: profile,
            },
          })
          .then((response) => {
            return response.data;
          })
          .catch((e) => {
            throw "Error " + e.response.status + ": " + e.response.data;
          });
      })
      .catch((e) => {
        throw e;
      });
  },
  apiPost(
    url,
    service,
    command,
    auth,
    arr,
    isUpload,
    raw
  ) /* istanbul ignore next */ {
    var profile = auth["profile"]["email"];
    var full_url = "";
    if (window.location.host.indexOf(devel_port) !== -1) {
      full_url = local_backend + url;
    } else {
      full_url = "/api/" + url;
    }

    console.log(url);
    console.log(service);
    console.log(command);
    console.log(auth);
    console.log(arr);
    console.log(isUpload);
    console.log(raw);

    return auth.getAccessToken().then((accessToken) => {
      // `isUpload` is kept for existing callers, but no Content-Type is set:
      // fetch adds the multipart boundary itself, and a hand-set
      // "multipart/form-data" header without one leaves the server unable to
      // find the uploaded file.
      let headers = {
        Authorization: `Bearer ${accessToken}`,
        Email: profile,
      };

      return fetch(full_url + service + "/" + command, {
        method: "POST",
        headers: headers,
        body: arr,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
          }
          return raw ? response : response.text();
        })
        .then((data) => {
          if (raw === undefined) {
            return data;
          } else {
            console.log("RETVAL");
            console.log(data);
            return data;
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          throw error;
        });
    });
  },
  apiPut(url, command, auth, body) /* istanbul ignore next */ {
    var profile = auth["profile"]["email"];
    var full_url = "";
    if (window.location.host.indexOf(devel_port) !== -1) {
      full_url = local_backend + url;
    } else {
      full_url = "/api/" + url;
    }

    return auth.getAccessToken().then((accessToken) => {
      return fetch(full_url + "/" + command, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          Email: profile,
          "Content-Type": "application/json",
        },
        body: typeof body === "string" ? body : JSON.stringify(body),
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
          }
          return response.text();
        })
        .catch((error) => {
          console.error("Error:", error);
          throw error;
        });
    });
  },
};
