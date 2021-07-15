import axios from "axios";
export default {
    name: "Helper",
formatDate(date) {
    var d = new Date(date),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear();

    if (month.length < 2) 
        month = '0' + month;
    if (day.length < 2) 
        day = '0' + day;

    return [year, month, day].join('-');
},
	getURL(){
		var full_url  = ""
		if (window.location.host.indexOf("8002") != -1){
			full_url = "https://localhost:7000/api/" 
		}else{
			full_url = "/api/"
		}
		return full_url
	},
	apiCall(url, command, auth) {
		var profile = auth["profile"]["email"];
		var full_url = ""
		if (window.location.host.indexOf("8002") != -1){
			full_url = "https://localhost:7000/api/" + url
		}else{
			full_url = "/api/" + url
		}

		return auth.getAccessToken().then((accessToken) => {
			return axios
				.get(full_url + "/" + encodeURIComponent(command), {
					headers: {
						Authorization: `Bearer ${accessToken}`,
						Email: profile,
					},
				})
				.then((response) => {
					return response.data;
				});
		});
    },
    apiDelete(url, command, auth) {
		var profile = auth["profile"]["email"];
		var full_url = ""
		if (window.location.host.indexOf("8002") != -1){
			full_url = "https://localhost:7000/api/" + url
		}else{
			full_url = "/api/" + url
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
				});
		});
	},
	apiPost(url, service, command, auth, arr, isUpload) {
		var profile = auth['profile']['email']
		var full_url = ""
		if (window.location.host.indexOf("8002") != -1){
			full_url = "https://localhost:7000/api/" + url
		}else{
			full_url = "/api/" + url
		}
		return auth.getAccessToken().then(accessToken => {
			let headers
			headers = {
				Authorization: `Bearer ${accessToken}`,
				Email: profile,
			}

			if (isUpload != undefined) {
				headers['Content-Type'] = 'multipart/form-data'
			}

			return axios({
				method: 'post',
				url: full_url + service + '/' + command,
				data: arr,
				headers: headers,
			}).then(response => {
				return response.data
			})
		})
	},
};
