import axios from "axios";

const local_backend =
    "https://" + window.location.host.split(":")[0] + ":7210/api/";
const devel_port = "8101";

/*
const local_backend = "https://network.north.altamontco.com/api/"
const devel_port = ""
*/
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

    return auth.getAccessToken().then((accessToken) => {
      return axios
        .delete(full_url + "/" + encodeURIComponent(command), {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            Email: profile,
          },
        })
        .then((response) => {
          return response.data;
        }).catch(e=>{
            throw "Error " + e.response.status + ": " + e.response.data;
        });
    }).catch(e=>{
        throw e;
    });
  },
  apiPost(
    url,
    service,
    command,
    auth,
    arr,
    isUpload
  ) /* istanbul ignore next */ {
    var profile = auth["profile"]["email"];
    var full_url = "";
    if (window.location.host.indexOf(devel_port) != -1) {
      full_url = local_backend + url;
    } else {
      full_url = "/api/" + url;
    }
    return auth.getAccessToken().then((accessToken) => {
      let headers;
      headers = {
        Authorization: `Bearer ${accessToken}`,
        Email: profile,
      };

      if (isUpload != undefined) {
        headers["Content-Type"] = "multipart/form-data";
      }

      return axios({
        method: "post",
        url: full_url + service + "/" + command,
        data: arr,
        headers: headers,
      }).then((response) => {
        return response.data;
      });
    });
  },
};
